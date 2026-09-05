"""Contract for the read-only signing environment preflight script."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-signing-preflight.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "build-release-installer.yml"


def test_preflight_checks_every_value_the_workflow_gate_requires() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for name in (
        "AZURE_CLIENT_ID",
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "BAGO_SIGNING_ENDPOINT",
        "BAGO_SIGNING_ACCOUNT",
        "BAGO_SIGNING_PROFILE",
        "BAGO_SIGNING_PUBLISHER",
    ):
        assert f'"{name}"' in source
        assert name in workflow

    assert "release-signing" in source
    assert "environment_exists" in source
    assert '"bago.signing-preflight.v1"' in source


def test_preflight_is_read_only_and_never_prints_secret_values() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-GhCapture" in source
    assert '$ErrorActionPreference = "Continue"' in source
    assert "& gh @Arguments 2>&1" in source
    assert '@("secret", "list", "-R", $Repository)' in source
    assert '"repos/$Repository/environments/$Environment/secrets"' in source
    assert '"repos/$Repository/environments/$Environment/variables"' in source
    for write_verb in ("gh secret set", "gh variable set", "--method POST", "--method PUT", "--method PATCH"):
        assert write_verb not in source
    assert "never prints secret values" in source


def test_preflight_fails_closed_when_anything_is_missing() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'throw "gh CLI no está disponible' in source
    assert "exit 1" in source
    assert "ready = ($failures.Count -eq 0)" in source
