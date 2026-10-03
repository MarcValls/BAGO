"""In-process MSIX bootstrap checks and canonical BAGO session initialization."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


_SESSION_MANAGER = None
_INSTALL_REQUEST = None
_INSTALL_INTERACTION_ID = "msix-bootstrap-install"


def verify_loaded_authority(authority_root: str, release_manifest_sha256: str) -> None:
    root = Path(authority_root).resolve(strict=True)
    manifest_path = root.parent / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if digest.lower() != str(release_manifest_sha256).lower():
        raise RuntimeError("Authenticated release manifest identity mismatch")
    if manifest.get("schema") != "bago.release-manifest.v1":
        raise RuntimeError("Unsupported BAGO release manifest")
    for module_name in ("authorization_boundary", "execution_gateway", "session_manager"):
        module = __import__(module_name)
        module_path = Path(module.__file__).resolve(strict=True)
        if root not in module_path.parents:
            raise RuntimeError(f"BAGO authority module loaded outside the package: {module_name}")


def create_bootstrap_session(state_root: str) -> str:
    """Initialize the canonical manager in-process with mirrors explicitly disabled."""
    global _SESSION_MANAGER
    os.environ["BAGO_SESSION_MIRROR"] = "0"
    os.environ["BAGO_STATE_ROOT"] = str(Path(state_root).resolve())
    from session_manager import SessionManager

    manager = SessionManager(
        provider="ollama-cloud",
        model="bootstrap",
        base_path=str(Path(os.environ["LOCALAPPDATA"]).resolve()),
        state_root=os.environ["BAGO_STATE_ROOT"],
    )
    _SESSION_MANAGER = manager
    return str(_SESSION_MANAGER.session_id)


def install_from_package(package_root: str, publisher: str, package_payload_sha256: str) -> str:
    """Run first install through the canonical authority and return evidence."""
    global _INSTALL_REQUEST
    if _SESSION_MANAGER is None:
        raise RuntimeError("BAGO bootstrap session is not initialized")
    from authorization_boundary import AuthorizationBoundary
    from execution_adapter_contract import ExecutionContext
    from execution_gateway import ExecutionGateway
    from execution_request import build_execution_request
    from install_plan import build_install_plan

    root = Path(package_root).resolve(strict=True)
    source = root / "payload"
    helper = source / "backend" / "install-v4.ps1"
    target = Path(os.environ.get("LOCALAPPDATA", str(root))) / "BAGO"
    configuration = {
        "providers": {
            "ollama-local": {"enabled": False, "base_url": "", "model": ""},
            "codex": {"enabled": False, "base_url": "", "api_key": "", "model": ""},
            "copilot": {"enabled": False, "base_url": "", "api_key": "", "auth_mode": "device-flow", "model": ""},
            "ollama-cloud": {"enabled": False, "base_url": "", "api_key": "", "auth_mode": "signin", "model": ""},
        },
        "knowledge": {"mode": "none", "path": "", "visibility": "private", "git_init": False},
        "credential_store": {"mode": "session", "path": "", "encrypted": True, "scope": "session"},
    }
    plan = build_install_plan(
        action="install", source_root=str(source), helper_path=str(helper),
        install_dir=str(target), mode="Express", options={
            "skip_tests": True, "no_path_update": False,
            "no_shell_integration": False, "preserve_dev_role": False,
            "explorer_context_menu": False,
        }, configuration=configuration, package_digest=str(package_payload_sha256),
    )
    request = build_execution_request(
        effect_id="system.install.apply", actor_kind="user",
        principal_id="interactive-local-user", session_id=str(_SESSION_MANAGER.session_id),
        source_surface="msix.bootstrap.install", target=plan,
        arguments={"configuration": configuration}, scope="system",
        world_state_authority=_SESSION_MANAGER,
    )
    boundary = AuthorizationBoundary()
    challenge = boundary.create_challenge(request, interaction_id=_INSTALL_INTERACTION_ID)
    authorization = boundary.approve_challenge(
        challenge_id=str(challenge["challenge_id"]),
        interaction_id=_INSTALL_INTERACTION_ID,
        session_id=str(_SESSION_MANAGER.session_id), channel="desktop",
    )
    permit = authorization.get("permit", {})
    result, consumed = ExecutionGateway(boundary).execute(
        permit_token=str(permit.get("token") or ""), request=request,
        context=ExecutionContext(manager=_SESSION_MANAGER),
    )
    _INSTALL_REQUEST = request
    result["authorization"] = {
        "state": "consumed", "permit_id": consumed.get("permit_id"),
        "operation_fingerprint": consumed.get("operation_fingerprint"),
    }
    return json.dumps(result, ensure_ascii=False, sort_keys=True)
