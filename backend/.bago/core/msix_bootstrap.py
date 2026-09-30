"""In-process MSIX bootstrap checks and canonical BAGO session initialization."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


_SESSION_MANAGER = None


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
