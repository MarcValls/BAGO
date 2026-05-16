
import datetime
from pathlib import Path

from ..constants import BAGO_DIR, BAGO_REPO_ROOT, BAGO_SYSTEM
from ..ui import console, _menu_input, _menu_select, pe, pi

def _cmd_sync(session):
    """Sincronizacion + comportamiento post-sync (repliegue / letargo / continuar)."""
    while True:
        choices = [
            ("sync_git",     "Sincronizar con GitHub  (git add + commit + push)"),
            ("sync_usb",     "Sincronizar con USB  (mirror knowledge + state)"),
            ("sync_both",    "Sincronizar con GitHub Y USB"),
            ("after_sync",   f"Comportamiento post-sync: [cyan]{session.sync_after}[/cyan]"),
        ]
        sel = _menu_select("BAGO / Sync",
                           "Sincronizacion de estado y conocimiento:", choices)
        if sel is None: break

        if sel in ("sync_git", "sync_both"):
            _sync_git(session)

        if sel in ("sync_usb", "sync_both"):
            _sync_usb()

        if sel == "after_sync":
            mode = _menu_select("Post-sync",
                                "Que hace BAGO despues de sincronizar?",
                                [("continuar",  "Continuar — seguir en el chat normalmente"),
                                 ("repliegue",  "Repliegue — limpiar contexto RAM, volver a baseline"),
                                 ("letargo",    "Letargo — limpiar contexto y cerrar sesion")])
            if mode:
                session.sync_after = mode
                pi(f"Post-sync: {mode}")

def _sync_git(session):
    """Hace git add + commit + push del repo BAGO."""
    bago_root = BAGO_REPO_ROOT
    if not (bago_root / ".git").exists():
        pe(f"No es un repo git: {bago_root}"); return

    msg = _menu_input("Mensaje de commit",
                      "Mensaje del commit de sync:",
                      default=f"sync: sesion {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if not msg: return

    pi("Guardando sesion antes de sync...")
    saved = session.save()
    pi(f"  Sesion: {saved}")

    with console.status("[dim cyan]Sincronizando con GitHub...[/dim cyan]", spinner="dots"):
        try:
            import subprocess as sp
            r1 = sp.run(["git", "-C", str(bago_root), "add", "-A"],
                        capture_output=True, text=True)
            full_msg = f"{msg}\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
            r2 = sp.run(["git", "-C", str(bago_root), "commit", "-m", full_msg],
                        capture_output=True, text=True)
            r3 = sp.run(["git", "-C", str(bago_root), "push"],
                        capture_output=True, text=True)
            ok = r3.returncode == 0
            detail = r3.stdout.strip() or r3.stderr.strip() or "sin output"
        except Exception as e:
            ok = False; detail = str(e)

    if ok:
        pi(f"GitHub sync OK: {detail[:80]}")
    else:
        pe(f"Git push error: {detail[:200]}")
        return

    _post_sync(session)

def _sync_usb():
    """Detecta y sincroniza con USB si esta disponible."""
    import subprocess as sp
    # Buscar drives extraibles con estructura BAGO
    usb_candidates = []
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        p = Path(f"{letter}:\\BAGO\\.bago")
        if p.exists():
            usb_candidates.append(p.parent)

    if not usb_candidates:
        pe("No se encontro ningun USB con BAGO. Conecta el pendrive e intenta de nuevo.")
        return

    usb = usb_candidates[0]
    pi(f"USB encontrado: {usb}")

    # Sincronizar knowledge + state
    src_knowledge = BAGO_DIR / "knowledge"
    src_state     = BAGO_DIR / "state"
    dst_knowledge = usb / ".bago" / "knowledge"
    dst_state     = usb / ".bago" / "state"

    synced = 0
    for src, dst in [(src_knowledge, dst_knowledge), (src_state, dst_state)]:
        if src.exists():
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*"):
                if f.is_file():
                    import shutil
                    shutil.copy2(f, dst / f.name)
                    synced += 1

    pi(f"USB sync OK: {synced} archivos copiados a {usb}")

def _post_sync(session):
    """Ejecuta el comportamiento post-sync configurado."""
    mode = session.sync_after
    if mode == "continuar":
        pi("Post-sync: continuando sesion.")
        return

    if mode == "repliegue":
        pi("[bold]Repliegue activado:[/bold] limpiando contexto RAM, volviendo a baseline...")
        session.history = [{"role": "system", "content": BAGO_SYSTEM}]
        session.switches = 0
        session.started_at = datetime.datetime.now()
        pi("Contexto limpio. Sesion en baseline. Puedes continuar trabajando.")

    elif mode == "letargo":
        pi("[bold]Letargo:[/bold] sincronizacion completa. Cerrando sesion BAGO.")
        pi("Hasta la proxima activacion. /exit para salir.")
