"""wal.py — Write-Ahead Log para el bridge.

Garantiza la invariante: **si el bridge afirma que un evento fue
aceptado, está en disco.**

Implementación:
    - `WALStore` mantiene un archivo append-only en
      `project_root/.gabo/integrations/pi/wal/<execution-id-component>.jsonl`.
    - Cada evento se delega a `state.write` en modo append; el owner hace
      `write` + `flush` + `fsync` antes de retornar.
    - El bridge llama a `wal.append(event)` justo después de validar
      el evento pero antes de `log.append(event)` en memoria.
    - Si la escritura falla (disco lleno, permisos), el bridge
      rechaza la ejecución con `BRIDGE_PERSISTENCE_FAILED`.

Notas de rendimiento:
    - Fase 0-3 del PLAN no especifica volumen. v0.1 hacía un fsync por
      evento. El WAL también lo hace (mismo costo).
    - El gateway abre y cierra el archivo por evento. La invariante de fsync
      se mantiene; no se conserva un handle de escritura en el llamador.

Esta es la acción A2 del dictamen CRIT v0.2.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .errors import BridgeError
from .identity_paths import artifact_component


WAL_DIRNAME: str = "wal"
WAL_FILENAME_SUFFIX: str = ".jsonl"


class WALStore:
    """Append duradero de WALs delegado al owner de estado del gateway."""

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root)
        self._base_dir = self._workspace_root / ".gabo" / "integrations" / "pi" / WAL_DIRNAME
        self._global_lock = threading.Lock()

    def _safe_id(self, execution_id: str) -> str:
        return artifact_component(execution_id)

    def append(self, execution_id: str, event: dict[str, Any]) -> None:
        """Añade un evento al WAL con fsync.

        Raises:
            BridgeError: si la escritura o el fsync fallan.
        """
        try:
            line = json.dumps(event, ensure_ascii=False, sort_keys=True, default=str)
            from bago_core.server_effects import append_text_durable

            with self._global_lock:
                append_text_durable(
                    self.path_for(execution_id),
                    line + "\n",
                    trusted_root=self._base_dir,
                    source_surface="pi.wal",
                    session_id=f"pi.execution:{execution_id}",
                )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise BridgeError(
                "WAL append failed",
                details={
                    "execution_id": execution_id,
                    "path": str(self.path_for(execution_id)),
                    "error": str(exc),
                },
            ) from exc

    def close(self, execution_id: str) -> None:
        return None

    def close_all(self) -> None:
        return None

    def path_for(self, execution_id: str) -> Path:
        safe = self._safe_id(execution_id)
        return self._base_dir / f"{safe}{WAL_FILENAME_SUFFIX}"

    def list_events(self, execution_id: str) -> list[dict[str, Any]]:
        """Lee todos los eventos persistidos para una ejecución.

        Útil para recovery post-crash. La lista está en orden de
        inserción (el WAL es append-only).
        """
        path = self.path_for(execution_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # Línea corrupta: la descartamos, pero no fallamos
                    # la lectura completa. El evento podría haber sido
                    # parcial durante un crash.
                    continue
        return events


__all__ = ["WALStore", "WAL_DIRNAME", "WAL_FILENAME_SUFFIX"]
