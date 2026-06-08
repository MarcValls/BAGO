#!/usr/bin/env python3
"""
deploy_landing.py — Despliega la landing page de BAGO a Vercel.

Uso:
    python scripts/deploy_landing.py [--prod] [--yes] [--token TOKEN]

Requiere:
    - vercel CLI instalado globalmente: npm i -g vercel
    - Sesión activa con vercel login, o un token con --token
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


VERCEL_CMD = Path.home() / "AppData" / "Roaming" / "npm" / "vercel.cmd"


def resolve_vercel_cmd():
    found = shutil.which("vercel")
    if found:
        return found
    if VERCEL_CMD.exists():
        return str(VERCEL_CMD)
    raise FileNotFoundError("vercel CLI no encontrado. Instálalo con: npm i -g vercel")


def deploy(prod: bool = False, yes: bool = False, token: str = "") -> str:
    repo_root = Path(__file__).resolve().parents[1]
    vercel = resolve_vercel_cmd()
    cmd = [vercel, str(repo_root)]
    if prod:
        cmd.append("--prod")
    if yes:
        cmd.append("--yes")
    if token:
        cmd.extend(["--token", token])

    print(f"[deploy_landing] Ejecutando: {' '.join(cmd[:2])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    # Buscar URL
    for line in result.stdout.splitlines():
        if line.startswith("https://") and "vercel.app" in line:
            print(f"[deploy_landing] URL: {line}")
            return line
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Despliega la landing page de BAGO a Vercel")
    parser.add_argument("--prod", action="store_true", help="Despliega a producción")
    parser.add_argument("--yes", action="store_true", help="Confirma automáticamente")
    parser.add_argument("--token", default="", help="Token de Vercel (opcional, evita vercel login)")
    args = parser.parse_args()
    deploy(prod=args.prod, yes=args.yes, token=args.token)


if __name__ == "__main__":
    main()
