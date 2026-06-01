#!/usr/bin/env python3
"""
verify_default_model.py — BAGO 4.1.5 default_model drift verifier

Falla (exit 1) si alguno de los `config.json` canónicos y los strings en
documentación/scripts no coinciden con un único `default_model`.

Por defecto, el modelo canónico para Express install es `llama3.2:3b`.

Uso:
    python scripts\verify_default_model.py
    python scripts\verify_default_model.py --expected llama3.2:3b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# Rutas canónicas a verificar.
DEFAULT_PATHS = [
    ".bago/config.json",
    ".bago/active/.bago/config.json",
    ".bago/versions/4.1.5/.bago/config.json",
    "BAGO/.bago/config.json",
]

# Strings canónicos en código fuente y documentación.
PYTHON_DEFAULT_RE = re.compile(
    r'("default_model"\s*:\s*")([^"]+)(")'
)
SHELL_DEFAULT_RE = re.compile(
    r'(Read-InputOrDefault[^\n]*?-Default\s+")([^"]+)(")'
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_json_configs(repo: Path, expected: str) -> list[str]:
    failures: list[str] = []
    for rel in DEFAULT_PATHS:
        p = repo / rel
        if not p.exists():
            failures.append(f"[missing] {rel}")
            continue
        try:
            data = _load_json(p)
        except Exception as exc:
            failures.append(f"[parse-error] {rel}: {exc}")
            continue
        actual = data.get("default_model")
        if actual != expected:
            failures.append(
                f"[drift] {rel}: expected={expected!r} actual={actual!r}"
            )
    return failures


def check_config_manager_default(repo: Path, expected: str) -> list[str]:
    failures: list[str] = []
    cm = repo / "BAGO" / ".bago" / "core" / "config_manager.py"
    if not cm.exists():
        failures.append(f"[missing] {cm.relative_to(repo)}")
        return failures
    text = cm.read_text(encoding="utf-8")
    match = PYTHON_DEFAULT_RE.search(text)
    if not match:
        failures.append(f"[no-default_model] {cm.relative_to(repo)}")
    elif match.group(2) != expected:
        failures.append(
            f"[drift] {cm.relative_to(repo)}: expected={expected!r} actual={match.group(2)!r}"
        )
    return failures


def check_launcher_default(repo: Path, expected: str) -> list[str]:
    failures: list[str] = []
    launcher = repo / "BAGO" / "bago_core" / "launcher.py"
    if not launcher.exists():
        return failures
    text = launcher.read_text(encoding="utf-8")
    # Línea ~189: default_model = "llama3.2:3b" (fallback)
    pattern = re.compile(
        r'default_model\s*=\s*"([^"]+)"\s*$',
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        # Solo el fallback duro fuera del install_config.
        line = text[max(0, match.start() - 80):match.end()]
        if "install_config" in line:
            continue
        if match.group(1) != expected:
            failures.append(
                f"[drift] BAGO/bago_core/launcher.py fallback: "
                f"expected={expected!r} actual={match.group(1)!r}"
            )
    return failures


def check_install_v4(repo: Path, expected: str) -> list[str]:
    failures: list[str] = []
    installer = repo / "BAGO" / "install-v4.ps1"
    if not installer.exists():
        return failures
    text = installer.read_text(encoding="utf-8")
    # Filtrar defaults que NO son el default_model canónico de ollama (e.g. codex/copilot).
    for match in SHELL_DEFAULT_RE.finditer(text):
        line = installer.read_text(encoding="utf-8").splitlines()
        # Aproximar el número de línea donde se encontró el match.
        # Buscar la línea que contiene el match.group(0).
        actual = match.group(2)
        # Sólo nos interesa el default_model canónico (ollama-local/cloud por defecto).
        # Identificamos si es ollama o copilot/codex mirando el contexto cercano.
        start = match.start()
        ctx = text[max(0, start - 200):start]
        if "ollama" not in ctx:
            continue
        if actual != expected:
            failures.append(
                f"[drift] BAGO/install-v4.ps1: expected={expected!r} "
                f"actual={actual!r}"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected",
        default="llama3.2:3b",
        help="default_model canónico esperado (default: llama3.2:3b)",
    )
    parser.add_argument(
        "--repo",
        default="C:/Users/AMTEC_Terminal_1º",
        help="raíz del repo a inspeccionar",
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    expected = args.expected

    failures: list[str] = []
    failures += check_json_configs(repo, expected)
    failures += check_config_manager_default(repo, expected)
    failures += check_launcher_default(repo, expected)
    failures += check_install_v4(repo, expected)

    if failures:
        print(f"default_model:DRIFT ({len(failures)} issues)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"default_model:ok ({expected})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
