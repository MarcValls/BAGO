#!/usr/bin/env python3
"""bago_update.py — actualiza componentes conocidos y repara incompatibilidades.

Uso:
    bago update [--yes] [--dry-run] [--test]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _info(msg: str) -> None:
    print(f"  -> {msg}")


def _ok(msg: str) -> None:
    print(f"  OK {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN {msg}")


def _err(msg: str) -> None:
    print(f"  ERR {msg}")


def _run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool = False, timeout: int = 300) -> int:
    shown = " ".join(cmd)
    _info(shown)
    if dry_run:
        return 0
    try:
        proc = subprocess.run(cmd, cwd=str(cwd or PROJECT_ROOT), timeout=timeout)
        return proc.returncode
    except subprocess.TimeoutExpired:
        _err(f"timeout: {shown}")
        return 124
    except Exception as exc:
        _err(f"{shown}: {exc}")
        return 1


def _ollama_models() -> list[str]:
    ollama = shutil.which("ollama")
    if not ollama:
        return []
    try:
        proc = subprocess.run([ollama, "list"], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
    except Exception:
        return []
    models: list[str] = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        model = line.split()[0].strip()
        if model and model.upper() != "NAME":
            models.append(model)
    seen: set[str] = set()
    unique: list[str] = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique.append(model)
    return unique


def _confirm() -> bool:
    try:
        answer = input("Buscar versiones nuevas, instalarlas y reparar incompatibilidades? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes", "s", "si"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    assume_yes = "--yes" in argv

    if "--test" in argv:
        required = [
            TOOLS_DIR / "outdated_check.py",
            TOOLS_DIR / "deps_check.py",
            TOOLS_DIR / "auto_heal.py",
            TOOLS_DIR / "env.py",
            Path(__file__),
        ]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            _err("faltan archivos: " + ", ".join(missing))
            return 1
        _ok("self-test OK")
        return 0

    print()
    print("  BAGO Update")
    print("  ----------------------------------------------")

    if not dry_run and not assume_yes and not _confirm():
        _warn("cancelado")
        return 0

    failures = 0
    models = _ollama_models()
    if models:
        _info(f"modelos locales detectados: {', '.join(models)}")
        ollama = shutil.which("ollama") or "ollama"
        for model in models:
            rc = _run([ollama, "pull", model], dry_run=dry_run, timeout=1800)
            if rc != 0:
                failures += 1
    else:
        _warn("sin modelos locales activos; no hay pulls que ejecutar")

    rc = _run([PYTHON, str(TOOLS_DIR / "outdated_check.py")], dry_run=dry_run, timeout=180)
    if rc not in (0, 1):
        failures += 1

    deps_args = [PYTHON, str(TOOLS_DIR / "deps_check.py")]
    if not dry_run:
        deps_args.append("--install")
    rc = _run(deps_args, dry_run=dry_run, timeout=300)
    if rc not in (0, 1, 2):
        failures += 1

    heal_args = [PYTHON, str(TOOLS_DIR / "auto_heal.py"), "--dry-run" if dry_run else "--fix"]
    rc = _run(heal_args, dry_run=False, timeout=300)
    if rc != 0:
        failures += 1

    rc = _run([PYTHON, str(TOOLS_DIR / "env.py"), "check"], dry_run=dry_run, timeout=180)
    if rc not in (0, 1):
        failures += 1

    if failures:
        _warn(f"update finalizado con incidencias: {failures}")
        return 1
    _ok("update finalizado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
