from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


def _make_manager(tmp_path: str, workspace: str):
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse
    import session_manager as sm

    class ValidatorAdapter(ProviderAdapter):
        def __init__(self, config=None):
            super().__init__("validator-provider", config)

        def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
            return ProviderResponse(
                content="ok",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=None,
            )

        def list_models(self):
            return [ModelInfo("validator-model", "validator-model", self.provider_name, 8192, 1024, "test", "free")]

        def health_check(self, timeout=5.0):
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok", latency_ms=1.0)

        def is_configured(self):
            return True

        def supports_tools(self):
            return False

        def supports_streaming(self):
            return False

    sm.ADAPTER_REGISTRY["validator-provider"] = ValidatorAdapter
    mgr = sm.SessionManager(
        session_id="validator-test",
        provider="validator-provider",
        model="validator-model",
        base_path=workspace,
        state_root=tmp_path,
    )
    return mgr, sm


def test_receipt_validator_certifies_and_detects_mutation():
    from context_receipt_validator import ContextReceiptValidator

    with tempfile.TemporaryDirectory() as td:
        workspace = tempfile.mkdtemp()
        mgr, sm = _make_manager(td, workspace)
        try:
            mgr.set_goal("Validar receipts")
            mgr.send("hola")
            receipt = mgr.last_receipt
            assert receipt is not None

            validator = ContextReceiptValidator()
            report = validator.validate(
                receipt,
                expected_workspace=str(mgr.base_path),
                expected_workspace_state_root=str(Path(workspace) / ".gabo"),
                expected_provider="validator-provider",
                expected_model="validator-model",
                expected_context_revision=mgr.context_revision,
                expected_session_id=mgr.session_id,
                expected_session_summary={
                    "session_id": mgr.session_id,
                    "workspace_state_root": str(Path(workspace) / ".gabo"),
                    "authorized_root": str(mgr.base_path),
                    "provider": "validator-provider",
                    "model": "validator-model",
                    "bago_mode": mgr.bago_mode,
                    "objective": "Validar receipts",
                },
            )
            assert report.ok is True
            assert report.assurance_state == "certified"

            receipt.provider_used = "mutated-provider"
            mutated = validator.validate(
                receipt,
                expected_workspace=workspace,
                expected_provider="validator-provider",
                expected_model="validator-model",
                expected_context_revision=mgr.context_revision,
                expected_session_id=mgr.session_id,
            )
            assert mutated.ok is False
            assert mutated.assurance_state in {"partially_tested", "verified_isolation"}
            assert any(item["name"] == "provider_match" for item in mutated.failures)
        finally:
            mgr.close()
            sm.ADAPTER_REGISTRY.pop("validator-provider", None)
