"""Regression contracts for retained legacy manager compatibility surfaces."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_installation_cards_do_not_reference_undefined_seal_badge():
    source = (ROOT / "manager" / "js" / "legacy-manager.js").read_text(encoding="utf-8")
    assert "sealBadge" not in source


def test_provider_endpoint_awaits_electron_manager_url():
    source = (ROOT / "manager" / "js" / "core.js").read_text(encoding="utf-8")
    assert "async function pmManagerBaseUrl()" in source
    assert "await api.getManagerUrl()" in source
    assert "async function pmProvidersEndpoint()" in source
    assert "await pmManagerBaseUrl()" in source
    assert "const endpoint=await pmProvidersEndpoint()" in source
