#!/usr/bin/env python3
"""Run gestor-con-bago's real TypeScript client against BAGO's real dispatcher."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend" / ".bago" / "api")]


def unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gestor", default=str(ROOT.parent / "gestor-con-bago"))
    args = parser.parse_args()
    gestor = Path(args.gestor).resolve()
    if not (gestor / "src" / "api" / "client.integration.test.ts").exists():
        raise SystemExit(f"gestor integration test missing: {gestor}")

    from bridge import BagoAPIServer

    with tempfile.TemporaryDirectory(prefix="bago-gestor-e2e-") as state_dir:
        state_root = Path(state_dir)
        manager = SimpleNamespace(
            state_root=state_root,
            base_path=state_root,
            session_id="gestor-typescript-e2e",
            provider="test",
            model="test",
        )
        server = BagoAPIServer(manager, SimpleNamespace(), port=0, token="")
        server.start()
        environment = os.environ.copy()
        environment["BAGO_E2E_BASE"] = f"http://127.0.0.1:{server.port}"
        environment["BAGO_E2E_DEAD_BASE"] = f"http://127.0.0.1:{unused_local_port()}"
        npm = "npm.cmd" if os.name == "nt" else "npm"
        try:
            result = subprocess.run(
                [npm, "test", "--", "--run", "src/api/client.integration.test.ts"],
                cwd=gestor,
                env=environment,
            )
            return result.returncode
        finally:
            server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
