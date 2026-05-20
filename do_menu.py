import sys
from pathlib import Path

# ── PATCH main_menu.py ───────────────────────────────────────────────────────
menu_path = Path(".bago/tools/bago/menus/main_menu.py")
menu = menu_path.read_text(encoding="utf-8")

# Add __all_cmds__ entry before Utilidades
old = '''    # ── 8 · Utilidades ───────────────────────────────────────────────
    (None,          "  -- Utilidades ---------------------------------"),
    ("/help",       "  Ayuda  -- todos los comandos con descripcion"),
    ("/clear",      "  Limpiar historial de chat"),'''
new = '''    # ── 8 · Framework BAGO ─────────────────────────────────────────
    (None,          "  -- Framework BAGO (160 cmds) ------------------"),
    ("__all_cmds__","  > Todos los comandos BAGO..."),

    # ── 9 · Utilidades ───────────────────────────────────────────────
    (None,          "  -- Utilidades ---------------------------------"),
    ("/help",       "  Ayuda  -- todos los comandos con descripcion"),
    ("/clear",      "  Limpiar historial de chat"),'''
menu = menu.replace(old, new)

# Replace _cmd_main_menu to handle __all_cmds__
old_fn = '''def _cmd_main_menu(session) -> str | None:
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

new_fn = '''def _all_cmds_menu(session) -> str | None:
    import importlib.util
    reg_path = Path(__file__).resolve().parents[2] / "tool_registry.py"
    entries = [("__back__", "  ↩  Volver al menú principal")]
    if reg_path.exists():
        try:
            spec = importlib.util.spec_from_file_location("_tr_menu", str(reg_path))
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(reg_path.parent))
            spec.loader.exec_module(mod)
            registry = getattr(mod, "REGISTRY", {})
            stabs = {"core": [], "dangerous": [], "experimental": [], "legacy": [], "internal": []}
            for name, entry in sorted(registry.items()):
                stab = getattr(entry, "stability", "unknown")
                stabs.setdefault(stab, []).append(entry)
            for stab in ("core", "dangerous", "experimental", "legacy", "internal"):
                if not stabs.get(stab):
                    continue
                entries.append((None, f"  -- {stab.upper()} ({len(stabs[stab])}) ---"))
                for e in sorted(stabs[stab], key=lambda x: x.cmd):
                    desc = (getattr(e, "description", "") or "")[:45]
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

menu = menu.replace(old_fn, new_fn)
menu_path.write_text(menu, encoding="utf-8")
print("PATCHED main_menu.py")

# ── PATCH cmd.py — fallback genérico para cualquier /cmd ─────────────────────
cmd_path = Path(".bago/tools/bago/cmd.py")
cmd = cmd_path.read_text(encoding="utf-8")

# Insert helper near imports
old_imp = "from .ui import console, pe, pi"
new_imp = """from .ui import console, pe, pi

# ── Generic BAGO command runner (fallback for any /cmd not handled above) ──
def _run_bago_cmd(cmd: str, args: str) -> bool:
    import subprocess
    bago_script = Path(__file__).resolve().parents[3] / "bago"
    if not bago_script.exists():
        return False
    full_args = [cmd] + (args.split() if args else [])
    pi(f"[dim]Ejecutando: bago {' '.join(full_args)}[/dim]")
    result = subprocess.run(
        [sys.executable, str(bago_script)] + full_args,
        cwd=str(bago_script.parent),
    )
    return result.returncode == 0"""
cmd = cmd.replace(old_imp, new_imp)

# Replace final else block
old_else = '''        else:
            pe(f"Desconocido: {v}  —  /help")
    return True'''
new_else = '''        else:
            _ran = _run_bago_cmd(v.lstrip("/"), a)
            if _ran:
                return True
            pe(f"Desconocido: {v}  —  /help")
    return True'''
cmd = cmd.replace(old_else, new_else)

cmd_path.write_text(cmd, encoding="utf-8")
print("PATCHED cmd.py")
