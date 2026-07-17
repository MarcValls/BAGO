#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
script_registry.py — BAGO 4.1.5 Script Registry

Índice explícito de scripts Python agrupados por baterías funcionales.
Permite resolver una tarea hacia un script concreto y decir qué falta cuando
no existe un script compatible.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token}


def _contains_path(base: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class ScriptBattery:
    id: str
    description: str
    keywords: tuple[str, ...]
    missing_script: str
    fallback_tool: str | None = None


@dataclass(frozen=True)
class ScriptSpec:
    id: str
    battery: str
    description: str
    path: str
    keywords: tuple[str, ...] = ()
    fixed_args: tuple[str, ...] = ()
    enabled: bool = True

    def resolved_path(self, repo_root: Path) -> Path:
        return (repo_root / self.path).resolve()

    def command(self, repo_root: Path, extra_args: list[str] | None = None) -> list[str]:
        script_path = self.resolved_path(repo_root)
        if not _contains_path(repo_root, script_path):
            raise ValueError(f"Script fuera del repo: {self.path}")
        return [sys.executable, str(script_path), *self.fixed_args, *(extra_args or [])]

    def as_dict(self, repo_root: Path) -> dict[str, Any]:
        script_path = self.resolved_path(repo_root)
        return {
            "id": self.id,
            "battery": self.battery,
            "description": self.description,
            "path": self.path,
            "enabled": self.enabled,
            "exists": script_path.exists(),
            "keywords": list(self.keywords),
            "fixed_args": list(self.fixed_args),
        }


@dataclass(frozen=True)
class ScriptMatch:
    script: ScriptSpec | None
    battery: ScriptBattery | None
    score: int = 0
    reason: str = ""
    missing_script: str = ""


class ScriptRegistry:
    """Índice explícito de scripts y baterías de BAGO."""

    def __init__(self, repo_root: str | Path | None = None, event_sink: Any | None = None) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[2]).resolve()
        self.event_sink = event_sink
        self._batteries: dict[str, ScriptBattery] = {
            "filesystem": ScriptBattery(
                id="filesystem",
                description="Exploración de rutas, directorios y análisis de estructura.",
                keywords=(
                    "file",
                    "filesystem",
                    "directory",
                    "dir",
                    "folder",
                    "tree",
                    "path",
                    "scan",
                    "list",
                    "directorio",
                    "carpeta",
                    "listar",
                    "analiza",
                    "analizar",
                ),
                missing_script="scan_directory.py",
                fallback_tool="list_directory",
            ),
            "diagnostics": ScriptBattery(
                id="diagnostics",
                description="Smoke tests, validación y salud del runtime.",
                keywords=("test", "validate", "diagnose", "smoke", "health", "check", "prueba", "validar", "validacion", "salud"),
                missing_script="run_smoke_tests.py",
            ),
            "chat": ScriptBattery(
                id="chat",
                description="REPL, comandos slash y sesión persistente.",
                keywords=("chat", "repl", "command", "slash", "session", "conversation", "sesion", "comandos"),
                missing_script="chat_qa.py",
            ),
            "runtime": ScriptBattery(
                id="runtime",
                description="Integraciones locales, providers y adapters.",
                keywords=("runtime", "ollama", "provider", "adapter", "cpp", "local", "proveedor", "adaptador"),
                missing_script="runtime_probe.py",
            ),
            "evidence": ScriptBattery(
                id="evidence",
                description="Bundles de evidencia, contratos y reportes.",
                keywords=("evidence", "bundle", "contract", "report", "evidencia", "contrato", "informe"),
                missing_script="generate_evidence.py",
            ),
            "release": ScriptBattery(
                id="release",
                description="Empaquetado, validación y publicación.",
                keywords=("release", "publish", "zip", "tag", "deploy", "pack", "publicar", "empaquetar"),
                missing_script="publish_release.py",
            ),
            "data": ScriptBattery(
                id="data",
                description="Procesamiento de CSV/JSON y reportes tabulares.",
                keywords=("csv", "json", "table", "report", "dataset", "data", "datos", "tabla"),
                missing_script="process_data.py",
            ),
        }
        self._scripts: dict[str, ScriptSpec] = {
            "diagnostics.launcher_test": ScriptSpec(
                id="diagnostics.launcher_test",
                battery="diagnostics",
                description="Smoke test del launcher principal.",
                path="bago_core/launcher.py",
                keywords=("launcher", "validate", "boot"),
                fixed_args=("--test",),
            ),
            "diagnostics.cli_test": ScriptSpec(
                id="diagnostics.cli_test",
                battery="diagnostics",
                description="Smoke test del entrypoint CLI.",
                path="bago_core/cli.py",
                keywords=("cli", "entrypoint", "bootstrap"),
                fixed_args=("--test",),
            ),
            "filesystem.scan_directory": ScriptSpec(
                id="filesystem.scan_directory",
                battery="filesystem",
                description="Recorre directorios y muestra un arbol legible.",
                path="scripts/scan_directory.py",
                keywords=("scan", "directory", "tree", "list", "directory tree", "directorio", "carpeta"),
            ),
            "release.publish_release": ScriptSpec(
                id="release.publish_release",
                battery="release",
                description="Prepara un release local y puede construir un zip del repositorio.",
                path="scripts/publish_release.py",
                keywords=("release", "publish", "zip", "bundle", "publicar", "empaquetar"),
            ),
            "diagnostics.e2e": ScriptSpec(
                id="diagnostics.e2e",
                battery="diagnostics",
                description="Prueba end-to-end del framework.",
                path="test_e2e.py",
                keywords=("e2e", "integration", "prueba", "endtoend"),
            ),
            "diagnostics.claim_ledger_test": ScriptSpec(
                id="diagnostics.claim_ledger_test",
                battery="diagnostics",
                description="Smoke test del claim ledger.",
                path="bago_core/claim_ledger.py",
                keywords=("ledger", "claim", "evidence"),
                fixed_args=("--test",),
            ),
            "diagnostics.evidence_bundle_test": ScriptSpec(
                id="diagnostics.evidence_bundle_test",
                battery="diagnostics",
                description="Smoke test del generador de bundles de evidencia.",
                path="bago_core/evidence_bundle.py",
                keywords=("evidence", "bundle", "contract"),
                fixed_args=("--test",),
            ),
            "chat.commands_test": ScriptSpec(
                id="chat.commands_test",
                battery="chat",
                description="Smoke test del parser de comandos slash.",
                path=".bago/chat/commands.py",
                keywords=("commands", "slash", "parser"),
                fixed_args=("--test",),
            ),
            "chat.repl_test": ScriptSpec(
                id="chat.repl_test",
                battery="chat",
                description="Smoke test del REPL de chat.",
                path=".bago/chat/repl.py",
                keywords=("repl", "menu", "ui"),
                fixed_args=("--test",),
            ),
            "chat.session_manager_test": ScriptSpec(
                id="chat.session_manager_test",
                battery="chat",
                description="Smoke test del session manager.",
                path=".bago/core/session_manager.py",
                keywords=("session", "manager", "context"),
                fixed_args=("--test",),
            ),
            "runtime.embedding_store_test": ScriptSpec(
                id="runtime.embedding_store_test",
                battery="runtime",
                description="Smoke test del almacén de embeddings.",
                path=".bago/core/embedding_store.py",
                keywords=("embedding", "store", "vector"),
                fixed_args=("--test",),
            ),
            "runtime.knowledge_base_test": ScriptSpec(
                id="runtime.knowledge_base_test",
                battery="runtime",
                description="Smoke test de la knowledge base.",
                path=".bago/core/knowledge_base.py",
                keywords=("knowledge", "kb", "database"),
                fixed_args=("--test",),
            ),
        }

    def get_battery(self, battery_id: str) -> ScriptBattery | None:
        return self._batteries.get(battery_id)

    def get_script(self, script_id: str) -> ScriptSpec | None:
        return self._scripts.get(script_id)

    def list_batteries(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for battery in self._batteries.values():
            scripts = self.list_scripts(battery.id)
            items.append({
                "id": battery.id,
                "description": battery.description,
                "keywords": list(battery.keywords),
                "missing_script": battery.missing_script,
                "fallback_tool": battery.fallback_tool,
                "script_count": len(scripts),
                "scripts": scripts,
            })
        return items

    def list_scripts(self, battery_id: str | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for script in self._scripts.values():
            if battery_id and script.battery != battery_id:
                continue
            items.append(script.as_dict(self.repo_root))
        return items

    def _score_batteries(self, text: str) -> list[tuple[int, ScriptBattery]]:
        tokens = _tokenize(text)
        scored: list[tuple[int, ScriptBattery]] = []
        for battery in self._batteries.values():
            score = len(tokens.intersection(battery.keywords))
            if battery.id in text.lower():
                score += 2
            scored.append((score, battery))
        scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
        return scored

    def _score_script(self, text: str, script: ScriptSpec, battery_score: int) -> int:
        tokens = _tokenize(text)
        haystack = _tokenize(script.id) | _tokenize(script.description) | _tokenize(script.path)
        haystack.update(script.keywords)
        score = battery_score * 10 + len(tokens.intersection(haystack)) * 3
        text_lower = text.lower()
        if script.id.lower() in text_lower:
            score += 25
        if Path(script.path).stem.lower() in text_lower:
            score += 10
        return score

    def resolve_task(self, task: str) -> ScriptMatch:
        text = task.strip()
        if not text:
            return ScriptMatch(script=None, battery=None, reason="Tarea vacía.")

        battery_scores = self._score_batteries(text)
        best_battery_score, best_battery = battery_scores[0] if battery_scores else (0, None)
        scored_scripts: list[tuple[int, ScriptSpec]] = []
        for script in self._scripts.values():
            battery_score = 0
            battery = self._batteries.get(script.battery)
            if battery is not None:
                battery_score = len(_tokenize(text).intersection(battery.keywords))
                if battery.id in text.lower():
                    battery_score += 2
            score = self._score_script(text, script, battery_score)
            scored_scripts.append((score, script))
        scored_scripts.sort(key=lambda item: (item[0], item[1].id), reverse=True)

        if scored_scripts and scored_scripts[0][0] > 0:
            score, script = scored_scripts[0]
            battery = self._batteries.get(script.battery)
            reason = f"Script '{script.id}' coincide con la tarea."
            return ScriptMatch(script=script, battery=battery, score=score, reason=reason)

        if best_battery is not None and best_battery_score > 0:
            return ScriptMatch(
                script=None,
                battery=best_battery,
                score=best_battery_score,
                reason=f"La tarea cae en la batería '{best_battery.id}', pero no hay script compatible.",
                missing_script=best_battery.missing_script,
            )

        return ScriptMatch(script=None, battery=None, reason="No se pudo resolver la tarea contra ninguna batería.")

    def describe_script(self, script: ScriptSpec) -> str:
        status = "enabled" if script.enabled else "disabled"
        path = script.resolved_path(self.repo_root)
        exists = "exists" if path.exists() else "missing"
        return f"{script.id} [{status}, {exists}] -> {script.path}"

    def describe_catalog(self) -> str:
        lines: list[str] = []
        for battery in self.list_batteries():
            lines.append(f"{battery['id']}: {battery['description']}")
            lines.append(f"  falta: {battery['missing_script']}")
            if battery["fallback_tool"]:
                lines.append(f"  fallback: {battery['fallback_tool']}")
            if battery["scripts"]:
                for script in battery["scripts"]:
                    marker = "✓" if script["enabled"] and script["exists"] else "!"
                    lines.append(
                        f"  {marker} {script['id']} — {script['description']} ({script['path']})"
                    )
            else:
                lines.append("  (sin scripts registrados)")
        return "\n".join(lines)

    def missing_script_message(self, task: str, match: ScriptMatch | None = None) -> str:
        match = match or self.resolve_task(task)
        if match.battery is None:
            return (
                f"No hay script registrado para: {task}\n"
                "Falta crear una batería compatible o ampliar el índice explícito."
            )
        lines = [
            f"No hay script registrado para: {task}",
            f"Batería: {match.battery.id}",
            f"Falta script: {match.missing_script}",
        ]
        if match.battery.fallback_tool:
            lines.append(f"Fallback disponible: tool {match.battery.fallback_tool}")
        lines.append("Registra el script en .bago/core/script_registry.py o en scripts/.")
        return "\n".join(lines)

    def _emit_backend_event(self, kind: str, title: str, detail: str = "", *, reset_clock: bool = True) -> None:
        sink = getattr(self, "event_sink", None)
        if sink is None:
            return
        try:
            if hasattr(sink, "record_backend_event"):
                sink.record_backend_event(kind, title, detail, reset_clock=reset_clock)
        except Exception:
            pass

    def run_script(self, script_id: str, args: list[str] | None = None) -> str:
        script = self.get_script(script_id)
        if script is None:
            known = ", ".join(sorted(self._scripts))
            raise ValueError(f"Script '{script_id}' no está registrado. Disponibles: {known}")
        if not script.enabled:
            raise ValueError(f"Script '{script_id}' está deshabilitado.")
        script_path = script.resolved_path(self.repo_root)
        if not script_path.exists():
            raise FileNotFoundError(f"Script '{script_id}' no existe en disco: {script.path}")
        cmd = script.command(self.repo_root, args)
        self._emit_backend_event(
            "script_start",
            f"Script lanzado: {script_id}",
            detail=" ".join(cmd[:2]) if cmd else script_id,
            reset_clock=True,
        )
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                cwd=str(self.repo_root),
                timeout=120,
            )
        except Exception as exc:
            self._emit_backend_event(
                "script_failed",
                f"Script fallido: {script_id}",
                detail=str(exc),
                reset_clock=False,
            )
            raise
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            detail = stderr or stdout or "(sin salida)"
            self._emit_backend_event(
                "script_failed",
                f"Script fallido: {script_id}",
                detail=f"exit={result.returncode}; {detail}",
                reset_clock=False,
            )
            raise RuntimeError(f"Exit code {result.returncode}\n{detail}")
        self._emit_backend_event(
            "script_done",
            f"Script completado: {script_id}",
            detail=stdout or stderr or "(sin salida)",
            reset_clock=False,
        )
        return stdout or stderr or "(sin salida)"

    def run_task(self, task: str, args: list[str] | None = None) -> str:
        match = self.resolve_task(task)
        if match.script is None:
            return self.missing_script_message(task, match)
        script_path = match.script.resolved_path(self.repo_root)
        if not script_path.exists():
            return (
                f"El script registrado '{match.script.id}' no existe en disco: {match.script.path}\n"
                + self.missing_script_message(task, match)
            )
        return self.run_script(match.script.id, args)


def _run_tests() -> int:
    reg = ScriptRegistry()
    battery_names = [item["id"] for item in reg.list_batteries()]
    assert "filesystem" in battery_names
    assert "diagnostics" in battery_names

    catalog = reg.describe_catalog()
    assert "diagnostics.launcher_test" in catalog
    assert "filesystem" in catalog

    match = reg.resolve_task("analiza el directorio actual")
    assert match.battery is not None
    assert match.battery.id == "filesystem"
    assert match.script is not None
    assert match.script.id == "filesystem.scan_directory"
    output = reg.run_task("analiza el directorio actual")
    assert ".bago" in output or "bago.cmd" in output

    release_match = reg.resolve_task("prepara un release del proyecto")
    assert release_match.battery is not None
    assert release_match.battery.id == "release"
    assert release_match.script is not None
    assert release_match.script.id == "release.publish_release"

    scripted = reg.resolve_task("haz una prueba end to end del framework")
    assert scripted.script is not None
    assert scripted.script.id == "diagnostics.e2e"

    print("script_registry.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
