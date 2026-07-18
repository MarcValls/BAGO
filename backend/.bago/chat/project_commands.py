from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

# CANON[PRJ-001]: /project is the canonical binding surface for project/workspace state.
# CANON[PRJ-002]: analyze/status/init/link all rebind through SessionManager before reporting.
# LEGACY[PRJ-L001]: load_tool_module and parse_project_args stay local for direct file imports.
from command_utils import load_tool_module, parse_project_args


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve().samefile(right.resolve())
    except Exception:
        try:
            return left.resolve() == right.resolve()
        except Exception:
            return str(left).lower() == str(right).lower()


def cmd_project(mgr: Any, engine: Any, args: list[str], *, load_module=load_tool_module) -> dict:
    mod = load_module("project_memory", "project_memory.py")
    action, root = parse_project_args(args)
    project_root = None
    if root:
        project_root = mod.resolve_project_root(root, allow_fallback_cwd=False)
    else:
        project_root = Path(getattr(mgr, "project_root", getattr(mgr, "base_path", Path.cwd()))).expanduser().resolve()
    if project_root is None:
        return {
            "ok": False,
            "message": "No hay proyecto activo. Usa /project <analyze|status|init|link|seed|sync> <ruta>.",
        }

    if action == "sync" and root:
        return {"ok": False, "message": "Uso: /project sync (sin ruta)."}

    current_root_value = getattr(mgr, "project_root", getattr(mgr, "base_path", None))
    has_current_root = current_root_value is not None
    current_root = Path(current_root_value if current_root_value is not None else project_root).expanduser().resolve()

    if action != "sync" and hasattr(mgr, "rebind_project_root"):
        should_rebind = (not root) or (not has_current_root) or (not _same_path(project_root, current_root))
        if should_rebind:
            try:
                mgr.rebind_project_root(project_root)
            except Exception as exc:
                return {"ok": False, "message": f"No se pudo activar el proyecto {project_root}: {exc}"}

    if action == "init":
        report = mod.init_project(project_root)
        message = (
            f"Initialized project memory at: {report['bago_dir']}\n"
            f"Created directories: {len(report['created_dirs'])}\n"
            f"Created files: {len(report['created_files'])}"
        )
        return {"ok": True, "message": message, "data": report}
    if action == "status":
        data = mod.status_data(project_root)
        return {"ok": True, "message": mod.format_status(data), "data": data}
    if action == "link":
        data = mod.link_project(project_root)
        message = (
            f"Linked project memory at: {data['root']}\n"
            f"Link mode: {data['link_mode']}\n"
            f"Marker: {data['marker']}"
        )
        return {"ok": True, "message": message, "data": data}
    if action == "analyze":
        data = mod.analyze_data(project_root)
        if hasattr(mgr, "record_project_analysis"):
            mgr.record_project_analysis(data)
        return {"ok": True, "message": mod.format_analysis(data), "data": data}
    if action == "seed":
        report = mod.seed_project(project_root, depth=3, ref=None)
        message = (
            f"Seeded workspace at: {report['root']}\n"
            f"Tree files: {report['tree']['count']}\n"
            f"Files indexed: {report['meta']['files_indexed']}\n"
            f"Symbols indexed: {report['meta']['symbols_indexed']}\n"
            f"Working set size: {report['meta']['working_set_size']}"
        )
        return {"ok": True, "message": message, "data": report}
    if action == "sync":
        if not hasattr(mgr, "sync_workspace_mirror"):
            return {"ok": False, "message": "La sesión no expone sync_workspace_mirror()."}
        data = mgr.sync_workspace_mirror()
        return {"ok": bool(data.get("ok")), "message": data.get("message", "Sincronización completada"), "data": data}
    return {"ok": False, "message": "Uso: /project [analyze|status|init|link|seed|sync] [ruta|depth]"}
