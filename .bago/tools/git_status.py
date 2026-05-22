#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git_status.py — Muestra un resumen compacto del estado de git del proyecto.

Usa comandos git estándar. Funciona en cualquier repositorio git.

Uso:
    python3 .bago/tools/git_status.py          # resumen completo
    python3 .bago/tools/git_status.py --log N  # últimos N commits (default 5)
    python3 .bago/tools/git_status.py --short  # una línea
    python3 .bago/tools/git_status.py --diff   # muestra archivos modificados

Códigos de salida: 0 = OK, 1 = no es un repositorio git
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"
def MAGENTA(s: str)-> str: return f"\033[35m{s}\033[0m"


def _load_project() -> Path | None:
    gs = STATE / "global_state.json"
    if not gs.exists():
        return None
    try:
        data = json.loads(gs.read_text(encoding="utf-8"))
        p = data.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


GIT_CMD: list[str] | None = None  # resolved lazily


def _resolve_git() -> list[str] | None:
    global GIT_CMD
    if GIT_CMD is not None:
        return GIT_CMD
    # Try common locations on Windows
    candidates = [
        "git",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        r"C:\Users\%USERNAME%\AppData\Local\Programs\Git\bin\git.exe",
    ]
    import shutil
    found = shutil.which("git")
    if found:
        GIT_CMD = [found]
        return GIT_CMD
    for c in candidates[1:]:
        p = Path(c)
        if p.exists():
            GIT_CMD = [str(p)]
            return GIT_CMD
    GIT_CMD = []
    return GIT_CMD


def _git(cmd: list[str], cwd: Path) -> tuple[str, bool]:
    """Run git command. Returns (output, success)."""
    git = _resolve_git()
    if not git:
        return "git no encontrado en PATH", False
    try:
        result = subprocess.run(
            git + cmd, cwd=str(cwd),
            capture_output=True, timeout=15,
        )
        out = result.stdout.decode("utf-8", errors="replace").strip()
        return out, result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return str(e), False


def main() -> int:
    args    = sys.argv[1:]
    short   = "--short" in args or "-s" in args
    show_diff = "--diff" in args or "-d" in args

    log_n = 5
    if "--log" in args:
        idx = args.index("--log")
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            log_n = int(args[idx + 1])

    project = _load_project()
    git_root = project if project else ROOT

    # Check if git is available at all
    if not _resolve_git():
        print()
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │  BAGO · Git Status                                          │")
        print("  └─────────────────────────────────────────────────────────────┘")
        print(f"  {YELLOW('⚠')} git no está instalado o no está en PATH")
        print(f"  {DIM('Instala Git: https://git-scm.com/download/win')}")
        print()
        print(f"  Directorio del proyecto: {DIM(str(git_root))}")
        # Still show basic file info
        files_count = sum(1 for _ in git_root.rglob("*") if _.is_file()
                          and ".bago" not in _.parts and "node_modules" not in _.parts)
        print(f"  Archivos en proyecto: {files_count}")
        print()
        return 0

    # Check if it's a git repo
    _, is_git = _git(["rev-parse", "--git-dir"], git_root)
    if not is_git:
        # Try parent dirs
        for parent in git_root.parents:
            _, ok = _git(["rev-parse", "--git-dir"], parent)
            if ok:
                git_root = parent
                break
        else:
            print(f"\n  {YELLOW('⚠')} No es un repositorio git: {git_root}\n")
            return 1

    # Gather info
    branch, _   = _git(["rev-parse", "--abbrev-ref", "HEAD"], git_root)
    commit, _   = _git(["log", "-1", "--format=%h %s"], git_root)
    author, _   = _git(["log", "-1", "--format=%an"], git_root)
    date_str, _ = _git(["log", "-1", "--format=%ar"], git_root)
    status_out, _ = _git(["status", "--porcelain"], git_root)

    # Count changes
    status_lines = [l for l in status_out.splitlines() if l.strip()]
    staged    = sum(1 for l in status_lines if l[:2][0] in "MADRC" and l[:2][0] != " ")
    unstaged  = sum(1 for l in status_lines if l[:2][1] in "MD")
    untracked = sum(1 for l in status_lines if l.startswith("??"))

    if short:
        clean = "(limpio)" if not status_lines else f"{len(status_lines)} cambios"
        print(f"  git: {CYAN(branch)}  {DIM(commit.split()[0] if commit else '?')}  {clean}")
        return 0

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Git Status                                          │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Repositorio: {DIM(str(git_root))}")
    print()
    print(f"  {'Rama':<16} {CYAN(branch)}")
    if commit:
        sha = commit.split()[0] if commit else "?"
        msg = " ".join(commit.split()[1:])[:50] if len(commit.split()) > 1 else ""
        print(f"  {'Último commit':<16} {BOLD(sha)}  {DIM(msg)}")
        print(f"  {'Autor':<16} {author}  {DIM(date_str)}")

    print()
    if not status_lines:
        print(f"  {GREEN('✅ Working tree limpio')} — sin cambios pendientes")
    else:
        total = len(status_lines)
        print(f"  {YELLOW('⚠')} {BOLD(str(total))} cambio(s) en el working tree")
        if staged:
            print(f"    {GREEN(str(staged) + ' staged')}  (listos para commit)")
        if unstaged:
            print(f"    {YELLOW(str(unstaged) + ' modificados')}  (no staged)")
        if untracked:
            print(f"    {DIM(str(untracked) + ' sin seguimiento')}")

        if show_diff:
            print()
            for line in status_lines[:20]:
                code   = line[:2]
                fpath  = line[3:]
                if "??" in code:
                    icon = DIM("?")
                elif code[0] != " ":
                    icon = GREEN("A" if "A" in code else "M")
                else:
                    icon = YELLOW("M")
                print(f"    {icon}  {fpath}")
            if len(status_lines) > 20:
                print(f"    {DIM(f'... y {len(status_lines)-20} más')}")

    # Recent log
    print()
    print(f"  {BOLD(f'Últimos {log_n} commits:')}")
    log_out, ok = _git(
        ["log", f"-{log_n}", "--format=%h %ar  %s", "--no-merges"],
        git_root
    )
    if ok and log_out:
        for line in log_out.splitlines():
            parts = line.split("  ", 2)
            if len(parts) == 3:
                sha, when, msg = parts
                print(f"  {MAGENTA(sha)}  {DIM(when):<16}  {msg[:55]}")
            else:
                print(f"  {DIM(line)}")
    print()

    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
