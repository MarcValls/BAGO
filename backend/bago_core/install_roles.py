#!/usr/bin/env python3
"""Persistent installation role selection for BAGO.

Roles:
- active: copy used by plain `bago`
- dev: development copy used by `bago des`
- launch: main startup copy used by `bago ign`
- writer: copy assigned to writing workflows
- illustrator: copy assigned to visual/illustration workflows
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path
from typing import Any

from bago_core.user_state_paths import install_selection_file, legacy_user_root

ROLES = ("active", "dev", "launch", "writer", "illustrator")
ROLE_LABELS = {
    "active": "Copia activa",
    "dev": "Copia de desarrollo",
    "launch": "Arranque principal",
    "writer": "Escritor",
    "illustrator": "Ilustrador",
}


def selection_file() -> Path:
    return install_selection_file()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path) -> str:
    return str(Path(value).expanduser().resolve())


def _empty() -> dict[str, Any]:
    return {"version": 1, "updated_at": "", "roles": {}}


def load_selection(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else selection_file()
    if path is None and not target.is_file():
        legacy = legacy_user_root() / "install_selection.json"
        if legacy.is_file():
            target = legacy
    if not target.is_file():
        return _empty()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    data.setdefault("version", 1)
    data.setdefault("updated_at", "")
    roles = data.get("roles")
    if not isinstance(roles, dict):
        data["roles"] = {}
    return data


def save_selection(data: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path) if path else selection_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    data["version"] = 1
    data["updated_at"] = _now()
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def role_paths(data: dict[str, Any] | None = None) -> dict[str, str]:
    data = data or load_selection()
    out: dict[str, str] = {}
    for role in ROLES:
        entry = (data.get("roles") or {}).get(role)
        if isinstance(entry, dict) and entry.get("path"):
            out[role] = str(entry["path"])
    return out


def roles_for_path(path: str | Path, data: dict[str, Any] | None = None) -> list[str]:
    needle = _norm_path(path).lower()
    out: list[str] = []
    for role, selected in role_paths(data).items():
        try:
            if _norm_path(selected).lower() == needle:
                out.append(role)
        except Exception:
            continue
    return out


def looks_like_bago(path: str | Path) -> bool:
    root = Path(path)
    return root.is_dir() and (
        (root / "bago_core" / "cli.py").is_file()
        or (root / "bago.ps1").is_file()
        or (root / "bago.cmd").is_file()
    )


def set_role(role: str, path: str | Path, *, strict: bool = True) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"rol no valido: {role}")
    root = Path(path).expanduser()
    if strict and not looks_like_bago(root):
        raise ValueError(f"la ruta no parece una copia BAGO valida: {root}")
    data = load_selection()
    roles = data.setdefault("roles", {})
    roles[role] = {
        "path": _norm_path(root),
        "label": ROLE_LABELS[role],
        "updated_at": _now(),
    }
    written = save_selection(data)
    data["selection_file"] = str(written)
    return data


def clear_role(role: str | None = None) -> dict[str, Any]:
    data = load_selection()
    roles = data.setdefault("roles", {})
    if role:
        if role not in ROLES:
            raise ValueError(f"rol no valido: {role}")
        roles.pop(role, None)
    else:
        roles.clear()
    written = save_selection(data)
    data["selection_file"] = str(written)
    return data


def render_selection(data: dict[str, Any]) -> str:
    lines = ["BAGO INSTALL ROLES", "-" * 40]
    paths = role_paths(data)
    for role in ROLES:
        lines.append(f"{role:11s}: {paths.get(role, '-')}")
    lines.append(f"file   : {data.get('selection_file') or selection_file()}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestiona roles de instalaciones BAGO.")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    sub = parser.add_subparsers(dest="cmd")
    show_p = sub.add_parser("show", help="Muestra roles seleccionados")
    show_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    set_p = sub.add_parser("set", help="Fija un rol a una ruta BAGO")
    set_p.add_argument("--role", required=True, choices=ROLES)
    set_p.add_argument("--path", required=True)
    set_p.add_argument("--no-strict", action="store_true")
    set_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    clear_p = sub.add_parser("clear", help="Borra un rol o todos")
    clear_p.add_argument("--role", choices=ROLES, default="")
    clear_p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "set":
            payload = set_role(args.role, args.path, strict=not args.no_strict)
        elif args.cmd == "clear":
            payload = clear_role(args.role or None)
        else:
            payload = load_selection()
            payload["selection_file"] = str(selection_file())
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        else:
            print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    if args.json:
        payload["ok"] = True
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_selection(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
