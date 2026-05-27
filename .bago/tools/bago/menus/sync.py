
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import datetime
import json
import platform
import shutil
import subprocess as sp
import sys
import zipfile
from pathlib import Path

from rich.panel import Panel

from ..constants import BAGO_DIR, BAGO_REPO_ROOT, BAGO_SYSTEM, SYNC_REMOTES_FILE, USER_BAGO
from ..sendnow_api import SendNowClient, SendNowError
from ..tumba import tumba_add, tumba_get
from ..ui import console, _menu_input, _menu_select, pe, pi


def _send_api_base_url() -> str:
    return os.environ.get("BAGO_SEND_API_BASE_URL", "https://send.now/api").rstrip("/")


def _send_public_base_url() -> str:
    return os.environ.get("BAGO_SEND_PUBLIC_BASE_URL", "https://send.now").rstrip("/")


def _sendnow_client(api_key: str) -> SendNowClient:
    return SendNowClient(
        api_key=api_key,
        base_url=_send_api_base_url(),
        public_base_url=_send_public_base_url(),
    )


def _mirror_tree(src: Path, dst: Path) -> int:
    """Copy a directory tree preserving relative structure."""
    copied = 0
    if not src.exists():
        return copied
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied += 1
    return copied


def _portable_usb_bases() -> list[Path]:
    """Devuelve bases portables detectadas: drive\\bago o drive\\BAGO."""
    bases: list[Path] = []

    def _add(base: Path) -> None:
        if base not in bases:
            bases.append(base)

    def _scan_root(root: Path) -> None:
        marker = root / ".bago_portable"
        if marker.exists():
            for folder in ("bago", "BAGO"):
                base = root / folder
                if (base / ".bago").exists():
                    _add(base)
        for folder in ("bago", "BAGO"):
            base = root / folder
            if (base / ".bago").exists():
                _add(base)

    if platform.system() == "Windows":
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:\\")
            if root.exists():
                _scan_root(root)
    elif platform.system() == "Darwin":
        for vol in Path("/Volumes").iterdir():
            if vol.exists():
                _scan_root(vol)
    else:
        for base in [Path("/media"), Path("/run/media")]:
            if base.exists():
                for vol in base.iterdir():
                    if vol.exists():
                        _scan_root(vol)

    return bases


def _sync_knowledge(action: str = "sync") -> None:
    """Sync the canonical knowledge tree with the local bago-knowledge repo."""
    script = BAGO_DIR / "tools" / "knowledge_sync.py"
    if not script.exists():
        pe(f"No se encontro knowledge_sync.py en {script}")
        return
    r = sp.run([sys.executable, str(script), action], capture_output=True, text=True)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode == 0:
        pi(out or f"Knowledge sync OK ({action})")
    else:
        pe(err or out or f"knowledge sync fallo con codigo {r.returncode}")

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


# ── Cloud versioning (send.now) ───────────────────────────────────────────────
# Esquema de versionado:
#   bago_v3.4.0_20260519_1234.zip  ← snapshot versionado
#   bago_manifest.json             ← índice de versiones con URLs
#   install_bago.py                ← script autónomo de instalación
#
# El manifest se sube también al servicio cloud configurado. Su URL se guarda localmente.
# Con eso cualquier persona puede instalar BAGO sin GitHub:
#   python install_bago.py --from URL_DEL_SERVICIO
#
# El manifest NO es infinito: se mantienen hasta MAX_CLOUD_VERSIONS entradas.
# Las antiguas se eliminan del registro local (el servicio cloud no tiene API de borrado
# en cuentas free, pero los links simplemente dejan de listarse en el manifest).

_CLOUD_VERSIONS_FILE = None   # se resuelve en runtime para evitar importación circular
_MAX_CLOUD_VERSIONS  = 10


def _cloud_versions_file() -> Path:
    from ..constants import USER_BAGO
    return USER_BAGO / "cloud_versions.json"


def _load_cloud_manifest() -> dict:
    f = _cloud_versions_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"versions": [], "manifest_url": ""}


def _save_cloud_manifest(manifest: dict):
    f = _cloud_versions_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _sendcm_api_key() -> str:
    """Lee la API key de send.now desde credentials.json. La pide si no existe."""
    cred_file = USER_BAGO / "credentials.json"
    try:
        creds = json.loads(cred_file.read_text(encoding="utf-8"))
        key = creds.get("sendcm", {}).get("api_key", "")
        if key:
            return key
    except Exception:
        pass
    tumba_key = tumba_get("SendCM API Key") or tumba_get("sendcm api key") or tumba_get("sendcm")
    if tumba_key:
        return tumba_key

    key = _menu_input(
        "send.now API Key",
        "Introduce tu API key de send.now (o send.cm si usas compatibilidad):",
        default=""
    )
    if not key:
        return ""
    _save_sendcm_secret(key)
    return key


def _sendcm_key_exists() -> bool:
    try:
        creds = json.loads((USER_BAGO / "credentials.json").read_text(encoding="utf-8"))
        if creds.get("sendcm", {}).get("api_key", ""):
            return True
    except Exception:
        pass
    return bool(tumba_get("SendCM API Key") or tumba_get("sendcm api key") or tumba_get("sendcm"))


def _save_sendcm_secret(api_key: str, email: str = "") -> None:
    try:
        cred_file = USER_BAGO / "credentials.json"
        creds = {}
        if cred_file.exists():
            creds = json.loads(cred_file.read_text(encoding="utf-8"))
        creds.setdefault("sendcm", {})["api_key"] = api_key
        if email:
            creds["sendcm"]["email"] = email
        cred_file.write_text(json.dumps(creds, indent=2, ensure_ascii=False), encoding="utf-8")
        tumba_add(f"SendCM API Key: {api_key}")
        if email:
            tumba_add(f"SendCM Email: {email}")
        pi("API key guardada en credentials.json y en la tumba")
    except Exception as e:
        pe(f"No se pudo guardar la API key: {e}")


def _sync_sendcm_from_tumba(session) -> bool:
    api_key = tumba_get("SendCM API Key") or tumba_get("sendcm api key") or tumba_get("sendcm")
    email = tumba_get("SendCM Email") or ""
    if not api_key:
        pi("Abriendo /tumba fill sendcm para capturar las credenciales...")
        from ..commands.tumba import cmd_tumba
        cmd_tumba(session, "fill sendcm")
        api_key = tumba_get("SendCM API Key") or tumba_get("sendcm api key") or tumba_get("sendcm")
        email = tumba_get("SendCM Email") or ""
    if not api_key:
        pe("No se pudo completar send.cm desde la tumba.")
        return False
    _save_sendcm_secret(api_key, email)
    return True


def _diagnose_sync(session) -> None:
    remotes = _load_remotes()
    enabled = [rm for rm in remotes if rm.get("enabled", True)]
    missing = []
    if not enabled:
        missing.append(("repos", "No hay repositorios remotos habilitados"))
    if not _sendcm_key_exists():
        missing.append(("sendcm", "Falta la API key de send.now"))

    if not missing:
        pi("No faltan piezas críticas para sync/cloud.")
        return

    console.print(Panel(
        "\n".join(f"• {desc}" for _, desc in missing)
        + "\n\n[dim]Si falta una llave, BAGO puede abrir tumba, capturarla y copiarla al sitio correcto.[/dim]",
        title="[bold]Diagnóstico de sync[/bold]",
        border_style="yellow",
        expand=False,
    ))

    for kind, _desc in missing:
        if kind == "sendcm":
            action = _menu_select(
                "SendCM faltante",
                "¿Cómo quieres completar send.now?",
                [
                    ("tumba", "Rellenar en modo tumba y copiar a credentials.json"),
                    ("login", "Login normal de send.now"),
                    ("skip", "Saltar por ahora"),
                ],
            )
            if action == "tumba":
                if _sync_sendcm_from_tumba(session):
                    pi("send.now configurado desde tumba.")
            elif action == "login":
                session.creds.do_login("sendcm")
        elif kind == "repos":
            action = _menu_select(
                "Repositorios faltantes",
                "¿Quieres gestionarlos ahora?",
                [
                    ("manage", "Abrir gestor de repositorios"),
                    ("skip", "Saltar por ahora"),
                ],
            )
            if action == "manage":
                _manage_remotes()


def _sendcm_upload(api_key: str, file_path: Path, label: str = "") -> str:
    """Sube un fichero a send.now y devuelve la URL pública (o '' si falla)."""
    try:
        upload = _sendnow_client(api_key).upload_file(file_path)
        return upload.url
    except SendNowError as e:
        pe(f"send.now: error subiendo {label or file_path.name}: {e}")
        return ""
    except Exception as e:
        pe(f"send.now: error en upload {label or file_path.name}: {e}")
        return ""


def _generate_install_script(manifest_url: str) -> str:
    """Genera el contenido de install_bago.py — script autónomo de instalación."""
    return f'''\
#!/usr/bin/env python3
"""
install_bago.py — Instalador autónomo de BAGO
Descarga la version especificada (o la mas reciente) desde el servicio cloud configurado
y la extrae en el directorio actual.

Uso:
  python install_bago.py                         # ultima version
  python install_bago.py --version v3.4.0        # version concreta
  python install_bago.py --from URL              # URL directa al zip
  python install_bago.py --manifest URL          # manifest alternativo
  python install_bago.py --list                  # listar versiones
"""

import argparse, json, os, sys, urllib.request, zipfile
from pathlib import Path

MANIFEST_URL = "{manifest_url}"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def download(url: str, dest: Path):
    print(f"  Descargando {{url[:70]}}...")
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done  = 0
        while chunk := r.read(65536):
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                print(f"\\r  {{pct:3d}}% {{done // 1048576}} MB / {{total // 1048576}} MB", end="", flush=True)
    print()


def main():
    parser = argparse.ArgumentParser(description="Instalador BAGO desde el servicio cloud configurado")
    parser.add_argument("--manifest", default=MANIFEST_URL, help="URL del manifest JSON")
    parser.add_argument("--from",    dest="direct_url",    help="URL directa al zip")
    parser.add_argument("--version", default="",           help="Version a instalar (ej: v3.4.0)")
    parser.add_argument("--list",    action="store_true",  help="Listar versiones disponibles")
    parser.add_argument("--dest",    default=".",          help="Directorio de instalacion")
    args = parser.parse_args()

    # Manifest
    if not args.direct_url:
        if not args.manifest:
            print("ERROR: No hay manifest URL. Proporciona --manifest URL o --from URL")
            sys.exit(1)
        print(f"Leyendo manifest: {{args.manifest}}")
        try:
            manifest = fetch_json(args.manifest)
        except Exception as e:
            print(f"ERROR leyendo manifest: {{e}}"); sys.exit(1)

        versions = manifest.get("versions", [])
        if not versions:
            print("Sin versiones en el manifest."); sys.exit(1)

        if args.list:
            print("\\nVersiones disponibles en BAGO cloud:")
            for v in versions:
                print(f"  {{v['version']:12}}  {{v['date'][:10]}}  {{v['size_mb']:.1f}} MB  {{v['url']}}")
            sys.exit(0)

        if args.version:
            entry = next((v for v in versions if v["version"] == args.version), None)
            if not entry:
                print(f"Version {{args.version}} no encontrada."); sys.exit(1)
        else:
            entry = versions[-1]
            print(f"Ultima version: {{entry['version']}} ({{entry['date'][:10]}})")

        download_url = entry["url"]
        fname        = f"bago_{{entry['version']}}.zip"
    else:
        download_url = args.direct_url
        fname        = "bago_download.zip"

    dest_dir = Path(args.dest).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / fname

    print(f"\\nInstalando BAGO en: {{dest_dir}}")
    download(download_url, zip_path)

    print("  Extrayendo...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()

    print(f"\\n✅  BAGO instalado en {{dest_dir}}")
    print("   Ejecuta:  python .bago/tools/bago_chat.py")


if __name__ == "__main__":
    main()
'''


def _sync_cloud_snapshot():
    """Sube snapshot versionado al servicio cloud, actualiza manifest y genera install_bago.py."""
    try:
        import requests  # noqa: F401
    except ImportError:
        pe("El paquete 'requests' no está instalado. Ejecuta: pip install requests"); return

    api_key = _sendcm_api_key()
    if not api_key:
        return

    # Submenú: qué hacer
    action = _menu_select(
        "BAGO Cloud (send.now)",
        "¿Qué quieres hacer?",
        [
            ("upload",   "Subir nueva versión  (zip + actualizar manifest)"),
            ("list",     "Ver versiones en el manifest local"),
            ("install",  "Generar script install_bago.py con manifest actual"),
            ("show_url", "Mostrar URL del manifest actual"),
        ]
    )
    if action is None:
        return

    manifest = _load_cloud_manifest()

    if action == "list":
        versions = manifest.get("versions", [])
        if not versions:
            pi("No hay versiones en el manifest local todavía.")
        else:
            console.print("\n[bold]Versiones BAGO en cloud:[/bold]")
            for v in versions:
                console.print(f"  [cyan]{v['version']:14}[/cyan]  {v['date'][:10]}  "
                               f"{v.get('size_mb', 0):.1f} MB  [dim]{v['url']}[/dim]")
            if manifest.get("manifest_url"):
                console.print(f"\n  [dim]Manifest: {manifest['manifest_url']}[/dim]")
        return

    if action == "show_url":
        url = manifest.get("manifest_url", "")
        if url:
            console.print(f"\n  Manifest URL: [bold cyan]{url}[/bold cyan]")
            console.print(f"  [dim]Comparte para instalar con: python install_bago.py --manifest {url}[/dim]")
        else:
            pi("Todavía no se ha subido ningún manifest. Sube una versión primero.")
        return

    if action == "install":
        manifest_url = manifest.get("manifest_url", "")
        script = _generate_install_script(manifest_url)
        out = BAGO_REPO_ROOT / "install_bago.py"
        out.write_text(script, encoding="utf-8")
        pi(f"Script generado: {out}")
        if manifest_url:
            console.print(f"  [dim]Uso: python install_bago.py  (manifest precargado)[/dim]")
        else:
            console.print(f"  [yellow]⚠  Manifest URL vacía — sube una versión primero.[/yellow]")
        return

    # action == "upload"
    from ..constants import BAGO_VERSION
    ts  = datetime.datetime.now()
    tag = f"v{BAGO_VERSION}"
    zip_name = f"bago_{tag}_{ts.strftime('%Y%m%d_%H%M')}.zip"
    zip_path = Path.home() / zip_name

    # Crear zip (excluye .git y __pycache__)
    with console.status("[dim]Comprimiendo framework...[/dim]", spinner="dots"):
        try:
            exclude = {".git", "__pycache__", ".pytest_cache"}
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in BAGO_REPO_ROOT.rglob("*"):
                    if f.is_file() and not any(p in exclude for p in f.parts):
                        zf.write(f, f.relative_to(BAGO_REPO_ROOT))
            size_mb = zip_path.stat().st_size / 1_048_576
        except Exception as e:
            pe(f"Error creando zip: {e}"); return

    pi(f"Snapshot: {zip_name} ({size_mb:.1f} MB)")

    # Subir zip
    dl_url = _sendcm_upload(api_key, zip_path, zip_name)
    zip_path.unlink(missing_ok=True)
    if not dl_url:
        return
    pi(f"[green]✓[/green] Zip subido: {dl_url}")

    # Actualizar manifest local
    versions = manifest.get("versions", [])
    versions.append({
        "version": tag,
        "date":    ts.isoformat(),
        "size_mb": round(size_mb, 2),
        "url":     dl_url,
        "name":    zip_name,
    })
    # Mantener solo MAX_CLOUD_VERSIONS entradas
    if len(versions) > _MAX_CLOUD_VERSIONS:
        versions = versions[-_MAX_CLOUD_VERSIONS:]
    manifest["versions"] = versions

    # Generar y subir manifest JSON
    manifest_tmp = Path.home() / "bago_manifest.json"
    manifest_tmp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest_url = _sendcm_upload(api_key, manifest_tmp, "bago_manifest.json")
    manifest_tmp.unlink(missing_ok=True)

    if manifest_url:
        manifest["manifest_url"] = manifest_url
        pi(f"[green]✓[/green] Manifest subido: {manifest_url}")
    else:
        pi("[yellow]⚠  Manifest no subido, pero el zip sí está disponible.[/yellow]")

    _save_cloud_manifest(manifest)

    # Regenerar install_bago.py con la nueva manifest_url
    script = _generate_install_script(manifest.get("manifest_url", ""))
    install_out = BAGO_REPO_ROOT / "install_bago.py"
    install_out.write_text(script, encoding="utf-8")
    pi(f"install_bago.py actualizado → {install_out}")

    console.print(f"\n[bold green]✅ BAGO {tag} disponible en cloud[/bold green]")
    console.print(f"  Zip:      [cyan]{dl_url}[/cyan]")
    if manifest_url:
        console.print(f"  Manifest: [cyan]{manifest_url}[/cyan]")
        console.print(f"\n  [dim]Para instalar desde cero en otra máquina:[/dim]")
        console.print(f"  [bold]python install_bago.py --manifest {manifest_url}[/bold]")
        console.print(f"  [dim]o simplemente: python install_bago.py  (si el script ya tiene la URL)[/dim]")


# ── USB ───────────────────────────────────────────────────────────────────────

def _sync_usb():
    """Detecta y sincroniza con USB si esta disponible."""
    usb_candidates = _portable_usb_bases()

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
    synced += _mirror_tree(src_knowledge, dst_knowledge)
    synced += _mirror_tree(src_state, dst_state)

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
            ("sync_knowledge", "Sincronizar knowledge con repo local"),
            ("sync_usb",     "Sincronizar con USB  (mirror knowledge + state)"),
            ("sync_both",    "Sincronizar con repositorios Y USB"),
            ("diagnose",    "Diagnosticar faltantes y completar llaves/repos"),
            ("manage_repos", "Gestionar repositorios  (GitHub / GitLab / Codeberg / custom)"),
            ("cloud_snap",   "Cloud send.now  — subir versión / listar / instalar desde cero"),
            ("after_sync",   f"Comportamiento post-sync: [cyan]{session.sync_after}[/cyan]"),
        ]
        sel = _menu_select("BAGO / Sync",
                           "Sincronizacion de estado y conocimiento:", choices)
        if sel is None:
            break

        if sel in ("sync_git", "sync_both"):
            _sync_git(session)

        if sel == "sync_knowledge":
            _sync_knowledge("sync")

        if sel in ("sync_usb", "sync_both"):
            _sync_usb()

        if sel == "manage_repos":
            _manage_remotes()

        if sel == "diagnose":
            _diagnose_sync(session)

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
