"""Guardrails para el arranque portable de BAGO."""
from __future__ import annotations

from pathlib import Path


def test_launcher_forces_portable_user_home():
    launcher = Path(__file__).resolve().parents[3] / "bago_core" / "launcher.py"
    text = launcher.read_text(encoding="utf-8")

    assert 'os.environ["BAGO_USER_HOME"] = str(DEFAULT_USER_BAGO)' in text
    assert "setdefault(\"BAGO_USER_HOME\"" not in text


def test_portable_entry_clears_credential_env_and_sets_user_roots():
    bago_ps1 = Path(__file__).resolve().parents[3] / "bago.ps1"
    text = bago_ps1.read_text(encoding="utf-8")

    assert "$env:BAGO_USER_HOME = $portableUserHome" in text
    assert "$env:BAGO_USER_DIR = $portableUserHome" in text
    assert "$env:BAGO_STATE_ROOT = $portableUserHome" in text
    assert "Reset-BagoCredentialEnv" in text
    assert "Clear-BagoColdStartCredentials" in text
    assert "$script:CREDENTIAL_FILES" in text
    assert "Resolve-BagoModelsDir" in text
    assert "$env:OLLAMA_MODELS" in text
    assert "REPLICATE_API_TOKEN" in text
    assert "OPENAI_API_KEY" in text
    assert "$HasDevice -or -not $UserHome -or $script:COLD_START_CREDENTIALS_CLEARED" in text


def test_no_device_branch_is_local_not_portable():
    bago_ps1 = Path(__file__).resolve().parents[3] / "bago.ps1"
    text = bago_ps1.read_text(encoding="utf-8")

    assert "$script:BAGO_DEVICE_PRESENT" in text
    assert "$script:COLD_START_CREDENTIALS_CLEARED" in text
    assert "Fuente de verdad: $usbPath (LOCAL)" in text
    assert "Fuente de verdad: $usbPath (PENDRIVE)" in text
