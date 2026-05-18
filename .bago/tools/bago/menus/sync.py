
import datetime
import json
import shutil
import subprocess as sp
import zipfile
from pathlib import Path

from ..constants import BAGO_DIR, BAGO_REPO_ROOT, BAGO_SYSTEM, SYNC_REMOTES_FILE
from ..ui import console, _menu_input, _menu_select, pe, pi

# ── Gestión de repositorios remotos ────────────────────────────────────────────

def _load_remotes() -> list[dict]:
    """Carga lista de remotes configurados. Siempre incluye origin si existe."""
    remotes: list[dict] = []
    try:
        if SYNC_REMOTES_FILE.exists():
            remotes = json.loads(SYNC_REMOTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        remotes = []
    # Sincronizar con lo que git ya tiene configurado como origin
    try:
        r = sp.run(
            ["git", "-C", str(BAGO_REPO_ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True
        )
        if r.returncode == 0 and r.stdout.strip():
            origin_url = r.stdout.strip()
            if not any(rm.get("name") == "origin" for rm in remotes):
                remotes.insert(0, {
                    "name": "origin",
                    "url": origin_url,
                    "label": "GitHub (origin)",
                    "enabled": True,
                })
    except Exception:
        pass
    return remotes


def _save_remotes(remotes: list[dict]):
    SYNC_REMOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_REMOTES_FILE.write_text(json.dumps(remotes, indent=2, ensure_ascii=False), encoding="utf-8")


def _ensure_git_remote(name: str, url: str):
    """Añade o actualiza un remote git en el repo."""
    existing = sp.run(
        ["git", "-C", str(BAGO_REPO_ROOT), "remote"],
        capture_output=True, text=True
    ).stdout.split()
    if name in existing:
        sp.run(["git", "-C", str(BAGO_REPO_ROOT), "remote", "set-url", name, url],
               capture_output=True)
    else:
        sp.run(["git", "-C", str(BAGO_REPO_ROOT), "remote", "add", name, url],
               capture_output=True)


def _manage_remotes():
    """Submenú para añadir / quitar / habilitar remotos."""
    while True:
        remotes = _load_remotes()
        choices = []
        for i, rm in enumerate(remotes):
            status = "[green]✓[/green]" if rm.get("enabled", True) else "[dim]✗[/dim]"
            choices.append((f"toggle_{i}", f"{status}  {rm['label']}  [dim]{rm['url'][:60]}[/dim]"))
        choices.append(("add_github",   "➕  Añadir repositorio GitHub"))
        choices.append(("add_gitlab",   "➕  Añadir repositorio GitLab"))
        choices.append(("add_codeberg", "➕  Añadir repositorio Codeberg"))
        choices.append(("add_custom",   "➕  Añadir repositorio personalizado (URL git)"))
        if remotes:
            choices.append(("remove",   "🗑   Eliminar un repositorio"))

        sel = _menu_select("Gestionar repositorios", "Remotos configurados:", choices)
        if sel is None:
            break

        # Habilitar / deshabilitar
        if sel.startswith("toggle_"):
            idx = int(sel.split("_")[1])
            remotes[idx]["enabled"] = not remotes[idx].get("enabled", True)
            state = "activado" if remotes[idx]["enabled"] else "desactivado"
            pi(f"{remotes[idx]['label']}: {state}")
            _save_remotes(remotes)
            continue

        # Añadir GitHub
        if sel == "add_github":
            url = _menu_input("GitHub", "URL del repo (ej: https://github.com/user/BAGO.git):", default="")
            if not url:
                continue
            name = _menu_input("Nombre del remote", "Nombre del remote git (ej: github-backup):", default="github-backup")
            if not name:
                continue
            remotes.append({"name": name, "url": url, "label": f"GitHub ({name})", "enabled": True})
            _ensure_git_remote(name, url)
            _save_remotes(remotes)
            pi(f"Repositorio añadido: {name} → {url}")
            continue

        # Añadir GitLab
        if sel == "add_gitlab":
            url = _menu_input("GitLab", "URL del repo (ej: https://gitlab.com/user/BAGO.git):", default="")
            if not url:
                continue
            name = _menu_input("Nombre del remote", "Nombre del remote git:", default="gitlab")
            if not name:
                continue
            remotes.append({"name": name, "url": url, "label": f"GitLab ({name})", "enabled": True})
            _ensure_git_remote(name, url)
            _save_remotes(remotes)
            pi(f"Repositorio añadido: {name} → {url}")
            continue

        # Añadir Codeberg
        if sel == "add_codeberg":
            url = _menu_input("Codeberg", "URL del repo (ej: https://codeberg.org/user/BAGO.git):", default="")
            if not url:
                continue
            name = _menu_input("Nombre del remote", "Nombre del remote git:", default="codeberg")
            if not name:
                continue
            remotes.append({"name": name, "url": url, "label": f"Codeberg ({name})", "enabled": True})
            _ensure_git_remote(name, url)
            _save_remotes(remotes)
            pi(f"Repositorio añadido: {name} → {url}")
            continue

        # Añadir custom
        if sel == "add_custom":
            url = _menu_input("Repositorio custom", "URL git del repositorio:", default="")
            if not url:
                continue
            label = _menu_input("Etiqueta", "Nombre descriptivo:", default=url[:40])
            name = _menu_input("Nombre del remote", "Nombre del remote git:", default="backup")
            if not name:
                continue
            remotes.append({"name": name, "url": url, "label": label or name, "enabled": True})
            _ensure_git_remote(name, url)
            _save_remotes(remotes)
            pi(f"Repositorio añadido: {name} → {url}")
            continue

        # Eliminar
        if sel == "remove":
            if not remotes:
                continue
            rm_choices = [(str(i), f"{rm['label']}  [dim]{rm['url'][:60]}[/dim]")
                          for i, rm in enumerate(remotes)]
            rm_sel = _menu_select("Eliminar remote", "¿Cuál eliminar?", rm_choices)
            if rm_sel is not None:
                idx = int(rm_sel)
                removed = remotes.pop(idx)
                _save_remotes(remotes)
                pi(f"Eliminado: {removed['label']}")


# ── Sincronización con todos los remotos habilitados ──────────────────────────

def _sync_git(session):
    """Hace git add + commit + push a todos los remotos habilitados."""
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

    remotes = [rm for rm in _load_remotes() if rm.get("enabled", True)]
    if not remotes:
        pe("No hay repositorios remotos habilitados. Configura uno en 'Gestionar repositorios'.")
        return

    # git add + commit (una sola vez)
    with console.status("[dim cyan]Preparando commit...[/dim cyan]", spinner="dots"):
        sp.run(["git", "-C", str(bago_root), "add", "-A"], capture_output=True, text=True)
        full_msg = f"{msg}\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
        sp.run(["git", "-C", str(bago_root), "commit", "-m", full_msg],
               capture_output=True, text=True)

    # Push a cada remote habilitado
    any_ok = False
    for rm in remotes:
        name = rm["name"]
        label = rm["label"]
        with console.status(f"[dim cyan]Enviando a {label}...[/dim cyan]", spinner="dots"):
            try:
                # Pull + rebase solo para origin para evitar divergencias
                if name == "origin":
                    sp.run(["git", "-C", str(bago_root), "pull", "--rebase", "--autostash",
                            name, "main"], capture_output=True, text=True)
                r_push = sp.run(
                    ["git", "-C", str(bago_root), "push", name, "main"],
                    capture_output=True, text=True
                )
                ok = r_push.returncode == 0
                detail = r_push.stdout.strip() or r_push.stderr.strip() or "sin output"
            except Exception as exc:
                ok = False
                detail = str(exc)

        if ok:
            pi(f"[green]✓[/green]  {label}: enviado correctamente")
            any_ok = True
        else:
            pe(f"[red]✗[/red]  {label}: {detail[:120]}")

    if any_ok:
        _post_sync(session)


# ── Snapshot a nube (send.cm) ─────────────────────────────────────────────────

def _sync_cloud_snapshot():
    """Crea un zip del framework y lo sube a send.cm. Devuelve link compartible."""
    try:
        import requests
    except ImportError:
        pe("El paquete 'requests' no está instalado. Ejecuta: pip install requests"); return

    # Leer API key guardada
    from ..constants import USER_BAGO
    cred_file = USER_BAGO / "credentials.json"
    api_key = ""
    try:
        creds = json.loads(cred_file.read_text(encoding="utf-8"))
        api_key = creds.get("sendcm", {}).get("api_key", "")
    except Exception:
        pass

    if not api_key:
        api_key = _menu_input(
            "send.cm API Key",
            "Introduce tu API key de send.cm (se guarda en credentials.json):",
            default=""
        )
        if not api_key:
            pe("Sin API key — operación cancelada."); return
        # Guardar
        try:
            creds = {}
            if cred_file.exists():
                creds = json.loads(cred_file.read_text(encoding="utf-8"))
            creds.setdefault("sendcm", {})["api_key"] = api_key
            cred_file.write_text(json.dumps(creds, indent=2, ensure_ascii=False), encoding="utf-8")
            pi("API key guardada en credentials.json")
        except Exception as e:
            pe(f"No se pudo guardar la API key: {e}")

    # Crear zip
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    zip_path = Path.home() / f"bago_snapshot_{ts}.zip"
    with console.status("[dim]Comprimiendo framework...[/dim]", spinner="dots"):
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in BAGO_REPO_ROOT.rglob("*"):
                    if f.is_file() and ".git" not in f.parts:
                        zf.write(f, f.relative_to(BAGO_REPO_ROOT))
            size_mb = zip_path.stat().st_size / 1_048_576
        except Exception as e:
            pe(f"Error creando zip: {e}"); return

    pi(f"Snapshot creado: {zip_path.name} ({size_mb:.1f} MB)")

    # Obtener servidor de upload
    with console.status("[dim]Conectando a send.cm...[/dim]", spinner="dots"):
        try:
            r = requests.get(
                "https://send.cm/api/upload/server",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            r.raise_for_status()
            upload_url = r.json()["data"]["upload_url"]
        except Exception as e:
            pe(f"Error obteniendo servidor de upload: {e}")
            zip_path.unlink(missing_ok=True)
            return

    # Subir
    with console.status("[dim cyan]Subiendo snapshot a send.cm...[/dim cyan]", spinner="dots"):
        try:
            with open(zip_path, "rb") as fh:
                up = requests.post(
                    upload_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (zip_path.name, fh)},
                    timeout=120
                )
            up.raise_for_status()
            data = up.json()
            download_url = data.get("data", {}).get("url") or data.get("url", "?")
        except Exception as e:
            pe(f"Error en upload: {e}")
            zip_path.unlink(missing_ok=True)
            return

    zip_path.unlink(missing_ok=True)
    pi(f"[green]✓ Snapshot subido:[/green]")
    console.print(f"  [bold cyan]{download_url}[/bold cyan]")
    console.print(f"  [dim]Comparte este link para que alguien descargue BAGO[/dim]")


# ── USB ───────────────────────────────────────────────────────────────────────

def _sync_usb():
    """Detecta y sincroniza con USB si esta disponible."""
    import platform
    usb_candidates = []

    if platform.system() == "Darwin":
        for vol in Path("/Volumes").iterdir():
            p = vol / "BAGO" / ".bago"
            if p.exists():
                usb_candidates.append(p.parent)
            p2 = vol / ".bago"
            if p2.exists() and vol not in usb_candidates:
                usb_candidates.append(vol)
    elif platform.system() == "Linux":
        for base in [Path("/media"), Path("/run/media")]:
            if base.exists():
                for vol in base.rglob("BAGO/.bago"):
                    usb_candidates.append(vol.parent)
                for vol in base.rglob(".bago"):
                    if vol.parent not in usb_candidates:
                        usb_candidates.append(vol.parent)
    else:
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            p = Path(f"{letter}:\\BAGO\\.bago")
            if p.exists():
                usb_candidates.append(p.parent)

    if not usb_candidates:
        pe("No se encontro ningun USB con BAGO. Conecta el pendrive e intenta de nuevo.")
        return

    usb = usb_candidates[0]
    pi(f"USB encontrado: {usb}")

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
                    shutil.copy2(f, dst / f.name)
                    synced += 1

    pi(f"USB sync OK: {synced} archivos copiados a {usb}")


# ── Menú principal sync ───────────────────────────────────────────────────────

def _cmd_sync(session):
    """Sincronizacion + comportamiento post-sync (repliegue / letargo / continuar)."""
    while True:
        remotes = _load_remotes()
        enabled = [rm for rm in remotes if rm.get("enabled", True)]
        repo_label = (
            ", ".join(rm["label"] for rm in enabled[:3])
            if enabled else "[dim]sin repositorios[/dim]"
        )
        choices = [
            ("sync_git",     f"Sincronizar con repositorios  ({repo_label})"),
            ("sync_usb",     "Sincronizar con USB  (mirror knowledge + state)"),
            ("sync_both",    "Sincronizar con repositorios Y USB"),
            ("manage_repos", "Gestionar repositorios  (GitHub / GitLab / Codeberg / custom)"),
            ("cloud_snap",   "Exportar snapshot a nube  (send.cm — link compartible)"),
            ("after_sync",   f"Comportamiento post-sync: [cyan]{session.sync_after}[/cyan]"),
        ]
        sel = _menu_select("BAGO / Sync",
                           "Sincronizacion de estado y conocimiento:", choices)
        if sel is None:
            break

        if sel in ("sync_git", "sync_both"):
            _sync_git(session)

        if sel in ("sync_usb", "sync_both"):
            _sync_usb()

        if sel == "manage_repos":
            _manage_remotes()

        if sel == "cloud_snap":
            _sync_cloud_snapshot()

        if sel == "after_sync":
            mode = _menu_select("Post-sync",
                                "Que hace BAGO despues de sincronizar?",
                                [("continuar",  "Continuar — seguir en el chat normalmente"),
                                 ("repliegue",  "Repliegue — limpiar contexto RAM, volver a baseline"),
                                 ("letargo",    "Letargo — limpiar contexto y cerrar sesion")])
            if mode:
                session.sync_after = mode
                pi(f"Post-sync: {mode}")


# ── Post-sync ──────────────────────────────────────────────────────────────────

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
