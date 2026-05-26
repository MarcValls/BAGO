#!/usr/bin/env python3
"""
agent_static_guard.py — Guardián de la separación estático/dinámico en BAGO.

Principio ShepardCycle:
  Los agentes con función estática en espiral (el motor) NO se modifican
  durante la sesión. Son la definición invariante de cada rol.

  Los agentes estáticos LEEN su configuración una vez y escriben sus
  resultados en archivos DINÁMICOS (.bago/state/agents/) — nunca en su
  propio directorio (.bago/agents/).

Mapa de directorios:
  .bago/agents/           ← ESTÁTICO  (read-only durante la sesión)
    MAESTRO_BAGO.md       ← motor del rol MAESTRO
    ANALISTA_Contexto.md  ← motor del rol ANALISTA
    agent_factory.py      ← herramienta (código del motor)
    agent_gateway.py      ← herramienta (código del motor)
    *.py (análisis)       ← herramientas de análisis (motor)

  .bago/state/agents/     ← DINÁMICO  (escritura libre durante la sesión)
    manifest.json         ← registro de agentes creados en runtime
    <name>.py             ← agentes generados por factory

API:
  from agent_static_guard import guard

  guard.is_static(path)          → bool
  guard.assert_writable(path)    → lanza AgentWriteError si estático
  guard.dynamic_path(name)       → Path al archivo dinámico del agente
  guard.dynamic_manifest()       → Path al manifest dinámico
  guard.load_manifest()          → dict con el manifest dinámico
  guard.save_manifest(data)      → escribe el manifest dinámico
  guard.dynamic_agents()         → list[str] nombres de agentes dinámicos
  guard.all_agents()             → list[str] todos los agentes (static + dynamic)
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import sys
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE        = Path(__file__).resolve().parent      # .bago/tools/
_BAGO        = _HERE.parent                         # .bago/
_STATIC_DIR  = _BAGO / "agents"                     # motor estático
_DYNAMIC_DIR = _BAGO / "state" / "agents"           # outputs dinámicos
_MANIFEST    = _DYNAMIC_DIR / "manifest.json"       # único manifest


class AgentWriteError(PermissionError):
    """Se lanza al intentar escribir en el directorio estático del motor."""


# ── Extensiones que definen el motor (nunca se generan dinámicamente) ─────────
_STATIC_EXTS = {".md", ".json"}   # personas + contratos

# ── Archivos Python que SON parte del motor (no agentes generados) ────────────
_MOTOR_PY_FILES = {
    "agent_factory.py",
    "agent_gateway.py",
    "duplication_finder.py",
    "logic_checker.py",
    "security_analyzer.py",
    "smell_detector.py",
    "__init__.py",
}


class _StaticGuard:
    """
    Guardián de la inmutabilidad del motor BAGO.

    Instancia global: `guard` (importar directamente).
    """

    def __init__(self) -> None:
        _DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)

    # ── Clasificación ─────────────────────────────────────────────────────────

    def is_static(self, path: str | Path) -> bool:
        """
        Devuelve True si el path pertenece al motor estático.

        Un archivo es estático si:
          - está dentro de _STATIC_DIR, Y
          - es .md / .json  (personas, contratos), O
          - es uno de los .py del motor (_MOTOR_PY_FILES)
        """
        p = Path(path).resolve()
        if _STATIC_DIR not in p.parents and p.parent != _STATIC_DIR:
            return False
        # .md y .json siempre estáticos dentro del motor
        if p.suffix in _STATIC_EXTS:
            return True
        # .py: solo los del motor, NO los agentes generados
        if p.suffix == ".py" and p.name in _MOTOR_PY_FILES:
            return True
        return False

    def is_dynamic(self, path: str | Path) -> bool:
        """Devuelve True si el path es un archivo dinámico legítimo."""
        p = Path(path).resolve()
        return _DYNAMIC_DIR in p.parents or p.parent == _DYNAMIC_DIR

    def assert_writable(self, path: str | Path, *, operation: str = "write") -> None:
        """
        Lanza AgentWriteError si el path es estático.

        Usar antes de cualquier operación de escritura sobre agentes.
        """
        if self.is_static(path):
            raise AgentWriteError(
                f"[AgentStaticGuard] {operation} bloqueado: '{path}' pertenece al "
                f"motor estático de BAGO (.bago/agents/). "
                f"Escribe en el directorio dinámico: {_DYNAMIC_DIR}"
            )

    # ── Rutas dinámicas ───────────────────────────────────────────────────────

    def dynamic_path(self, name: str) -> Path:
        """Devuelve la ruta dinámica para un agente generado en runtime."""
        safe_name = name.replace("/", "_").replace("..", "_")
        if not safe_name.endswith(".py"):
            safe_name = f"{safe_name}.py"
        return _DYNAMIC_DIR / safe_name

    def dynamic_manifest(self) -> Path:
        """Ruta canónica del manifest dinámico."""
        return _MANIFEST

    # ── Manifest ──────────────────────────────────────────────────────────────

    def load_manifest(self) -> dict:
        """Carga el manifest dinámico. Devuelve dict vacío si no existe."""
        if _MANIFEST.exists():
            try:
                return json.loads(_MANIFEST.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"agents": {}}

    def save_manifest(self, data: dict) -> None:
        """Persiste el manifest dinámico (en state/agents/, nunca en agents/)."""
        _DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
        _MANIFEST.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Inventario ────────────────────────────────────────────────────────────

    def dynamic_agents(self) -> list[str]:
        """Nombres de agentes generados dinámicamente (en state/agents/)."""
        if not _DYNAMIC_DIR.exists():
            return []
        return [
            p.stem
            for p in _DYNAMIC_DIR.iterdir()
            if p.suffix == ".py" and not p.name.startswith("_")
        ]

    def static_roles(self) -> list[str]:
        """Nombres de roles estáticos (las .md del motor)."""
        if not _STATIC_DIR.exists():
            return []
        return [p.stem for p in _STATIC_DIR.iterdir() if p.suffix == ".md"]

    def all_agents(self) -> list[str]:
        """Todos los agentes: roles estáticos + agentes dinámicos."""
        return self.static_roles() + self.dynamic_agents()

    # ── Diagnóstico ───────────────────────────────────────────────────────────

    def audit(self) -> dict:
        """
        Audita el estado de la separación estático/dinámico.

        Devuelve:
          - contaminated: archivos generados encontrados en el directorio estático
          - dynamic_count: agentes en el directorio dinámico
          - manifest_ok: el manifest está en el lugar correcto
        """
        contaminated: list[str] = []
        for p in _STATIC_DIR.iterdir():
            if (
                p.suffix == ".py"
                and p.name not in _MOTOR_PY_FILES
                and not p.name.startswith("_")
            ):
                contaminated.append(str(p))

        return {
            "contaminated": contaminated,
            "dynamic_count": len(self.dynamic_agents()),
            "static_roles": len(self.static_roles()),
            "manifest_ok": _MANIFEST.exists(),
            "manifest_path": str(_MANIFEST),
            "old_manifest_exists": (_STATIC_DIR / "manifest.json").exists(),
        }

    def fix_contamination(self, *, dry_run: bool = False) -> list[str]:
        """
        Mueve agentes dinámicos que están en el directorio estático a state/agents/.

        Retorna lista de archivos movidos (o que se moverían en dry_run).
        """
        audit = self.audit()
        moved: list[str] = []
        for src_str in audit["contaminated"]:
            src = Path(src_str)
            dst = _DYNAMIC_DIR / src.name
            if not dry_run:
                _DYNAMIC_DIR.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                src.unlink()
            moved.append(src.name)
        return moved


# ── Singleton global ──────────────────────────────────────────────────────────
guard: _StaticGuard = _StaticGuard()


# ── CLI / diagnóstico ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="BAGO Agent Static Guard — audita la separación motor/dinámico"
    )
    parser.add_argument("--audit",   action="store_true", help="audita la contaminación")
    parser.add_argument("--fix",     action="store_true", help="mueve agentes dinámicos al dir correcto")
    parser.add_argument("--dry-run", action="store_true", help="simula el fix sin escribir")
    parser.add_argument("--list",    action="store_true", help="lista todos los agentes")
    args = parser.parse_args()

    # Importar presencia si disponible
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("bago_presence", _HERE / "bago_presence.py")
        _mod  = _ilu.module_from_spec(_spec)  # type: ignore
        _spec.loader.exec_module(_mod)          # type: ignore
        bp = _mod.bp
    except Exception:
        class _NullBP:
            def __getattr__(self, _): return lambda *a, **k: None
        bp = _NullBP()  # type: ignore

    if args.list:
        bp.act("MAESTRO", "inventario de agentes BAGO")
        print("\n  Roles estáticos (motor):")
        for r in sorted(guard.static_roles()):
            print(f"    ◆  {r}")
        print("\n  Agentes dinámicos (runtime):")
        dynamic = guard.dynamic_agents()
        if dynamic:
            for d in sorted(dynamic):
                print(f"    ◈  {d}")
        else:
            print("    (ninguno todavía)")
        print()
        sys.exit(0)

    result = guard.audit()
    bp.act("AUDITOR_CANONICO", "auditando separación estático/dinámico")
    bp.status_line("Motor estático (.md)", str(result["static_roles"]))
    bp.status_line("Agentes dinámicos", str(result["dynamic_count"]))
    bp.status_line("Manifest correcto", "sí" if result["manifest_ok"] else "NO", ok=result["manifest_ok"])
    if result["old_manifest_exists"]:
        bp.status_line("manifest en agents/", "CONTAMINADO ⚠", ok=False)

    if result["contaminated"]:
        bp.think(f"{len(result['contaminated'])} archivo(s) dinámico(s) en directorio estático:")
        for f in result["contaminated"]:
            print(f"    ⚠  {f}")
        if args.fix:
            moved = guard.fix_contamination(dry_run=args.dry_run)
            for name in moved:
                prefix = "[dry-run] " if args.dry_run else ""
                bp.act("ORGANIZADOR", f"{prefix}movido → state/agents/{name}")
    else:
        bp.act("AUDITOR_CANONICO", "motor limpio — ningún agente dinámico en directorio estático")
    print()
