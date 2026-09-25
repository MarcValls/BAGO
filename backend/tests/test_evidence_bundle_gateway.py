from __future__ import annotations

import builtins
import sys
from pathlib import Path

import pytest


def test_public_evidence_bundle_generation_uses_consumed_cli_permit(tmp_path: Path, monkeypatch) -> None:
    from authorization_boundary import AuthorizationError
    import authorization_boundary
    from bago_core.evidence_model import registered_mock_adapter
    from bago_core.evidence_authorized import generate_bundle

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "si")
    monkeypatch.setattr(authorization_boundary, "state_root", lambda: tmp_path / "state")
    output = tmp_path / "reports" / "bundle"
    with registered_mock_adapter():
        manifest = generate_bundle(
            mode="simulated", objective="community-knowledge", output_dir=output,
            provider="mock-contract", model="mock-test", base_path=tmp_path,
            overwrite=False,
        )

    assert manifest == output / "manifest.json"
    assert manifest.is_file()
    assert (output / "report.md").is_file()


def test_public_evidence_bundle_generation_fails_closed_without_tty(tmp_path: Path, monkeypatch) -> None:
    from authorization_boundary import AuthorizationError
    from bago_core.evidence_authorized import generate_bundle

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    output = tmp_path / "bundle"
    with pytest.raises(AuthorizationError, match="TTY"):
        generate_bundle(
            mode="simulated", objective="community-knowledge", output_dir=output,
            provider="mock-contract", model="mock-test", base_path=tmp_path,
            overwrite=False,
        )
    assert not output.exists()
