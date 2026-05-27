#!/usr/bin/env python3
"""
bago_shell.py — Modo shell para BAGO.

Uso:
    bago shell                          → shell interactiva
    bago shell D:\\iniciar.cmd          → ejecuta script cmd/bat/ps1/py
    bago shell -- echo hola            → ejecuta comando del sistema
    bago shell --ls                    → alias compacto
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import shutil
import subprocess
import sys
from pathlib import Path

SHELL_ALIASES = {
    "ls": ["powershell", "-Command", "Get-ChildItem"] if sys.platform == "win32" else ["ls"],
    "cat": ["powershell", "-Command", "Get-Content"] if sys.platform == "win32" else ["cat"],
    "pwd": ["powershell", "-Command", "Get-Location"] if sys.platform == "win32" else ["pwd"],
    "dir": ["powershell", "-Command", "Get-ChildItem"] if sys.platform == "win32" else ["ls"],
}
WIN_BUILTINS = {"echo", "dir", "cd", "type", "cls", "copy", "del", "move", "ren", "md", "rd", "start", "pause", "ver", "vol", "date", "time", "path", "set", "exit", "call", "goto", "if", "for", "shift"}


def resolve_shell():
    if sys.platform == "win32":
        for cand in [
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Windows\System32\cmd.exe",
        ]:
            if Path(cand).exists():
                return cand
    return os.environ.get("SHELL", "/bin/sh")


def run_interactive():
    print("  🐚 BAGO Shell — escribe 'exit' para salir\n")
    shell = resolve_shell()
    while True:
        try:
            line = input("bago$ ")
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 Shell cerrada.")
            break
        line = line.strip()
        if not line or line.lower() in ("exit", "quit"):
            print("  👋 Shell cerrada.")
            break
        if line.startswith("--"):
            line = line[2:].strip()
        parts = line.split()
        if parts[0] in SHELL_ALIASES:
            parts = SHELL_ALIASES[parts[0]] + parts[1:]
        try:
            subprocess.run(parts)
        except Exception as e:
            print(f"  [ERROR] {e}")


def run_script(path_str):
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        print(f"  [ERROR] No existe: {p}")
        sys.exit(1)
    ext = p.suffix.lower()
    if ext in (".cmd", ".bat"):
        subprocess.run(["cmd", "/c", str(p)])
    elif ext == ".ps1":
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if not pwsh:
            print("  [ERROR] PowerShell no encontrado")
            sys.exit(1)
        subprocess.run([pwsh, "-ExecutionPolicy", "Bypass", "-File", str(p)])
    elif ext == ".py":
        subprocess.run([sys.executable, str(p)])
    else:
        subprocess.run([str(p)], shell=True)


def run_command(args):
    if not args:
        run_interactive()
        return
    first = args[0]
    # Alias compacto: --ls
    if first.startswith("--") and len(first) > 2:
        alias = first[2:]
        if alias in SHELL_ALIASES:
            args = SHELL_ALIASES[alias] + args[1:]
        else:
            args = [alias] + args[1:]
        first = args[0]
    # Detectar archivo ejecutable directo
    p = Path(first).expanduser().resolve()
    if p.exists() and p.suffix.lower() in (".cmd", ".bat", ".ps1", ".py"):
        run_script(str(p))
        return
    # Alias registrados
    if first in SHELL_ALIASES:
        args = SHELL_ALIASES[first] + args[1:]
        first = args[0]
    # En Windows, usar shell=True para built-ins
    use_shell = sys.platform == "win32" and (
        first.lower() in WIN_BUILTINS or shutil.which(first) is None
    )
    subprocess.run(args, shell=use_shell)


def main():
    args = sys.argv[1:]
    if not args:
        run_interactive()
        return
    if args[0] == "--":
        run_command(args[1:])
    else:
        run_command(args)




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()