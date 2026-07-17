"""wal.py — Write-Ahead Log para el bridge.

Garantiza la invariante: **si el bridge afirma que un evento fue
aceptado, está en disco.**

Implementación:
    - `WAL` mantiene un archivo append-only en
      `project_root/.gabo/integrations/pi/wal/<execution_id>.jsonl`.
    - Cada escritura hace `write` + `flush` + `fsync` antes de
      retornar. Si el proceso crashea tras la escritura, el WAL ya
      tiene el evento.
    - El bridge llama a `wal.append(event)` justo después de validar
      el evento pero antes de `log.append(event)` en memoria.
    - Si la escritura falla (disco lleno, permisos), el bridge
      rechaza la ejecución con `BRIDGE_PERSISTENCE_FAILED`.

Notas de rendimiento:
    - Fase 0-3 del PLAN no especifica volumen. v0.1 hacía un fsync por
      evento. El WAL también lo hace (mismo costo).
    - En producción con miles de eventos, agrupar fsync cada N
      eventos es un trade-off; v0.2 mantiene la invariante estricta.

Esta es la acción A2 del dictamen CRIT v0.2.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .errors import BridgeError


WAL_DIRNAME: str = "wal"
WAL_FILENAME_SUFFIX: str = ".jsonl"


@dataclass
class _WALHandle:
    """Handle de un WAL abierto. Thread-local y por ejecución."""

    execution_id: str
    path: Path
    _fh: Any  # file handle

    def close(self) -> None:
        try:
            if self._fh is not None and not self._fh.closed:
                self._fh.flush()
                os.fsync(self._fh.fileno())
                self._fh.close()
        except OSError:
            pass


class WALStore:
    """Pool de WALs por execution_id, con lock por handle."""

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root)
        self._base_dir = self._workspace_root / ".gabo" / "integrations" / "pi" / WAL_DIRNAME
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, _WALHandle] = {}
        self._global_lock = threading.Lock()

    def _safe_id(self, execution_id: str) -> str:
        return "".join(c for c in execution_id if c.isalnum() or c in "-_")

    def _open(self, execution_id: str) -> _WALHandle:
        safe = self._safe_id(execution_id)
        path = self._base_dir / f"{safe}{WAL_FILENAME_SUFFIX}"
        # Append mode; line buffered for incremental fsync.
        fh = open(path, "a", encoding="utf-8", newline="\n")
        return _WALHandle(execution_id=safe, path=path, _fh=fh)

    def append(self, execution_id: str, event: dict[str, Any]) -> None:
        """Añade un evento al WAL con fsync.

        Raises:
            BridgeError: si la escritura o el fsync fallan.
        """
        with self._global_lock:
            handle = self._handles.get(execution_id)
            if handle is None:
                handle = self._open(execution_id)
                self._handles[execution_id] = handle
        try:
            line = json.dumps(event, ensure_ascii=False, sort_keys=True, default=str)
            fh = handle._fh
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        except (OSError, TypeError, ValueError) as exc:
            raise BridgeError(
                "WAL append failed",
                details={
                    "execution_id": execution_id,
                    "path": str(handle.path),
                    "error": str(exc),
                },
            ) from exc

    def close(self, execution_id: str) -> None:
        with self._global_lock:
            handle = self._handles.pop(execution_id, None)
        if handle is not None:
            handle.close()

    def close_all(self) -> None:
        with self._global_lock:
            handles = list(self._handles.values())
            self._handles.clear()
        for h in handles:
            h.close()

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
