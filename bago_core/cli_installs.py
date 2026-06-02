#!/usr/bin/env python3
"""bago_core/cli_installs.py — escaneo de instalaciones BAGO en la máquina.

Uso:
    python -m bago_core.cli_installs            # JSON pretty a stdout
    python -m bago_core.cli_installs --plain    # sin indent (para pegar en web)
    bago list-installs                          # vía launcher (todas las copias)

Detecta instalaciones en:
  - C:\\Program Files\\BAGO              (instalación de sistema)
  - %USERPROFILE%\\.bago                 (instalación de trabajo por defecto)
  - %USERPROFILE%\\.bago\\active         (work / copia activa)
  - %USERPROFILE%\\.bago\\launch         (ignition / plataforma de lanzamiento)
  - %USERPROFILE%\\.bago\\dev            (dev / plataforma de desarrollo)
  - %USERPROFILE%\\BAGO                  (source tree del dev)
  - Cualquier otra ruta que tenga bago.ps1 + bago_core + scripts

Cada instalación detectada trae:
  - path         ruta absoluta
  - mode         active | work | dev | ign | launch | source | unknown
  - version      versión leída de release_version.txt o del tag en repo
  - has_bago_ps1 bool
  - has_bago_cmd bool
  - has_supervisor bool (si existe scripts/bago_supervisor.py)
  - has_probe       bool (si existe scripts/probe.py)
  - state_file      ~/.bago/state/supervisor.json si existe
  - supervisor_alive bool si el pid del state está vivo
  - last_release_sig SHA corto del release.sig más cercano
  - tag              v4.1.5-r2 si hay tag snapshot en bago_core/tags
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


KNOWN_LOCATIONS: list[tuple[str, str, str]] = [
    # (path_template, mode, description)
    ("{pf}\\BAGO",                                            "system",  "Instalación de sistema"),
    ("{home}\\.bago",                                          "user",    "User root (default work)"),
    ("{home}\\.bago\\active",                                  "work",    "Active / work"),
    ("{home}\\.bago\\launch",                                  "ign",     "Ignition / launch"),
    ("{home}\\.bago\\dev",                                     "dev",     "Dev tree (user)"),
    ("{home}\\BAGO",                                           "source",  "Source tree"),
]

EXTRA_HINTS = ["bago.ps1", "bago.cmd", "bago.sh", "release_version.txt"]


def _expand(p: str) -> Path:
    return Path(os.path.expandvars(p)).expanduser()


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        PROCESS_QUERY_LIMITED = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            return False
        STILL_ACTIVE = 259
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == STILL_ACTIVE
    except Exception:
        return False


def _read_version(root: Path) -> str:
    rv = root / "release_version.txt"
    if rv.is_file():
        return rv.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def _short_sig(p: Path) -> str:
    if not p.is_file():
        return ""
    try:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        return h[:16] + "..."
    except Exception:
        return ""


def _read_tag(root: Path) -> str:
    # busca el tag snapshot más reciente (v*.json) en bago_core/tags
    tags_dir = root / "bago_core" / "tags"
    if not tags_dir.is_dir():
        return ""
    versions = []
    for f in tags_dir.glob("v*.json"):
        versions.append((f.stat().st_mtime, f.stem))
    if not versions:
        return ""
    versions.sort(reverse=True)
    return versions[0][1]  # e.g. "v4.1.5"


def _classify(path: Path) -> dict[str, Any]:
    """Devuelve dict con todos los metadatos de la instalación."""
    out: dict[str, Any] = {
        "path":              str(path),
        "exists":            path.is_dir(),
        "mode":              "unknown",
        "description":       "",
        "version":           "",
        "tag":               "",
        "has_bago_ps1":      (path / "bago.ps1").is_file(),
        "has_bago_cmd":      (path / "bago.cmd").is_file(),
        "has_bago_sh":       (path / "bago.sh").is_file(),
        "has_supervisor":    (path / "scripts" / "bago_supervisor.py").is_file(),
        "has_supervisor_pyw":(path / "scripts" / "bago_supervisor.pyw").is_file(),
        "has_probe":         (path / "scripts" / "probe.py").is_file(),
        "has_seal":          (path / "scripts" / "seal_release_415.py").is_file(),
        "has_cli":           (path / "bago_core" / "cli.py").is_file(),
        "release_sig_short": "",
        "supervisor_state":  None,
        "supervisor_alive":  False,
    }
    if not out["exists"]:
        return out
    out["version"] = _read_version(path)
    out["tag"]     = _read_tag(path)
    sig = path / "release.sig"
    if sig.is_file():
        out["release_sig_short"] = _short_sig(sig)
    # supervisor state vive en ~/.bago/state NO en la instalación, pero
    # si la propia instalación tiene su state local, leemos de ahí.
    state = path / "state" / "supervisor.json"
    if not state.is_file():
        state = Path.home() / ".bago" / "state" / "supervisor.json"
    if state.is_file():
        try:
            payload = json.loads(state.read_text(encoding="utf-8"))
            out["supervisor_state"] = {
                "pid":     payload.get("pid"),
                "version": payload.get("version"),
                "started": payload.get("started_at"),
                "events":  payload.get("events", 0),
            }
            out["supervisor_alive"] = bool(payload.get("pid")) and _pid_alive(int(payload["pid"]))
        except Exception as exc:  # noqa: BLE001
            out["supervisor_state"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _scan() -> list[dict[str, Any]]:
    pf  = os.environ.get("ProgramFiles", r"C:\Program Files")
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tmpl, mode, desc in KNOWN_LOCATIONS:
        p = _expand(tmpl.format(pf=pf, home=home))
        if str(p).lower() in seen:
            continue
        seen.add(str(p).lower())
        info = _classify(p)
        info["mode"] = mode if info["exists"] else "missing"
        info["description"] = desc
        results.append(info)
    return results


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    alive = [i for i in items if i.get("supervisor_alive")]
    has_sup = [i for i in items if i.get("has_supervisor")]
    return {
        "scanned_at":   datetime.datetime.now().isoformat(timespec="seconds"),
        "platform":     sys.platform,
        "python":       sys.version.split()[0],
        "home":         str(Path.home()),
        "total_paths":  len(items),
        "existing":     sum(1 for i in items if i["exists"]),
        "missing":      sum(1 for i in items if not i["exists"]),
        "with_supervisor":   len(has_sup),
        "with_supervisor_alive": len(alive),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plain", action="store_true",
                   help="JSON compacto en una sola línea (fácil de copiar a la web)")
    p.add_argument("--active-only", action="store_true",
                   help="Solo listar instalaciones que existen (descarta las que faltan)")
    args = p.parse_args(argv)
    items = _scan()
    if args.active_only:
        items = [i for i in items if i["exists"]]
    payload = {
        "summary": _summary(items),
        "installations": items,
    }
    indent = None if args.plain else 2
    print(json.dumps(payload, indent=indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
