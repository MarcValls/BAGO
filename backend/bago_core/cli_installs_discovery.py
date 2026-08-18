#!/usr/bin/env python3
"""FASE 6.4: discovery logic for BAGO installations.

Walks the known locations plus the user-selected roles, classifies each
candidate path, and returns a flat list of installation dicts.

R0-R10:
- R0: <200 lines
- R1: imports from cli_installs_facts and cli_installs_state
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bago_core.install_roles import ROLES, load_selection, role_paths, roles_for_path
from bago_core.cli_installs_facts import (
    read_tag,
    read_version,
    short_sig,
    supervisor_state,
)
from bago_core.user_state_paths import user_root, legacy_user_root


KNOWN_LOCATIONS: list[tuple[str, str, str]] = [
    # (path_template, mode, description)
    ("{pf}\\BAGO",                                            "system",  "Instalacion de sistema"),
    ("{user}\\active",                                         "work",    "Active / work"),
    ("{user}\\launch",                                         "ign",     "Ignition / launch"),
    ("{user}\\dev",                                            "dev",     "Dev tree (user)"),
    ("{legacy}\\active",                                       "work",    "Legacy active / work"),
    ("{legacy}\\launch",                                       "ign",     "Legacy ignition / launch"),
    ("{legacy}\\dev",                                          "dev",     "Legacy dev tree"),
    ("{legacy}",                                               "user",    "Legacy user root"),
    ("{home}\\BAGO",                                           "source",  "Source tree"),
]

EXTRA_HINTS = ["bago.ps1", "bago.cmd", "bago.sh", "release_version.txt"]


def _expand(p: str) -> Path:
    return Path(os.path.expandvars(p)).expanduser()


def _classify(path: Path) -> dict[str, Any]:
    """Return a dict of metadata for the given installation path."""
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
        "has_cli":           (path / "bago_core" / "cli.py").is_file(),
        "release_sig_short": "",
        "supervisor_state":  None,
        "supervisor_alive":  False,
    }
    if not out["exists"]:
        return out
    out["version"] = read_version(path)
    out["tag"]     = read_tag(path)
    sig = path / "release.sig"
    if sig.is_file():
        out["release_sig_short"] = short_sig(sig)
    state, alive = supervisor_state(path)
    out["supervisor_state"] = state
    out["supervisor_alive"] = alive
    return out


def _scan() -> list[dict[str, Any]]:
    """Scan the known locations and the user-selected roles."""
    pf = os.environ.get("ProgramFiles", "").strip()
    if not pf:
        pf = str(Path.home() / "AppData" / "Local" / "Programs")
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    user = str(user_root())
    legacy = str(legacy_user_root())
    selection = load_selection()
    selected_paths = role_paths(selection)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_path(path: Path, mode: str, desc: str) -> None:
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        info = _classify(path)
        info["mode"] = mode if info["exists"] else "missing"
        info["description"] = desc
        roles = roles_for_path(path, selection)
        info["selection_roles"] = roles
        for role in ROLES:
            info[f"selected_{role}"] = role in roles
        results.append(info)

    for tmpl, mode, desc in KNOWN_LOCATIONS:
        p = _expand(tmpl.format(pf=pf, home=home, user=user, legacy=legacy))
        add_path(p, mode, desc)
    role_to_mode = {
        "active": "work",
        "dev": "dev",
        "launch": "ign",
        "writer": "manual",
        "illustrator": "manual",
    }
    for role, selected in selected_paths.items():
        add_path(Path(selected), role_to_mode.get(role, "manual"), f"Seleccion {role}")
    return results
