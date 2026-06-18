#!/usr/bin/env python3
"""
deploy_landing.py — Despliega la landing page de BAGO a Vercel.

Uso:
    python scripts/deploy_landing.py [--prod] [--yes]

Requiere:
    - vercel CLI instalado globalmente: npm i -g vercel
    - Sesión activa con vercel login
"""

import argparse
import subprocess
import sys
import shutil
from pathlib import Path


def deploy(prod: bool = False, yes: bool = False) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    # La landing está en la raíz (index.html + vercel.json)
    vercel_bin = shutil.which("vercel.cmd") or shutil.which("vercel") or "vercel"
    cmd = [vercel_bin, str(repo_root)]
    if prod:
        cmd.append("--prod")
    if yes:
        cmd.append("--yes")

    print(f"[deploy_landing] Ejecutando: {' '.join(cmd)}")
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
    args = parser.parse_args()
    deploy(prod=args.prod, yes=args.yes)


if __name__ == "__main__":
    main()
