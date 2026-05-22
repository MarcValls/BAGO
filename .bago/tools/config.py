#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified config tool for BAGO.

Usage:
  python config.py                 -> run config checks
  python config.py check [--list|--test]
  python config.py show [--json|--short|--section NAME]
  python config.py wizard [--show|--reset]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
TOOLS = ROOT / ".bago" / "tools"
CONFIG_DIR = STATE / "config"
CONFIG_FILE = STATE / "bago_config.json"
GLOBAL_STATE = STATE / "global_state.json"


def BOLD(s: str) -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str) -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str) -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def RED(s: str) -> str: return f"\033[31m{s}\033[0m"
def CYAN(s: str) -> str: return f"\033[36m{s}\033[0m"


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ── config_check.py ──────────────────────────────────────────────────────────
SCHEMAS: dict[str, list[str]] = {
    "ideas_catalog.json": ["version", "ideas"],
    "intents_catalog.json": ["version", "intents"],
    "sincerity_lexicon.json": ["version"],
    "scan_config.json": ["version", "todo_patterns"],
    "validation_patterns.json": ["version", "secret_patterns"],
    "efficiency_weights.json": ["version", "weights"],
    "preflight_rules.json": ["version", "role_map"],
    "tool_catalog.json": ["version", "tools"],
    "workflow_guidance.json": ["version", "workflows"],
    "contracts_config.json": ["version", "checkers"],
}

CONSUMERS: dict[str, str] = {
    "ideas_catalog.json": "emit_ideas.py",
    "intents_catalog.json": "intent_router.py",
    "sincerity_lexicon.json": "sincerity_detector.py",
    "scan_config.json": "todo_scan.py",
    "validation_patterns.json": "commit_readiness.py",
    "efficiency_weights.json": "efficiency_meter.py",
    "preflight_rules.json": "session_preflight.py",
    "tool_catalog.json": "tool_search.py",
    "workflow_guidance.json": "inspect_workflow.py",
    "contracts_config.json": "contracts.py",
}


def check_parseable(cfg_path: Path) -> list[dict]:
    issues = []
    try:
        json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append({"code": "CFG-E001", "file": cfg_path.name, "msg": f"JSON inválido: {exc}"})
    except Exception as exc:
        issues.append({"code": "CFG-E001", "file": cfg_path.name, "msg": f"Error de lectura: {exc}"})
    return issues


def check_schema(cfg_path: Path) -> list[dict]:
    required = SCHEMAS.get(cfg_path.name, ["version"])
    data = _load_json(cfg_path, None)
    if not isinstance(data, dict):
        return []
    return [
        {"code": "CFG-E002", "file": cfg_path.name, "msg": f"clave requerida ausente: '{key}'"}
        for key in required
        if key not in data
    ]


def check_tool_catalog_vs_registry() -> list[dict]:
    catalog_path = CONFIG_DIR / "tool_catalog.json"
    registry_path = TOOLS / "tool_registry.py"
    if not catalog_path.exists() or not registry_path.exists():
        return []
    catalog_data = _load_json(catalog_path, {})
    catalog_cmds = {t["command"] for t in catalog_data.get("tools", []) if isinstance(t, dict) and "command" in t}
    registry_text = registry_path.read_text(encoding="utf-8")
    issues = []
    for cmd in catalog_cmds & {"tool-guardian", "auto-register", "doctor"}:
        cmd_normalized = cmd.replace("-", "_")
        if not any(token in registry_text for token in (f'"{cmd}"', f"'{cmd}'", f'"{cmd_normalized}"', f"'{cmd_normalized}'")):
            issues.append({"code": "CFG-W001", "file": "tool_catalog.json", "msg": f"comando crítico '{cmd}' no encontrado en tool_registry.py"})
    return issues


def check_consumers() -> list[dict]:
    return [
        {"code": "CFG-W002", "file": cfg_name, "msg": f"consumidor '{script_name}' no encontrado en tools/"}
        for cfg_name, script_name in CONSUMERS.items()
        if (CONFIG_DIR / cfg_name).exists() and not (TOOLS / script_name).exists()
    ]


def check_orphan_configs() -> list[dict]:
    known = set(SCHEMAS)
    return [
        {"code": "CFG-W002", "file": cfg_path.name, "msg": "config sin esquema conocido (no validada)"}
        for cfg_path in sorted(CONFIG_DIR.glob("*.json"))
        if cfg_path.name not in known
    ]


def run_all() -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    warnings: list[dict] = []
    if not CONFIG_DIR.exists():
        errors.append({"code": "CFG-E001", "file": "state/config/", "msg": "directorio de configs no existe"})
        return errors, warnings
    for cfg_path in sorted(CONFIG_DIR.glob("*.json")):
        errors.extend(check_parseable(cfg_path))
        errors.extend(check_schema(cfg_path))
    warnings.extend(check_tool_catalog_vs_registry())
    warnings.extend(check_consumers())
    warnings.extend(check_orphan_configs())
    return errors, warnings


def print_results(errors: list[dict], warnings: list[dict]) -> None:
    n_configs = len(list(CONFIG_DIR.glob("*.json"))) if CONFIG_DIR.exists() else 0
    if not errors and not warnings:
        print(f"  ✅  {n_configs} configs OK — sin errores ni advertencias")
        return
    if errors:
        print(f"  ERRORES ({len(errors)}):")
        for item in errors:
            print(f"    [{item['code']}] {item['file']}: {item['msg']}")
    if warnings:
        if errors:
            print()
        print(f"  ADVERTENCIAS ({len(warnings)}):")
        for item in warnings:
            print(f"    [{item['code']}] {item['file']}: {item['msg']}")
    print(f"\n  {n_configs} configs auditadas — {len(errors)} errores, {len(warnings)} advertencias")


def cmd_list() -> None:
    if not CONFIG_DIR.exists():
        print("  (directorio de configs no existe)")
        return
    configs = sorted(CONFIG_DIR.glob("*.json"))
    print(f"\n  Configs en state/config/ ({len(configs)} archivos)\n")
    for cfg in configs:
        consumer = CONSUMERS.get(cfg.name, "—")
        data = _load_json(cfg, None)
        if isinstance(data, dict):
            print(f"  {cfg.name:<35}  v{data.get('version', '?')}  {len(data):3d} claves  →  {consumer}")
        else:
            print(f"  {cfg.name:<35}  [INVALID JSON]  →  {consumer}")
    print()


def check_main(argv: list[str]) -> int:
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    if "--test" in argv:
        return _self_test()
    if "--list" in argv:
        cmd_list()
        return 0
    errors, warnings = run_all()
    print_results(errors, warnings)
    return 1 if errors else 0


# ── config_show.py ───────────────────────────────────────────────────────────

def section_project() -> dict:
    gs = _load_json(STATE / "global_state.json", {})
    proj = gs.get("active_project", {}) if isinstance(gs, dict) else {}
    if not gs:
        return {"error": "global_state.json no encontrado"}
    return {
        "name": proj.get("name", "?"),
        "path": proj.get("path", "?"),
        "session_id": gs.get("session_id", "?"),
        "started_at": gs.get("started_at", "?"),
        "bago_version": gs.get("version", "?"),
    }


def section_ideas() -> dict:
    impl = _load_json(STATE / "implemented_ideas.json", {})
    items = impl.get("implemented", []) if isinstance(impl, dict) else []
    last = items[0] if items else None
    return {
        "total": len(items),
        "updated": impl.get("updated_at", "?") if isinstance(impl, dict) else "?",
        "last": last.get("title", "?") if last else None,
        "last_at": last.get("done_at", "?") if last else None,
    }


def section_tools() -> dict:
    base_files = {"tool_registry.py", "bago_core.py", "__init__.py", "db_init.py", "idea_gen.py", "validate.py"}
    tool_files = [f for f in TOOLS.glob("*.py") if f.name not in base_files]
    return {"tool_files": len(tool_files), "tool_names": sorted(f.stem for f in tool_files)}


def section_db() -> dict:
    db_path = STATE / "bago.db"
    if not db_path.exists():
        return {"exists": False}
    return {"exists": True, "path": str(db_path), "size_kb": db_path.stat().st_size // 1024}


def section_snapshots() -> dict:
    snap_dir = ROOT / ".bago" / "snapshots"
    snaps = sorted(snap_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if snap_dir.exists() else []
    return {"count": len(snaps), "latest": snaps[0].name if snaps else None, "total_kb": sum(s.stat().st_size // 1024 for s in snaps)}


def section_task() -> dict:
    task_file = STATE / "pending_w2_task.json"
    data = _load_json(task_file, {}) if task_file.exists() else {}
    if not isinstance(data, dict) or not data:
        return {"active": False}
    return {
        "active": True,
        "title": data.get("idea_title", data.get("title", "?")),
        "priority": data.get("priority", "?"),
        "slot": data.get("idea_index", data.get("slot", "?")),
    }


def show_main(argv: list[str]) -> int:
    as_json = "--json" in argv
    short = "--short" in argv
    section = None
    if "--section" in argv:
        idx = argv.index("--section")
        if idx + 1 < len(argv):
            section = argv[idx + 1]
    info = {
        "project": section_project(),
        "ideas": section_ideas(),
        "tools": section_tools(),
        "db": section_db(),
        "snapshots": section_snapshots(),
        "task": section_task(),
    }
    if section in info:
        info = {section: info[section]}
    if as_json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Configuración                                       │")
    print("  └─────────────────────────────────────────────────────────────┘")
    project = info.get("project", {})
    print(f"  {BOLD('Proyecto activo:')}")
    print(f"    Nombre:     {CYAN(project.get('name', '?'))}")
    print(f"    Ruta:       {DIM(project.get('path', '?'))}")
    session_id = str(project.get('session_id', '?'))
    print(f"    Session:    {DIM(session_id[:20] + '...' if len(session_id) > 20 else session_id)}\n")
    task = info.get("task", {})
    if task.get("active"):
        _priority = task.get('priority', '')
        print(f"  {BOLD('Tarea activa:')}  {YELLOW(task['title'])}  {DIM(f'(prioridad {_priority})')}")
    else:
        print(f"  {BOLD('Tarea activa:')}  {DIM('ninguna')}")
    print()
    ideas = info.get("ideas", {})
    print(f"  {BOLD('Ideas implementadas:')}  {GREEN(str(ideas.get('total', 0)))}")
    if ideas.get("last"):
        print(f"    Última:   {DIM(ideas['last'])}")
    print()
    tools = info.get("tools", {})
    names = tools.get("tool_names", [])
    print(f"  {BOLD('Herramientas registradas:')}  {len(names)}")
    if not short:
        for idx in range(0, len(names), 5):
            print(f"    {DIM('  '.join(names[idx:idx + 5]))}")
    print()
    db = info.get("db", {})
    if db.get("exists"):
        print(f"  {BOLD('Base de datos:')}  {GREEN('✅')} {DIM(str(db['size_kb']) + 'KB')}  {DIM(db.get('path', ''))}")
    else:
        print(f"  {BOLD('Base de datos:')}  {RED('✗ no encontrada')}")
    print()
    snaps = info.get("snapshots", {})
    print(f"  {BOLD('Snapshots:')}")
    if snaps.get("count", 0):
        print(f"    {GREEN(str(snaps['count']))} disponibles  |  Último: {DIM(snaps.get('latest', '?'))}  |  Total: {DIM(str(snaps.get('total_kb', 0)) + 'KB')}")
    else:
        print(f"    {YELLOW('ninguno')}  —  Usa: bago snapshot")
    print()
    return 0


# ── config_wizard.py ─────────────────────────────────────────────────────────
DEFAULTS: dict = {
    "project_path": "",
    "banner": {"enabled": True, "show_next_idea": True, "show_health": True, "show_task_alert": True},
    "notifications": {"task_overdue_hours": 2, "priority_decay_days": 7},
    "ideas": {"min_ideas": 5, "max_ideas": 20, "auto_replenish": True},
    "ui": {"encoding": "utf-8", "color": True},
}


def _load_config() -> dict:
    data = _load_json(CONFIG_FILE, None)
    return data if isinstance(data, dict) else dict(DEFAULTS)


def _save_config(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_project_from_global() -> str:
    gs = _load_json(GLOBAL_STATE, {})
    return gs.get("active_project", {}).get("path", "") if isinstance(gs, dict) else ""


def _prompt(question: str, default: str) -> str:
    default_str = f" [{DIM(default)}]" if default else ""
    try:
        answer = input(f"  {CYAN('?')} {question}{default_str}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer or default


def _prompt_bool(question: str, default: bool) -> bool:
    default_str = "S/n" if default else "s/N"
    try:
        answer = input(f"  {CYAN('?')} {question} [{DIM(default_str)}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return default if not answer else answer in ("s", "si", "sí", "y", "yes", "1", "true")


def _prompt_int(question: str, default: int) -> int:
    try:
        raw = input(f"  {CYAN('?')} {question} [{DIM(str(default))}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _show_config(cfg: dict) -> None:
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Configuración actual                                │")
    print("  └─────────────────────────────────────────────────────────────┘\n")
    print(f"  Ruta del proyecto       : {cfg.get('project_path', '') or DIM('(no configurada)')}")
    banner = cfg.get("banner", {})
    print(f"  Banner habilitado       : {'✅' if banner.get('enabled', True) else '❌'}")
    print(f"    Mostrar siguiente idea: {'✅' if banner.get('show_next_idea', True) else '❌'}")
    print(f"    Mostrar health score  : {'✅' if banner.get('show_health', True) else '❌'}")
    print(f"    Alerta tarea activa   : {'✅' if banner.get('show_task_alert', True) else '❌'}")
    notif = cfg.get("notifications", {})
    print(f"  Alerta overdue (horas)  : {notif.get('task_overdue_hours', 2)}")
    print(f"  Decaimiento prioridad   : cada {notif.get('priority_decay_days', 7)} días")
    ideas_cfg = cfg.get("ideas", {})
    print(f"  Ideas min/max           : {ideas_cfg.get('min_ideas', 5)} / {ideas_cfg.get('max_ideas', 20)}")
    print(f"  Auto-rellenar ideas     : {'✅' if ideas_cfg.get('auto_replenish', True) else '❌'}")
    print(f"  Color en terminal       : {'✅' if cfg.get('ui', {}).get('color', True) else '❌'}")
    print(f"\n  Guardada en: {DIM(str(CONFIG_FILE))}\n")


def _run_wizard(cfg: dict) -> dict:
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Configuración guiada                                │")
    print("  └─────────────────────────────────────────────────────────────┘\n")
    print(f"  {DIM('Presiona Enter para aceptar el valor por defecto.')}\n")
    current_path = cfg.get("project_path", "") or _load_project_from_global()
    print(f"  {BOLD('── Proyecto ──')}")
    cfg["project_path"] = _prompt("Ruta absoluta del proyecto", current_path)
    print(f"\n  {BOLD('── Banner ──')}")
    banner = cfg.get("banner", DEFAULTS["banner"].copy())
    banner["enabled"] = _prompt_bool("Mostrar banner al arrancar BAGO", banner.get("enabled", True))
    if banner["enabled"]:
        banner["show_next_idea"] = _prompt_bool("  Mostrar siguiente idea en el banner", banner.get("show_next_idea", True))
        banner["show_health"] = _prompt_bool("  Mostrar health score en el banner", banner.get("show_health", True))
        banner["show_task_alert"] = _prompt_bool("  Mostrar alerta de tarea activa", banner.get("show_task_alert", True))
    cfg["banner"] = banner
    print(f"\n  {BOLD('── Alertas ──')}")
    notif = cfg.get("notifications", DEFAULTS["notifications"].copy())
    notif["task_overdue_hours"] = _prompt_int("Horas hasta alerta de tarea activa demasiado larga", notif.get("task_overdue_hours", 2))
    notif["priority_decay_days"] = _prompt_int("Días sin implementar para aplicar decaimiento de prioridad", notif.get("priority_decay_days", 7))
    cfg["notifications"] = notif
    print(f"\n  {BOLD('── Ideas ──')}")
    ideas_cfg = cfg.get("ideas", DEFAULTS["ideas"].copy())
    ideas_cfg["min_ideas"] = _prompt_int("Número mínimo de ideas en el selector", ideas_cfg.get("min_ideas", 5))
    ideas_cfg["max_ideas"] = _prompt_int("Número máximo de ideas en el selector", ideas_cfg.get("max_ideas", 20))
    ideas_cfg["auto_replenish"] = _prompt_bool("Rellenar automáticamente si hay pocas ideas", ideas_cfg.get("auto_replenish", True))
    cfg["ideas"] = ideas_cfg
    print(f"\n  {BOLD('── Interfaz ──')}")
    ui = cfg.get("ui", DEFAULTS["ui"].copy())
    ui["color"] = _prompt_bool("Usar colores en la terminal", ui.get("color", True))
    cfg["ui"] = ui
    print()
    return cfg


def wizard_main(argv: list[str]) -> int:
    if "--reset" in argv:
        _save_config(dict(DEFAULTS))
        print(f"\n  {GREEN('✅  Configuración restaurada a valores por defecto.')}\n  {DIM(str(CONFIG_FILE))}\n")
        return 0
    cfg = _load_config()
    if "--show" in argv:
        _show_config(cfg)
        return 0
    try:
        cfg = _run_wizard(cfg)
    except KeyboardInterrupt:
        print(f"\n  {YELLOW('⚠  Configuración cancelada.')}\n")
        return 0
    _save_config(cfg)
    print(f"  {GREEN('✅  Configuración guardada.')}\n  {DIM(str(CONFIG_FILE))}\n")
    _show_config(cfg)
    return 0


def _self_test() -> int:
    assert "ideas" in DEFAULTS
    assert isinstance(section_tools(), dict)
    print("  2/2 tests pasaron")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return check_main([])
    if args[0] == "check":
        return check_main(args[1:])
    if args[0] == "show":
        return show_main(args[1:])
    if args[0] == "wizard":
        return wizard_main(args[1:])
    if args[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    return check_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
