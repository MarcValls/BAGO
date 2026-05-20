from pathlib import Path
import sys

# ── PATCH 1: cmd.py — fallback genérico para cualquier comando registrado ──
cmd_path = Path(".bago/tools/bago/cmd.py")
cmd_txt = cmd_path.read_text(encoding="utf-8")

# Find the "else:" block that handles unknown commands
old_else = '''        else:
            pe(f"Desconocido: {v}  —  /help")
    return True'''

new_else = '''        else:
            # ── Fallback: intentar ejecutar como comando BAGO registrado ──────────
            _ran = _run_bago_cmd(v.lstrip("/"), a)
            if _ran:
                return True
            pe(f"Desconocido: {v}  —  /help")
    return True'''

if old_else in cmd_txt:
    cmd_txt = cmd_txt.replace(old_else, new_else)
else:
    print("WARN: old_else pattern not found in cmd.py")

# Add import for tool_registry and helper near top
# Find the imports block end
import_idx = cmd_txt.find("from .ui import console, pe, pi")
if import_idx > 0:
    # Insert after the ui import line
    end_line = cmd_txt.find("\n", import_idx)
    insert_pos = end_line + 1
    helper_block = """

# ── Generic BAGO command runner (fallback for any /cmd not handled above) ──
def _run_bago_cmd(cmd: str, args: str) -> bool:
    import subprocess
    from pathlib import Path
    bago_script = Path(__file__).resolve().parents[3] / "bago"
    if not bago_script.exists():
        return False
    # Try to resolve via tool_registry
    reg_path = Path(__file__).resolve().parents[2] / "tool_registry.py"
    if reg_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("_tr", str(reg_path))
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(reg_path.parent))
            spec.loader.exec_module(mod)
            registry = getattr(mod, "REGISTRY", {})
            if cmd not in registry:
                return False
        except Exception:
            pass
    full_args = [cmd] + (args.split() if args else [])
    pi(f"[dim]Ejecutando: bago {' '.join(full_args)}[/dim]")
    result = subprocess.run(
        [sys.executable, str(bago_script)] + full_args,
        cwd=str(bago_script.parent),
    )
    return result.returncode == 0

"""
    cmd_txt = cmd_txt[:insert_pos] + helper_block + cmd_txt[insert_pos:]
    print("PATCHED cmd.py with fallback runner")
else:
    print("WARN: could not find insert position in cmd.py")

cmd_path.write_text(cmd_txt, encoding="utf-8")


# ── PATCH 2: main_menu.py — add dynamic command picker ──
menu_path = Path(".bago/tools/bago/menus/main_menu.py")
menu_txt = menu_path.read_text(encoding="utf-8")

old_entries = '''    # ── 8 · Utilidades ───────────────────────────────────────────────
    (None,          "  -- Utilidades ---------------------------------"),
    ("/help",       "  Ayuda  -- todos los comandos con descripcion"),
    ("/clear",      "  Limpiar historial de chat"),
]'''

new_entries = '''    # ── 8 · Framework BAGO (todos los comandos) ──────────────────────
    (None,          "  -- Framework BAGO ----------------------------"),
    ("__all_cmds__", "  🎛️  Todos los comandos BAGO...  -- ver lista completa"),

    # ── 9 · Utilidades ───────────────────────────────────────────────
    (None,          "  -- Utilidades ---------------------------------"),
    ("/help",       "  Ayuda  -- todos los comandos con descripcion"),
    ("/clear",      "  Limpiar historial de chat"),
]'''

if old_entries in menu_txt:
    menu_txt = menu_txt.replace(old_entries, new_entries)
else:
    print("WARN: old_entries pattern not found in main_menu.py")

# Update _cmd_main_menu to handle __all_cmds__
old_func = '''def _cmd_main_menu(session) -> str | None:
    """
    Abre el menú principal navegable.
    Devuelve la línea de comando seleccionada (p.ej. '/login')
    o None si el usuario canceló con Esc.
    """
    return _menu_pick(
        "BAGO  /  Menu principal",
        "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
        _ENTRIES,
    )'''

new_func = '''def _all_cmds_menu(session) -> str | None:
    """Picker dinámico con todos los comandos registrados en tool_registry."""
    import sys
    from pathlib import Path
    reg_path = Path(__file__).resolve().parents[2] / "tool_registry.py"
    entries = [("__back__", "  ↩  Volver al menú principal")]
    if reg_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("_tr_menu", str(reg_path))
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(reg_path.parent))
            spec.loader.exec_module(mod)
            registry = getattr(mod, "REGISTRY", {})
            # Group by stability
            groups = {}
            for name, entry in sorted(registry.items()):
                stab = getattr(entry, "stability", "unknown")
                groups.setdefault(stab, []).append(entry)
            for stab in ("core", "dangerous", "experimental", "legacy", "internal"):
                if stab not in groups:
                    continue
                entries.append((None, f"  -- {stab.upper()} ({len(groups[stab])}) ---"))
                for e in sorted(groups[stab], key=lambda x: x.cmd):
                    desc = getattr(e, "description", "")[:50]
                    label = f"  /{e.cmd}  -- {desc}" if desc else f"  /{e.cmd}"
                    entries.append((f"/{e.cmd}", label))
        except Exception:
            pass
    chosen = _menu_pick(
        "BAGO  /  Todos los comandos",
        "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
        entries,
    )
    if chosen == "__back__":
        return None
    return chosen


def _cmd_main_menu(session) -> str | None:
    """
    Abre el menú principal navegable.
    Devuelve la línea de comando seleccionada (p.ej. '/login')
    o None si el usuario canceló con Esc.
    """
    while True:
        selected = _menu_pick(
            "BAGO  /  Menu principal",
            "  ↑↓  navegar    Enter  seleccionar    Esc  volver",
            _ENTRIES,
        )
        if selected == "__all_cmds__":
            sub = _all_cmds_menu(session)
            if sub:
                return sub
            continue
        return selected'''

if old_func in menu_txt:
    menu_txt = menu_txt.replace(old_func, new_func)
else:
    print("WARN: old_func pattern not found in main_menu.py")

menu_path.write_text(menu_txt, encoding="utf-8")
print("PATCHED main_menu.py with dynamic picker")
