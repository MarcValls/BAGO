#!/usr/bin/env python3
"""state_manager.py — API unificada para el estado BAGO.

Abstrae las lecturas y escrituras sobre global_state.json mediante accessors
por sección. Los datos se organizan físicamente en tres ficheros divididos:

  state/health.json         — guardian_findings, last_validation, system_health
  state/sprint.json         — sprint_status, active_workflow, inventory, sessions
  state/knowledge_index.json— knowledge_base, bago_knowledge, knowledge details

global_state.json se mantiene como vista materializada para retrocompatibilidad
con los ~60 tools que lo leen directamente. Cada escritura via este manager
regenera esa vista automáticamente.

Uso:
    python3 state_manager.py --status          # estado de los tres ficheros divididos
    python3 state_manager.py --materialize     # regenera global_state.json desde split
    python3 state_manager.py --split           # divide global_state.json en 3 ficheros
    python3 state_manager.py --read health     # imprime la sección health en JSON
    python3 state_manager.py --read sprint     # imprime la sección sprint en JSON
    python3 state_manager.py --read knowledge  # imprime la sección knowledge en JSON
    python3 state_manager.py --test            # self-tests
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BAGO_ROOT    = Path(__file__).parent.parent          # .bago/
STATE_DIR    = BAGO_ROOT / "state"
GLOBAL_FILE  = STATE_DIR / "global_state.json"
HEALTH_FILE  = STATE_DIR / "health.json"
SPRINT_FILE  = STATE_DIR / "sprint.json"
KNOWLEDGE_FILE = STATE_DIR / "knowledge_index.json"

# ── Sección → claves en global_state.json ─────────────────────────────────────

HEALTH_KEYS    = {"system_health", "last_validation", "guardian_findings"}
SPRINT_KEYS    = {"sprint_status", "inventory", "unresolved", "sync_status",
                  "supervision", "notes"}
KNOWLEDGE_KEYS = {"knowledge_base", "bago_knowledge"}
META_KEYS      = {"bago_version", "updated_at", "last_updated"}


# ── Lectura global ─────────────────────────────────────────────────────────────

def read_state() -> dict[str, Any]:
    """Lee y devuelve global_state.json completo. Fuente de verdad para compatibilidad."""
    if not GLOBAL_FILE.exists():
        return {}
    return json.loads(GLOBAL_FILE.read_text("utf-8"))


# ── Lectura por sección ────────────────────────────────────────────────────────

def read_health() -> dict[str, Any]:
    """Devuelve la sección de salud del sistema."""
    if HEALTH_FILE.exists():
        return json.loads(HEALTH_FILE.read_text("utf-8"))
    state = read_state()
    return {k: state[k] for k in HEALTH_KEYS if k in state}


def read_sprint() -> dict[str, Any]:
    """Devuelve el estado del sprint/sesión activo."""
    if SPRINT_FILE.exists():
        return json.loads(SPRINT_FILE.read_text("utf-8"))
    state = read_state()
    return {k: state[k] for k in SPRINT_KEYS if k in state}


def read_knowledge() -> dict[str, Any]:
    """Devuelve el índice de la knowledge base."""
    if KNOWLEDGE_FILE.exists():
        return json.loads(KNOWLEDGE_FILE.read_text("utf-8"))
    state = read_state()
    return {k: state[k] for k in KNOWLEDGE_KEYS if k in state}


# ── Escritura por sección ──────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_health(data: dict[str, Any], *, materialize: bool = True) -> None:
    """Actualiza la sección health y regenera global_state.json."""
    _write_json(HEALTH_FILE, data)
    if materialize:
        _materialize()


def write_sprint(data: dict[str, Any], *, materialize: bool = True) -> None:
    """Actualiza la sección sprint y regenera global_state.json."""
    _write_json(SPRINT_FILE, data)
    if materialize:
        _materialize()


def write_knowledge(data: dict[str, Any], *, materialize: bool = True) -> None:
    """Actualiza la sección knowledge_index y regenera global_state.json."""
    _write_json(KNOWLEDGE_FILE, data)
    if materialize:
        _materialize()


def write_state(data: dict[str, Any]) -> None:
    """Actualiza global_state.json completo y sincroniza los tres ficheros divididos.
    Método de compatibilidad para tools existentes que escriben el estado completo."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = deepcopy(data)
    data["last_updated"] = ts
    _write_json(GLOBAL_FILE, data)
    _sync_split_from_global(data)


# ── División y materialización ─────────────────────────────────────────────────

def split(state: dict[str, Any] | None = None) -> None:
    """Divide global_state.json en los tres ficheros de sección."""
    if state is None:
        state = read_state()
    if not state:
        print("  state_manager: global_state.json vacío o inexistente", file=sys.stderr)
        return
    _sync_split_from_global(state)
    print(f"  state_manager: dividido en {HEALTH_FILE.name}, {SPRINT_FILE.name}, {KNOWLEDGE_FILE.name}")


def _sync_split_from_global(state: dict[str, Any]) -> None:
    """Actualiza los tres ficheros divididos desde un estado completo."""
    health_data    = {k: state[k] for k in HEALTH_KEYS if k in state}
    sprint_data    = {k: state[k] for k in SPRINT_KEYS if k in state}
    knowledge_data = {k: state[k] for k in KNOWLEDGE_KEYS if k in state}
    if health_data:
        _write_json(HEALTH_FILE, health_data)
    if sprint_data:
        _write_json(SPRINT_FILE, sprint_data)
    if knowledge_data:
        _write_json(KNOWLEDGE_FILE, knowledge_data)


def _materialize() -> None:
    """Regenera global_state.json desde los tres ficheros divididos."""
    existing = read_state()
    merged = deepcopy(existing)

    for section_file, keys in [
        (HEALTH_FILE,    HEALTH_KEYS),
        (SPRINT_FILE,    SPRINT_KEYS),
        (KNOWLEDGE_FILE, KNOWLEDGE_KEYS),
    ]:
        if section_file.exists():
            section = json.loads(section_file.read_text("utf-8"))
            merged.update(section)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    merged["last_updated"] = ts
    _write_json(GLOBAL_FILE, merged)


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    results: list[tuple[str, bool, str]] = []

    # T01 — read_state devuelve un dict
    state = read_state()
    results.append(("T01:read_state_returns_dict", isinstance(state, dict), ""))

    # T02 — read_health incluye system_health cuando está en global
    if state:
        health = read_health()
        results.append(("T02:read_health_dict", isinstance(health, dict), ""))

    # T03 — read_sprint incluye sprint_status cuando está en global
    if state:
        sprint = read_sprint()
        results.append(("T03:read_sprint_dict", isinstance(sprint, dict), ""))

    # T04 — read_knowledge incluye knowledge_base cuando está en global
    if state:
        knowledge = read_knowledge()
        results.append(("T04:read_knowledge_dict", isinstance(knowledge, dict), ""))

    # T05 — split crea los tres ficheros
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        fake_state = {
            "bago_version": "test",
            "system_health": "ok",
            "sprint_status": {"active_workflow": None},
            "knowledge_base": {"initialized": "2026-01-01"},
            "last_validation": {},
            "guardian_findings": {},
        }
        tmp_global = tmp / "global_state.json"
        tmp_health = tmp / "health.json"
        tmp_sprint = tmp / "sprint.json"
        tmp_knowledge = tmp / "knowledge_index.json"
        tmp_global.write_text(json.dumps(fake_state), encoding="utf-8")

        import importlib.util
        spec = importlib.util.spec_from_file_location("_sm_test", __file__)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.GLOBAL_FILE    = tmp_global
        mod.HEALTH_FILE    = tmp_health
        mod.SPRINT_FILE    = tmp_sprint
        mod.KNOWLEDGE_FILE = tmp_knowledge
        mod.STATE_DIR      = tmp

        state_loaded = mod.read_state()
        mod._sync_split_from_global(state_loaded)

        t05_ok = tmp_health.exists() and tmp_sprint.exists() and tmp_knowledge.exists()
        results.append(("T05:split_creates_files", t05_ok, ""))

        # T06 — materialize merges back
        if t05_ok:
            mod._materialize()
            merged = json.loads(tmp_global.read_text("utf-8"))
            t06_ok = "system_health" in merged and "sprint_status" in merged
            results.append(("T06:materialize_merges_back", t06_ok, ""))

        # T07 — health section keys correct
        if tmp_health.exists():
            h = json.loads(tmp_health.read_text("utf-8"))
            t07_ok = "system_health" in h
            results.append(("T07:health_section_keys", t07_ok, ""))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        sym = "✅" if ok else "❌"
        print(f"  {sym}  {name}" + (f": {detail}" if detail else ""))
    print(f"\n  {passed}/{len(results)} pasaron")

    output = {
        "tool": "state_manager",
        "status": "ok" if failed == 0 else "fail",
        "checks": [{"name": n, "passed": ok} for n, ok, _ in results],
    }
    print(json.dumps(output))
    return 0 if failed == 0 else 1


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cmd_status() -> None:
    files = [
        ("global_state.json", GLOBAL_FILE),
        ("health.json",       HEALTH_FILE),
        ("sprint.json",       SPRINT_FILE),
        ("knowledge_index.json", KNOWLEDGE_FILE),
    ]
    print("\n  State manager — ficheros:")
    for name, path in files:
        exists = "✅" if path.exists() else "❌ (no existe)"
        size   = f"{path.stat().st_size:,} bytes" if path.exists() else ""
        print(f"    {name:<25} {exists}  {size}")
    print()


def _cmd_read_section(section: str) -> None:
    readers = {"health": read_health, "sprint": read_sprint, "knowledge": read_knowledge}
    if section not in readers:
        print(f"  Sección desconocida: {section}. Opciones: health, sprint, knowledge",
              file=sys.stderr)
        sys.exit(1)
    data = readers[section]()
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--test" in args:
        sys.exit(_run_tests())

    if "--status" in args:
        _cmd_status()
        sys.exit(0)

    if "--split" in args:
        split()
        sys.exit(0)

    if "--materialize" in args:
        _materialize()
        print("  global_state.json regenerado desde ficheros divididos.")
        sys.exit(0)

    if "--read" in args:
        i = args.index("--read")
        section = args[i + 1] if i + 1 < len(args) else ""
        _cmd_read_section(section)
        sys.exit(0)

    print(__doc__)
    sys.exit(1)
