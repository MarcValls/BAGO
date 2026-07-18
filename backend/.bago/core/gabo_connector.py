"""gabo_connector.py — Conecta .gabo/ manifests al runtime de BAGO.

Lee los manifests JSON en .gabo/manifests/ y construye un contexto
verificable que se puede inyectar en el system prompt del LLM.

El contexto .gabo/ es la fuente de verdad del proyecto:
  - Qué áreas existen (api, core, tools, agents, ...)
  - Cuántos archivos tiene cada área
  - Si el área está rota o no
  - Versión del workspace

Esto permite al modelo responder con conocimiento verificable del
proyecto en vez de alucinar estructura.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class GaboArea:
    """Una área del workspace según .gabo/manifests/."""
    area: str
    root_rel: str
    exists: bool
    broken: bool
    file_count: int
    files: list[str] = field(default_factory=list)


@dataclass
class GaboSnapshot:
    """Snapshot del contexto .gabo/ leído en un momento dado."""
    captured: str = ""
    workspace_root: str = ""
    version: str = ""
    areas: list[GaboArea] = field(default_factory=list)
    total_files: int = 0
    broken_areas: list[str] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return len(self.areas) > 0

    def to_prompt_block(self, max_chars: int = 1200) -> str:
        """Renderiza el snapshot como bloque inyectable en system prompt."""
        if not self.is_available:
            return ""

        lines = [
            f"[GABO CONTEXT SEED — captured {self.captured}]",
            f"Workspace: {self.workspace_root} · v{self.version}",
            f"Áreas: {len(self.areas)} · Archivos totales: {self.total_files}",
            "",
        ]

        for area in self.areas:
            status = "✓" if not area.broken else "✗"
            lines.append(f"  {status} {area.area} ({area.file_count}f) → {area.root_rel}")
            if len(lines) > max_chars // 40:
                break

        lines.append("[/GABO CONTEXT SEED]")
        result = "\n".join(lines)

        if len(result) > max_chars:
            result = result[:max_chars - 3] + "..."
        return result


class GaboConnector:
    """Lee .gabo/ manifests y mantiene un snapshot del contexto del proyecto."""

    def __init__(self, workspace_root: str | Path | None = None):
        if workspace_root is None:
            workspace_root = Path.cwd()
        self.workspace_root = Path(workspace_root)
        self._gabo_dir = self.workspace_root / ".gabo"
        self._manifests_dir = self._gabo_dir / "manifests"
        self._index_path = self._gabo_dir / "index.md"
        self._live_path = self._gabo_dir / "live.json"
        self._snapshot: GaboSnapshot | None = None

    @property
    def is_available(self) -> bool:
        """True si .gabo/ existe y tiene manifests."""
        return self._manifests_dir.is_dir() and any(self._manifests_dir.glob("*.json"))

    def load(self) -> GaboSnapshot:
        """Lee todos los manifests y construye un snapshot."""
        if not self.is_available:
            self._snapshot = GaboSnapshot(workspace_root=str(self.workspace_root))
            return self._snapshot

        areas: list[GaboArea] = []
        total_files = 0
        broken: list[str] = []
        captured = ""
        version = ""

        # Leer index.md para metadata
        if self._index_path.exists():
            idx_text = self._index_path.read_text(encoding="utf-8", errors="replace")
            for line in idx_text.splitlines():
                if "Captured" in line and ":" in line:
                    captured = line.split(":", 1)[1].strip().strip("*").strip()
                elif "Version" in line and ":" in line:
                    version = line.split(":", 1)[1].strip().strip("*").strip()

        # Leer live.json si existe (metadata rápida)
        if self._live_path.exists():
            try:
                live = json.loads(self._live_path.read_text(encoding="utf-8", errors="replace"))
                if not captured and "captured" in live:
                    captured = live["captured"]
                if not version and "version" in live:
                    version = live["version"]
            except Exception:
                pass

        # Leer cada manifest
        for mf_path in sorted(self._manifests_dir.glob("*.json")):
            try:
                data = json.loads(mf_path.read_text(encoding="utf-8", errors="replace"))
                area = GaboArea(
                    area=data.get("area", mf_path.stem),
                    root_rel=data.get("root_rel", ""),
                    exists=data.get("exists", True),
                    broken=data.get("broken", False),
                    file_count=data.get("file_count", 0),
                    files=data.get("files", []),
                )
                areas.append(area)
                total_files += area.file_count
                if area.broken:
                    broken.append(area.area)
            except Exception:
                continue

        self._snapshot = GaboSnapshot(
            captured=captured,
            workspace_root=str(self.workspace_root),
            version=version,
            areas=areas,
            total_files=total_files,
            broken_areas=broken,
        )
        return self._snapshot

    def get_snapshot(self) -> GaboSnapshot:
        """Retorna el snapshot cacheado o lo carga si no existe."""
        if self._snapshot is None:
            self.load()
        return self._snapshot or GaboSnapshot()

    def get_prompt_block(self, max_chars: int = 1200) -> str:
        """Shortcut: snapshot → prompt block inyectable."""
        snap = self.get_snapshot()
        return snap.to_prompt_block(max_chars=max_chars)

    def get_area_files(self, area_name: str) -> list[str]:
        """Retorna los archivos de un área específica."""
        snap = self.get_snapshot()
        for area in snap.areas:
            if area.area == area_name:
                return area.files
        return []

    def verify_file_exists(self, area_name: str, filename: str) -> bool:
        """Verifica si un archivo existe en un área según el manifest."""
        files = self.get_area_files(area_name)
        return filename in files


def _run_tests() -> int:
    """Tests inline."""
    # Test 1: Sin .gabo/ → snapshot vacío
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        conn = GaboConnector(td)
        assert not conn.is_available
        snap = conn.load()
        assert not snap.is_available
        assert snap.to_prompt_block() == ""
        print("  ✓ empty workspace → empty snapshot")

    # Test 2: Con .gabo/ real (BAG4.8)
    root = Path(__file__).resolve().parents[2]  # .bago/core → .bago → BAG4.8
    # En runtime real, workspace_root es BAG4.8
    # Pero este archivo está en .bago/core/, parents[2] = BAG4.8
    conn = GaboConnector(root)
    if conn.is_available:
        snap = conn.load()
        assert snap.is_available
        assert len(snap.areas) > 0
        assert snap.total_files > 0
        block = snap.to_prompt_block()
        assert "GABO CONTEXT SEED" in block
        assert snap.version  # Debe tener versión
        print(f"  ✓ BAG4.8 .gabo/ loaded: {len(snap.areas)} areas, {snap.total_files} files, v{snap.version}")

        # Test 3: get_area_files
        core_files = conn.get_area_files("core")
        assert "session_manager.py" in core_files
        print(f"  ✓ get_area_files('core'): {len(core_files)} files")

        # Test 4: verify_file_exists
        assert conn.verify_file_exists("core", "session_manager.py")
        assert not conn.verify_file_exists("core", "nonexistent.py")
        print("  ✓ verify_file_exists")

        # Test 5: prompt block truncation
        short_block = snap.to_prompt_block(max_chars=100)
        assert len(short_block) <= 103  # 100 + "..."
        print(f"  ✓ prompt block truncation: {len(short_block)} chars")
    else:
        print("  ⚠ BAG4.8 .gabo/ not found — skipping integration tests")

    print("gabo_connector.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())