"""model_buffer.py — Buffer cleaner para modelos locales (Ollama).

Problema:
    Ollama mantiene los modelos cargados en RAM entre llamadas. Si tienes
    32GB de RAM y un modelo de 22GB (qwen3.6), ese modelo acapara la RAM
    y los demás modelos pequeños (1.5B, 3B) se vuelven lentos, colgados o
    "lobotomizados" (responden mal por falta de memoria).

Solución:
    Antes de cambiar de modelo, descargamos los modelos en uso que NO
    necesitamos, dejando solo el target + lo justo. Si no hay RAM
    suficiente para el target, descargamos TODO y dejamos al SO decidir.

Políticas:
    - KEEP_ACTIVE: solo descarga modelos que NO se usan en N minutos
    - LRU: descarga el Least Recently Used hasta que quepa el target
    - SAFE: nunca descarga el modelo target; descarga los demás hasta que quepa
    - HARD: descarga todo antes de cargar el target (maxlibera RAM, lento)

Uso:
    from model_buffer import ModelBuffer
    buf = ModelBuffer(ollama_url="http://127.0.0.1:11434")
    # Antes de cambiar a un modelo grande:
    buf.prepare_for("qwen3.6:latest", policy="LRU")
    # ... usar el modelo ...
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Literal


PolicyName = Literal["KEEP_ACTIVE", "LRU", "SAFE", "HARD"]


@dataclass
class LoadedModel:
    """Snapshot de un modelo cargado en Ollama."""
    name: str
    size_bytes: int = 0
    expires_at: str = ""
    vram_bytes: int = 0

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 ** 3)


@dataclass
class BufferReport:
    """Reporte de una operación de limpieza."""
    target: str
    policy: PolicyName
    freed_gb: float
    unloaded: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


class ModelBuffer:
    """Gestor del buffer de modelos cargados en Ollama local."""

    # Ventana por defecto: modelos sin uso > N minutos se pueden descargar
    DEFAULT_IDLE_MINUTES = 3.0

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        idle_minutes: float = DEFAULT_IDLE_MINUTES,
        request_timeout_s: float = 10.0,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.idle_minutes = idle_minutes
        self.request_timeout_s = request_timeout_s

    # ─── API HTTP a Ollama ───────────────────────────────

    def _http_post(self, path: str, payload: dict) -> dict | None:
        url = f"{self.ollama_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return {"__error__": str(exc)}

    def _http_get(self, path: str) -> dict | None:
        url = f"{self.ollama_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self.request_timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return {"__error__": str(exc)}

    # ─── Estado de Ollama ────────────────────────────────

    def list_loaded(self) -> list[LoadedModel]:
        """Lista los modelos cargados actualmente en Ollama."""
        data = self._http_get("/api/ps")
        if not data or "__error__" in data:
            return []
        out: list[LoadedModel] = []
        for m in data.get("models", []):
            out.append(LoadedModel(
                name=str(m.get("name", "")),
                size_bytes=int(m.get("size", 0)),
                expires_at=str(m.get("expires_at", "")),
                vram_bytes=int(m.get("size_vram", 0)),
            ))
        return out

    def unload(self, model_name: str) -> bool:
        """Descarga un modelo de Ollama (keep_alive=0)."""
        result = self._http_post("/api/generate", {
            "model": model_name,
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
        })
        if not result:
            return False
        if "__error__" in result:
            return False
        # Ollama responde con done_reason="unload" cuando libera
        return result.get("done_reason") == "unload" or result.get("done") is True

    def preload(self, model_name: str, keep_alive_minutes: int = 10) -> bool:
        """Pre-carga un modelo con keep_alive explícito."""
        result = self._http_post("/api/generate", {
            "model": model_name,
            "prompt": "",
            "stream": False,
            "keep_alive": f"{keep_alive_minutes}m",
        })
        return bool(result) and "__error__" not in (result or {})

    # ─── Políticas ───────────────────────────────────────

    def _idle_models(self, models: list[LoadedModel]) -> list[LoadedModel]:
        """Modelos cuyo keep_alive ya expiró o está por expirar."""
        # Ollama devuelve expires_at como ISO con offset; usamos comparación
        # simple: si expires_at es vacío, asumimos idle.
        # En la práctica Ollama solo devuelve modelos activos.
        # Esta función queda como hook para futuro tracking propio.
        return [m for m in models if not m.expires_at]

    def _candidates_to_unload(
        self,
        target: str,
        policy: PolicyName,
    ) -> tuple[list[LoadedModel], list[LoadedModel]]:
        """Devuelve (a_descargar, a_mantener) según la política."""
        loaded = self.list_loaded()
        if not loaded:
            return [], []

        target_norm = target.strip().lower()

        if policy == "HARD":
            # Descargar TODO. Ollama descargará el target también si está
            # cargado; lo recargamos después en prepare_for.
            return list(loaded), []

        if policy == "SAFE":
            # Mantener el target si está cargado; descargar el resto.
            keep, drop = [], []
            for m in loaded:
                if m.name.lower() == target_norm:
                    keep.append(m)
                else:
                    drop.append(m)
            return drop, keep

        if policy == "KEEP_ACTIVE":
            # Solo descargar modelos que ya pasaron su keep_alive.
            idle = self._idle_models(loaded)
            keep = [m for m in loaded if m not in idle]
            return idle, keep

        # LRU (default): descargar los menos usados primero.
        # Sin tracking propio, aproximamos por expires_at: el que expira
        # antes es el menos usado.
        candidates = [m for m in loaded if m.name.lower() != target_norm]
        # Orden por expires_at ascendente (caducan antes = descargar antes)
        candidates.sort(key=lambda m: m.expires_at or "")
        keep = [m for m in loaded if m.name.lower() == target_norm]
        return candidates, keep

    def prepare_for(
        self,
        target: str,
        policy: PolicyName = "LRU",
        target_size_gb: float | None = None,
    ) -> BufferReport:
        """Prepara Ollama para usar `target`. Descarga lo necesario.

        Args:
            target: nombre del modelo destino (e.g. "qwen3.6:latest")
            policy: KEEP_ACTIVE | LRU | SAFE | HARD
            target_size_gb: tamaño estimado del target. Si se sabe que no
                va a caber junto a otros, se descargan más.
        """
        started = time.time()
        report = BufferReport(target=target, policy=policy, freed_gb=0.0)

        try:
            drop, keep = self._candidates_to_unload(target, policy)
            report.kept = [m.name for m in keep]

            for m in drop:
                ok = self.unload(m.name)
                if ok:
                    report.unloaded.append(m.name)
                    report.freed_gb += m.size_gb
                else:
                    report.errors.append(f"no se pudo descargar {m.name}")

            # Si el target no está cargado y la política lo permite,
            # pre-cargarlo con un keep_alive razonable.
            target_loaded = any(m.name.lower() == target.strip().lower() for m in keep)
            if not target_loaded and policy in ("LRU", "SAFE", "HARD"):
                if self.preload(target, keep_alive_minutes=10):
                    report.kept.append(target)
                else:
                    report.errors.append(f"no se pudo pre-cargar {target}")

        except Exception as exc:
            report.errors.append(f"excepción: {exc}")

        report.elapsed_ms = (time.time() - started) * 1000
        return report

    def smart_pick(
        self,
        candidates: list[str],
        target_size_gb: dict[str, float] | None = None,
    ) -> str | None:
        """Elige el mejor modelo disponible de una lista, considerando RAM.

        Si el primero está bloqueado por otro modelo grande en RAM,
        lo descarga y lo prueba; si falla, prueba el siguiente.
        """
        for c in candidates:
            report = self.prepare_for(c, policy="LRU")
            # Si no hubo errores, el modelo está listo
            if not report.errors:
                return c
        return None


# ─── Helper de integración ─────────────────────────────────

_default_buffer: ModelBuffer | None = None


def get_model_buffer(ollama_url: str = "http://127.0.0.1:11434") -> ModelBuffer:
    """Singleton lazy del buffer."""
    global _default_buffer
    if _default_buffer is None:
        _default_buffer = ModelBuffer(ollama_url=ollama_url)
    return _default_buffer


if __name__ == "__main__":
    # CLI rápida: python -m model_buffer status|prepare <model> [policy]
    import sys
    buf = ModelBuffer()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        loaded = buf.list_loaded()
        if not loaded:
            print("(ningún modelo cargado)")
        for m in loaded:
            print(f"  {m.name:40} {m.size_gb:6.2f} GB  expira={m.expires_at or '?'}")
    elif cmd == "prepare":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        policy = sys.argv[3] if len(sys.argv) > 3 else "LRU"
        if not target:
            print("uso: python -m model_buffer prepare <modelo> [policy]")
            sys.exit(1)
        report = buf.prepare_for(target, policy=policy)  # type: ignore[arg-type]
        print(f"Target: {report.target}  Policy: {report.policy}")
        print(f"Descargados: {report.unloaded}")
        print(f"Mantenidos:  {report.kept}")
        print(f"Errores:     {report.errors}")
        print(f"RAM liberada: {report.freed_gb:.2f} GB en {report.elapsed_ms:.0f} ms")
    else:
        print(f"comando desconocido: {cmd}")
        sys.exit(1)
