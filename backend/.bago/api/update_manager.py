"""Actualizador integrado de BAGO basado en GitHub Releases.

El backend es la autoridad: descubre la release estable, descarga el payload,
verifica SHA-256 y deja la sustitución atómica a un proceso externo para que
el runtime en uso pueda cerrarse sin perder el estado del usuario.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
REPO_API = "https://api.github.com/repos/MarcValls/BAGO/releases"
RELEASE_PAGE = "https://github.com/MarcValls/BAGO/releases"
ACTIVE_STATES = {"queued", "downloading", "verifying", "applying"}
PRESERVED_STATES = ACTIVE_STATES | {"ready"}
_TAG_RE = re.compile(r"^v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
_SHA_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
_ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _version(value: str) -> tuple[int, int, int, tuple]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", str(value))
    if not match:
        return (0, 0, 0, ())
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ("~",)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease)


def _current() -> str:
    path = ROOT / "release_version.txt"
    return path.read_text(encoding="utf-8").strip().lstrip("vV") if path.is_file() else "0.0.0"


def _installation() -> dict:
    if ROOT.name.lower() != "backend":
        return {
            "ready": False,
            "root": str(ROOT),
            "reason": "Esta instalación no usa el layout actual backend + electron-viewer.",
        }
    install_root = ROOT.parent.resolve()
    viewer = install_root / "electron-viewer" / "BAGO.exe"
    if (install_root / ".git").exists():
        return {
            "ready": False,
            "root": str(install_root),
            "reason": "El checkout de desarrollo no se actualiza desde la aplicación.",
        }
    if install_root.name.lower() != "bago" or not viewer.is_file():
        return {
            "ready": False,
            "root": str(install_root),
            "reason": "No se encontró una instalación BAGO actualizable.",
        }
    return {"ready": True, "root": str(install_root), "viewer": str(viewer), "reason": ""}


def _update_root() -> Path:
    override = os.environ.get("BAGO_UPDATE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    installation = _installation()
    if installation.get("ready"):
        return Path(str(installation["root"])) / "state" / "updates"
    suffix = hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:10]
    return Path(tempfile.gettempdir()) / f"bago-dev-updates-{suffix}"


def _state_path() -> Path:
    return _update_root() / "release-update.json"


def _default_state() -> dict:
    return {
        "status": "idle",
        "phase": "idle",
        "message": "",
        "current": _current(),
        "latest": "",
        "available": False,
        "percent": 0,
        "transferred": 0,
        "total": 0,
        "release": {},
        "installation": _installation(),
        "error": "",
        "updated_at": _now(),
    }


def _load_state() -> dict:
    state = _default_state()
    path = _state_path()
    if not path.is_file():
        state["updated_at"] = ""
        return state
    try:
        saved = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(saved, dict):
            state.update(saved)
    except (OSError, ValueError):
        pass
    state["current"] = _current()
    state["installation"] = _installation()
    return state


_state: dict = _load_state()


def _persist(snapshot: dict) -> None:
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    except OSError:
        # El estado en memoria sigue siendo útil aunque el disco esté bloqueado.
        return


def _set_state(**changes) -> dict:
    with _lock:
        _state.update(changes)
        _state["updated_at"] = _now()
        snapshot = dict(_state)
    _persist(snapshot)
    return snapshot


def _replace_state(snapshot: dict) -> dict:
    with _lock:
        _state.clear()
        _state.update(snapshot)
        _state["updated_at"] = _now()
        restored = dict(_state)
    _persist(restored)
    return restored


def _request_json(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"BAGO-updater/{_current()}",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _release_asset(release: dict) -> dict:
    assets = [item for item in release.get("assets", []) if isinstance(item, dict)]
    version = str(release.get("tag_name", "")).lstrip("vV").lower()
    preferred = f"bago-{version}-distribution.zip"
    bundle = next(
        (item for item in assets if str(item.get("name", "")).lower() == preferred),
        None,
    ) or next(
        (item for item in assets if str(item.get("name", "")).lower().endswith("-distribution.zip")),
        None,
    )
    if not bundle:
        raise RuntimeError("La release no contiene el payload completo distribution.zip.")
    checksum_name = str(bundle.get("name", "")) + ".sha256"
    checksum = next(
        (item for item in assets if str(item.get("name", "")).lower() == checksum_name.lower()),
        None,
    )
    digest = str(bundle.get("digest", "")).removeprefix("sha256:").lower()
    if digest and not _SHA_RE.fullmatch(digest):
        digest = ""
    if not digest and not checksum:
        raise RuntimeError("La release no publica SHA-256 verificable para el payload.")
    return {
        "name": str(bundle.get("name", "")),
        "url": str(bundle.get("browser_download_url", "")),
        "size": int(bundle.get("size", 0) or 0),
        "digest": digest,
        "checksum_url": str((checksum or {}).get("browser_download_url", "")),
    }


def _find_release(tag: str = "") -> dict:
    current = _current()
    if tag:
        if not _TAG_RE.fullmatch(tag):
            raise RuntimeError("Tag de release no válido.")
        url = f"{REPO_API}/tags/{urllib.parse.quote(tag, safe='')}"
    else:
        url = f"{REPO_API}/latest"
    release = _request_json(url)
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        raise RuntimeError("GitHub no devolvió una release estable válida.")
    latest = str(release.get("tag_name", ""))
    if not _TAG_RE.fullmatch(latest):
        raise RuntimeError("La release publicada no tiene una versión válida.")
    asset = _release_asset(release)
    available = _version(latest) > _version(current)
    return {
        "available": available,
        "current": current,
        "latest": latest,
        "name": str(release.get("name", latest)),
        "notes": str(release.get("body", "")),
        "published_at": str(release.get("published_at", "")),
        "release_url": str(release.get("html_url", RELEASE_PAGE)),
        "asset": asset,
        "installation": _installation(),
        "message": "Nueva versión disponible" if available else "BAGO ya está actualizado",
    }


def check() -> dict:
    try:
        result = _find_release()
        with _lock:
            ready_stale = (
                _state.get("status") == "ready"
                and _state.get("latest") != result["latest"]
            )
            active = _state.get("status") in PRESERVED_STATES and not ready_stale
            completed = _state.get("status") == "completed" and not result["available"]
        changes = {
            "current": result["current"],
            "latest": result["latest"],
            "available": result["available"],
            "release": result,
            "installation": result["installation"],
            "error": "",
        }
        if not active:
            changes.update({
                "status": "completed" if completed else "idle",
                "phase": "completed" if completed else "idle",
                "message": _state.get("message") if completed else result["message"],
                "percent": 100 if completed else 0,
            })
        _set_state(**changes)
        return result
    except Exception as exc:
        with _lock:
            active = _state.get("status") in PRESERVED_STATES
            cached = dict(_state.get("release", {})) if isinstance(_state.get("release"), dict) else {}
        if cached.get("latest"):
            warning = "Sin conexión con GitHub. Se muestra la última comprobación guardada."
            cached.update({"offline": True, "warning": warning})
            if not active:
                _set_state(
                    status="offline",
                    phase="check",
                    message=warning,
                    error="",
                    current=_current(),
                    latest=cached.get("latest", ""),
                    available=bool(cached.get("available")),
                    release=cached,
                    installation=_installation(),
                )
            return cached
        friendly_error = "No se pudo conectar con GitHub Releases. Comprueba la conexión e inténtalo de nuevo."
        result = {
            "available": False,
            "current": _current(),
            "latest": "",
            "installation": _installation(),
            "release_url": RELEASE_PAGE,
            "error": friendly_error,
            "detail": str(exc),
        }
        if not active:
            _set_state(status="error", phase="check", message=friendly_error, **result)
        return result


def status() -> dict:
    # El helper externo puede haber actualizado el JSON después del reinicio.
    disk = _load_state()
    with _lock:
        if str(disk.get("updated_at", "")) > str(_state.get("updated_at", "")):
            _state.update(disk)
        _state["current"] = _current()
        _state["installation"] = _installation()
        return dict(_state)


def _assert_download_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    local_test = os.environ.get("BAGO_UPDATE_ALLOW_INSECURE_LOCAL", "") == "1" and host in {"127.0.0.1", "localhost"}
    if not ((parsed.scheme == "https" and host in _ALLOWED_DOWNLOAD_HOSTS) or local_test):
        raise RuntimeError("La release contiene una URL de descarga no permitida.")


def _download_text(url: str) -> str:
    _assert_download_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": f"BAGO-updater/{_current()}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(4096).decode("utf-8", errors="replace")


def _download_bundle(asset: dict, destination: Path) -> str:
    url = str(asset.get("url", ""))
    _assert_download_url(url)
    expected = str(asset.get("digest", "")).lower()
    checksum_url = str(asset.get("checksum_url", ""))
    if checksum_url:
        match = _SHA_RE.search(_download_text(checksum_url))
        if not match:
            raise RuntimeError("El archivo .sha256 no contiene un hash válido.")
        declared = match.group(0).lower()
        if expected and declared != expected:
            raise RuntimeError("El digest de GitHub y el archivo .sha256 no coinciden.")
        expected = declared
    if not expected:
        raise RuntimeError("No hay SHA-256 esperado para verificar la descarga.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": f"BAGO-updater/{_current()}"})
    digest = hashlib.sha256()
    transferred = 0
    last_report = 0.0
    expected_size = int(asset.get("size") or 0)
    if expected_size <= 0 or expected_size > 2 * 1024 * 1024 * 1024:
        raise RuntimeError("El tamaño publicado del payload no es válido.")
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
        resolved_url = getattr(response, "geturl", lambda: url)()
        _assert_download_url(str(resolved_url))
        total = int(response.headers.get("Content-Length") or expected_size)
        _set_state(status="downloading", phase="download", message="Descargando actualización…", total=total, transferred=0, percent=0)
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            digest.update(chunk)
            transferred += len(chunk)
            if transferred > expected_size:
                raise RuntimeError("La descarga supera el tamaño publicado por GitHub.")
            now = time.monotonic()
            if now - last_report >= 0.2:
                percent = min(99, int(transferred * 100 / total)) if total else 0
                _set_state(transferred=transferred, total=total, percent=percent)
                last_report = now
    if transferred != expected_size:
        partial.unlink(missing_ok=True)
        raise RuntimeError("La descarga no coincide con el tamaño publicado por GitHub.")
    actual = digest.hexdigest().lower()
    if actual != expected:
        partial.unlink(missing_ok=True)
        raise RuntimeError("SHA-256 no coincide; la actualización se ha descartado.")
    os.replace(partial, destination)
    return actual


def _verify_bundle(path: Path, expected_version: str) -> None:
    _set_state(status="verifying", phase="verify", message="Verificando contenido…", percent=99)
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            total_uncompressed = 0
            names = {}
            for info in infos:
                normalized = info.filename.replace("\\", "/")
                pure = PurePosixPath(normalized)
                if pure.is_absolute() or ".." in pure.parts or (pure.parts and ":" in pure.parts[0]):
                    raise RuntimeError("El payload contiene una ruta insegura.")
                total_uncompressed += int(info.file_size)
                if total_uncompressed > 2 * 1024 * 1024 * 1024:
                    raise RuntimeError("El payload expandido supera el límite permitido.")
                names[normalized] = info.filename
            version_name = "compiled/backend/release_version.txt"
            viewer_name = "compiled/electron-viewer/BAGO.exe"
            if version_name not in names or viewer_name not in names:
                raise RuntimeError("El payload no contiene backend y aplicación Electron completos.")
            packaged = archive.read(names[version_name]).decode("utf-8-sig").strip().lstrip("vV")
            if packaged != expected_version.lstrip("vV"):
                raise RuntimeError(f"El payload declara {packaged}, pero la release es {expected_version}.")
    except zipfile.BadZipFile as exc:
        raise RuntimeError("El payload descargado no es un ZIP válido.") from exc


def start_update(tag: str = "") -> dict:
    with _lock:
        if _state.get("status") in ACTIVE_STATES:
            return {**dict(_state), "ok": False, "error": "Ya hay una actualización en curso"}
        previous = dict(_state)
        _state.update(
            status="queued",
            phase="prepare",
            message="Preparando descarga…",
            error="",
            percent=0,
            transferred=0,
            total=0,
        )
        _state["updated_at"] = _now()
        reserved = dict(_state)
    _persist(reserved)
    try:
        release = _find_release(tag)
        if not release.get("available"):
            _replace_state(previous)
            return {**release, "ok": False, "error": "No hay una versión más reciente disponible"}
        if not release["installation"].get("ready"):
            _replace_state(previous)
            return {**release, "ok": False, "error": release["installation"].get("reason")}
    except Exception as exc:
        _replace_state(previous)
        return {**status(), "ok": False, "error": str(exc)}

    _set_state(
        status="queued",
        phase="prepare",
        message="Preparando descarga…",
        current=release["current"],
        latest=release["latest"],
        available=True,
        release=release,
        installation=release["installation"],
        error="",
        percent=0,
        transferred=0,
        total=int(release["asset"].get("size", 0)),
    )

    def worker() -> None:
        try:
            safe_tag = re.sub(r"[^0-9A-Za-z._-]", "_", release["latest"])
            bundle = _update_root() / f"bago-{safe_tag}-distribution.zip"
            actual = _download_bundle(release["asset"], bundle)
            _verify_bundle(bundle, release["latest"])
            detail = {"bundle_path": str(bundle), "sha256": actual}
            _set_state(
                status="ready",
                phase="ready",
                message="Actualización verificada. Lista para instalar y reiniciar.",
                percent=100,
                detail=detail,
                error="",
            )
        except Exception as exc:
            _set_state(status="error", phase="prepare", message=str(exc), error=str(exc), percent=0)

    threading.Thread(target=worker, name="bago-update-download", daemon=True).start()
    return {"ok": True, **status()}


def apply_update() -> dict:
    with _lock:
        if _state.get("status") != "ready":
            return {**dict(_state), "ok": False, "error": "La actualización aún no está descargada y verificada"}
        previous = dict(_state)
        _state.update(
            status="applying",
            phase="apply",
            message="BAGO se cerrará, instalará la actualización y volverá a abrirse.",
            error="",
        )
        _state["updated_at"] = _now()
        snapshot = dict(_state)
    _persist(snapshot)
    installation = snapshot.get("installation") if isinstance(snapshot.get("installation"), dict) else _installation()
    if not installation.get("ready"):
        _replace_state(previous)
        return {**previous, "ok": False, "error": installation.get("reason", "Instalación no actualizable")}
    detail = snapshot.get("detail") if isinstance(snapshot.get("detail"), dict) else {}
    bundle = Path(str(detail.get("bundle_path", "")))
    expected_sha = str(detail.get("sha256", ""))
    helper = Path(__file__).with_name("apply_release_update.ps1")
    if not bundle.is_file() or not helper.is_file() or not _SHA_RE.fullmatch(expected_sha):
        _replace_state(previous)
        return {**previous, "ok": False, "error": "Faltan archivos verificados para aplicar la actualización"}

    latest = str(snapshot.get("latest", ""))
    powershell = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not Path(powershell).is_file():
        powershell = "powershell.exe"
    log_path = _update_root() / "apply.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(helper),
        "-BundlePath", str(bundle),
        "-InstallRoot", str(installation["root"]),
        "-StatePath", str(_state_path()),
        "-ExpectedVersion", latest,
        "-ExpectedSha256", expected_sha,
        "-BackendPid", str(os.getpid()),
        "-Restart",
    ]
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        with log_path.open("ab") as log:
            subprocess.Popen(
                command,
                cwd=str(_update_root()),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                close_fds=True,
            )
    except OSError as exc:
        _replace_state(previous)
        return {**previous, "ok": False, "error": str(exc)}
    return {"ok": True, **status()}
