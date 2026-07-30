"""Actualización segura de BAGO desde el runtime activo."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_API = "https://api.github.com/repos/MarcValls/BAGO/releases"
_lock = threading.Lock()
_state: dict = {"status": "idle", "message": "", "current": "", "latest": "", "detail": {}}


def _version(value: str) -> tuple[int, int, int, str]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)(?:[-+]([^\s]+))?", str(value))
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4) or "") if match else (0, 0, 0, "")


def _current() -> str:
    return (ROOT / "release_version.txt").read_text(encoding="utf-8").strip().lstrip("vV")


def _request_json(url: str):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "BAGO-updater"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _find_release() -> dict:
    current = _current()
    releases = _request_json(REPO_API + "?per_page=100")
    candidates = []
    for release in releases if isinstance(releases, list) else []:
        if release.get("draft") or release.get("prerelease"):
            continue
        tag = str(release.get("tag_name", ""))
        if _version(tag) > _version(current):
            assets = {str(item.get("name", "")).lower(): item for item in release.get("assets", [])}
            bundles = [item for item in release.get("assets", []) if str(item.get("name", "")).lower().endswith(".zip") and not str(item.get("name", "")).lower().endswith(".sha256")]
            pair = next((item for item in bundles if str(item.get("name", "")).lower() + ".sha256" in assets), None)
            if pair:
                candidates.append({"release": release, "bundle": pair, "checksum": assets[str(pair.get("name", "")).lower() + ".sha256"]})
    if not candidates:
        return {"available": False, "current": current, "latest": current, "message": "BAGO ya está actualizado"}
    selected = max(candidates, key=lambda item: _version(item["release"].get("tag_name", "")))
    release = selected["release"]
    return {"available": True, "current": current, "latest": release.get("tag_name", ""), "name": release.get("name", ""), "notes": release.get("body", ""), "bundle": selected["bundle"], "checksum": selected["checksum"]}


def check() -> dict:
    try:
        result = _find_release()
        with _lock:
            running = _state.get("status") == "running"
            _state.update({"current": result.get("current", ""), "latest": result.get("latest", ""), "detail": result, "message": result.get("message", "Nueva versión disponible")})
            if not running:
                _state["status"] = "ready"
        return result
    except Exception as exc:
        result = {"available": False, "current": _current(), "error": str(exc)}
        with _lock:
            _state.update({"status": "error", "message": str(exc), "detail": result})
        return result


def status() -> dict:
    with _lock:
        return dict(_state)


def _backup_runtime() -> str:
    backup_root = Path(os.environ.get("PROGRAMDATA", tempfile.gettempdir())) / "BAGO" / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    target = backup_root / f"bago-update-preflight-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(part in {"state", "logs", "__pycache__"} for part in path.relative_to(ROOT).parts):
                continue
            archive.write(path, path.relative_to(ROOT).as_posix())
    return str(target)


def start_update(tag: str = "") -> dict:
    with _lock:
        if _state.get("status") == "running":
            return {"ok": False, "error": "Ya hay una actualización en curso", **dict(_state)}
        _state.update({"status": "running", "message": "Preparando actualización…"})

    def worker() -> None:
        try:
            release = check()
            if not release.get("available") and not tag:
                raise RuntimeError(release.get("error") or "No hay una actualización disponible")
            backup = _backup_runtime()
            script = ROOT / "install-remote.ps1"
            powershell = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
            command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Mode", "Express", "-SkipTests", "-NoPathUpdate", "-NoShellIntegration", "-AllowUpgrade"]
            if tag:
                command += ["-Tag", tag]
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(command, cwd=str(ROOT), creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with _lock:
                _state.update({"status": "started", "message": "Actualización lanzada. Cierra y vuelve a abrir BAGO al terminar.", "detail": {"backup": backup, "target": release.get("latest", tag)}})
        except Exception as exc:
            with _lock:
                _state.update({"status": "error", "message": str(exc), "detail": {}})
    threading.Thread(target=worker, name="bago-update", daemon=True).start()
    return {"ok": True, **status()}
