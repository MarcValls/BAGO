#!/usr/bin/env python3
"""bago.api.services.launcher — Arranca todos los proxies BAGO.

Usage:
    python -m bago.api.services.launcher           # todos
    python -m bago.api.services.launcher --only bago copilot  # solo esos
    python -m bago.api.services.launcher --list     # ver puertos
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import signal
import os
from pathlib import Path

SERVICES = {
    "bago": {
        "module": "bago.api.server:app",
        "port": 11435,
        "desc": "Orquestador BAGO",
    },
    "copilot": {
        "module": "bago.api.services.copilot:app",
        "port": 11436,
        "desc": "Copilot (GitHub Models)",
    },
    "codex": {
        "module": "bago.api.services.codex:app",
        "port": 11437,
        "desc": "Codex (OpenAI)",
    },
    "ollama-cloud": {
        "module": "bago.api.services.ollama_cloud:app",
        "port": 11438,
        "desc": "Ollama Cloud",
    },
    "telegram-bot": {
        "module": "bago.api.services.telegram_bot",
        "port": 11439,
        "desc": "Bot de Telegram para BAGO",
    },
    "utopia-bot": {
        "module": "bago.api.services.utopia_bot",
        "port": 11440,
        "desc": "Cliente Utopia para BAGO",
    },
}

processes = []


def launch_service(name: str, config: dict, host: str = "127.0.0.1") -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "uvicorn",
        config["module"],
        "--host", host,
        "--port", str(config["port"]),
    ]
    print(f"  [{name}] Arrancando en :{config['port']} — {config['desc']}")
    proc = subprocess.Popen(cmd)
    return proc


def check_deps():
    try:
        import fastapi
        import uvicorn
    except ImportError:
        print("Falta dependencias. Instala con:")
        print("  pip install fastapi uvicorn")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="BAGO Services Launcher")
    parser.add_argument("--only", nargs="+", choices=list(SERVICES.keys()),
                        help="Arranca solo estos servicios")
    parser.add_argument("--list", action="store_true", help="Lista servicios y puertos")
    parser.add_argument("--host", default="127.0.0.1", help="Host para bind")
    args = parser.parse_args()

    # Ensure bago tools is in path
    tools_dir = str(Path(__file__).resolve().parent.parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    if args.list:
        print("\n  BAGO Services\n  ==============\n")
        print(f"  {'Servicio':<16} {'Puerto':<8} {'Descripción'}")
        print(f"  {'-'*16} {'-'*8} {'-'*30}")
        print(f"  {'ollama-local':<16} {'11434':<8} Ollama local (nativo)")
        for name, cfg in SERVICES.items():
            print(f"  {name:<16} {cfg['port']:<8} {cfg['desc']}")
        print()
        return

    check_deps()

    targets = {k: v for k, v in SERVICES.items() if args.only is None or k in args.only}

    print("\n  BAGO Services Launcher\n  =======================\n")

    for name, config in targets.items():
        proc = launch_service(name, config, args.host)
        processes.append((name, proc))

    print(f"\n  {len(processes)} servicio(s) arrancados. Ctrl+C para parar.\n")

    def shutdown(sig, frame):
        print("\n  Parando servicios...")
        for name, proc in processes:
            proc.terminate()
        for name, proc in processes:
            proc.wait(timeout=5)
        print("  Todos parados.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            for name, proc in list(processes):
                if proc.poll() is not None:
                    print(f"  [{name}] Terminado con código {proc.returncode}")
                    processes.remove((name, proc))
            if not processes:
                print("  Todos los servicios terminados.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
