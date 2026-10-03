#!/usr/bin/env python3
"""CI-only clean-install launcher through BAGO's governed install owner.

This is test harness code, not a user-facing authorization bypass. It refuses
to run outside GitHub Actions and only accepts a destination below RUNNER_TEMP.
Production installation continues to require the normal interactive Manager
flow.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]

from authorization_boundary import AuthorizationBoundary  # noqa: E402
from execution_adapter_contract import ExecutionContext  # noqa: E402
from execution_gateway import ExecutionGateway  # noqa: E402
from execution_request import build_execution_request  # noqa: E402
from install_plan import build_install_plan  # noqa: E402


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _configuration() -> dict:
    return {
        "providers": {
            "ollama-local": {
                "enabled": True,
                "base_url": "http://127.0.0.1:11434",
                "model": "llama3.2:3b",
            },
            "codex": {
                "enabled": False,
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-5.4-mini",
            },
            "copilot": {
                "enabled": False,
                "base_url": "https://api.githubcopilot.com",
                "api_key": "",
                "auth_mode": "device-flow",
                "model": "gpt-4o-copilot",
            },
            "ollama-cloud": {
                "enabled": False,
                "base_url": "",
                "api_key": "",
                "auth_mode": "signin",
                "model": "llama3.2:3b",
            },
        },
        "knowledge": {
            "mode": "none",
            "path": "",
            "visibility": "private",
            "git_init": False,
        },
        "credential_store": {
            "mode": "session",
            "path": "",
            "encrypted": False,
            "scope": "session",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("install", "repair"), required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--mode", default="Express")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        raise SystemExit("clean-install gateway harness is CI-only")

    runner_temp_raw = os.environ.get("RUNNER_TEMP", "").strip()
    if not runner_temp_raw:
        raise SystemExit("RUNNER_TEMP is required")
    runner_temp = Path(runner_temp_raw).resolve()
    source_root = Path(args.source_root).resolve()
    install_dir = Path(args.install_dir).resolve()
    if not _under(install_dir, runner_temp):
        raise SystemExit("clean-install destination must stay under RUNNER_TEMP")
    if source_root != BACKEND_ROOT.resolve():
        raise SystemExit("clean-install source must be the checked-out backend root")

    helper = source_root / "install-v4.ps1"
    configuration = _configuration()
    options = {
        "skip_tests": bool(args.skip_tests),
        "no_path_update": True,
        "no_shell_integration": True,
        "preserve_dev_role": False,
        "explorer_context_menu": False,
    }
    target = build_install_plan(
        action=args.action,
        source_root=str(source_root),
        helper_path=str(helper),
        install_dir=str(install_dir),
        mode=args.mode,
        options=options,
        configuration=configuration,
    )

    session_id = "ci-clean-install-" + uuid.uuid4().hex
    interaction_id = "ci-clean-install-interaction-" + uuid.uuid4().hex
    manager = SimpleNamespace(session_id=session_id, base_path=str(source_root))
    request = build_execution_request(
        effect_id="system.install.apply",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=session_id,
        source_surface="api.install.apply",
        target=target,
        arguments={"configuration": configuration},
        scope="system",
        world_state_authority=manager,
    )
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id=interaction_id)

    # CI simulates the Manager's already-tested desktop confirmation only
    # inside the disposable runner. This harness cannot target a non-temporary
    # installation and is not reachable from product surfaces.
    with patch("authorization_boundary.confirm_strong_challenge", return_value=True):
        approval = boundary.approve_challenge(
            challenge_id=challenge["challenge_id"],
            interaction_id=interaction_id,
            session_id=session_id,
            channel="desktop",
        )
    result, authorization = ExecutionGateway(boundary).execute(
        permit_token=str(approval["permit"]["token"]),
        request=request,
        context=ExecutionContext(manager=manager),
    )
    if not result.get("ok") or result.get("status") != "completed":
        raise SystemExit("governed clean-install execution did not complete")
    print(json.dumps({
        "ok": True,
        "effect_id": result.get("effect_id"),
        "status": result.get("status"),
        "receipt_id": result.get("receipt_id"),
        "permit_id": authorization.get("permit_id"),
        "operation_fingerprint": authorization.get("operation_fingerprint"),
        "install_dir": str(install_dir),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
