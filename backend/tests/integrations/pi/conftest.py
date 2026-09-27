"""conftest.py para tests/integrations/pi.

Hace que `import integrations.pi` funcione tanto cuando los tests se
ejecutan desde la raíz del repo (sin instalar el paquete) como cuando
se ejecutan vía `pytest` con `rootdir=backend`.
"""
from __future__ import annotations

import sys
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # .../backend
BAGO_ROOT = REPO_ROOT / ".bago"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(BAGO_ROOT))


def run_fake_sidecar(spec, *, stdin_payload=None, sidecar_artifact_hash="", cancel_token=None):
    """Test-only process harness for protocol shims; production remains canonical-only."""
    from integrations.pi.errors import BridgeTimeout

    env = dict(spec.env)
    with tempfile.TemporaryDirectory(prefix="bago-pi-test-home-", dir=spec.home_parent) as home:
        env["HOME"] = home
        env["USERPROFILE"] = home
        process = subprocess.Popen(
            list(spec.argv), cwd=spec.cwd, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", shell=False,
        )
        output = []
        worker = threading.Thread(
            target=lambda: output.append(process.communicate(input=stdin_payload)), daemon=True
        )
        worker.start()
        deadline = time.monotonic() + spec.timeout_seconds
        cancelled = False
        while worker.is_alive() and time.monotonic() < deadline:
            if cancel_token is not None and cancel_token.is_cancelled():
                cancelled = True
                break
            worker.join(0.025)
        timed_out = worker.is_alive() and not cancelled
        if cancelled or timed_out:
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        worker.join(2)
        if timed_out:
            raise BridgeTimeout("test sidecar timeout")
        if worker.is_alive():
            process.kill()
            process.wait()
            worker.join()
        stdout, stderr = output[0] if output else ("", "")
        return subprocess.CompletedProcess(list(spec.argv), process.returncode, stdout, stderr)


@pytest.fixture(autouse=True)
def _fake_sidecars_are_test_only(monkeypatch):
    from integrations.pi import agent_runner
    from integrations.pi.process_boundary import run_sidecar as gateway_run_sidecar

    canonical = (BAGO_ROOT / "integrations" / "pi" / "sidecar" / "src" / "main.js").resolve()

    def dispatch(spec, **kwargs):
        script = Path(spec.argv[1]).resolve() if len(spec.argv) == 2 else None
        if script == canonical:
            return gateway_run_sidecar(spec, **kwargs)
        return run_fake_sidecar(spec, **kwargs)

    monkeypatch.setattr(agent_runner, "run_sidecar", dispatch)
