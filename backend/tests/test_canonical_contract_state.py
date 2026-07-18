from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


from contract_state import build_model_catalog_state, build_workspace_state  # noqa: E402
from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse  # noqa: E402
import session_manager as sm  # noqa: E402


class CanonicalContractStateTests(unittest.TestCase):
    def test_workspace_state_distinguishes_confirmed_and_unlinked_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".gabo").mkdir(parents=True)
            (root / ".gabo" / "workspace.json").write_text(
                json.dumps(
                    {
                        "workspace_id": "ws-rc5",
                        "project_root": str(root),
                        "workspace_scope_root": str(root),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            confirmed = build_workspace_state(root)
            unlinked = build_workspace_state(root, workspace_id="ws-other")

            self.assertEqual(confirmed["workspace_state"], "linked_confirmed")
            self.assertTrue(confirmed["binding_confirmed"])
            self.assertIn("chat.send", confirmed["allowed_actions"])

            self.assertEqual(unlinked["workspace_state"], "detected_unlinked")
            self.assertFalse(unlinked["binding_confirmed"])
            self.assertIn("workspace.link", unlinked["allowed_actions"])
            self.assertIn("workspace.init", unlinked["blocked_operations"])

    def test_model_catalog_state_preserves_selected_and_effective_model(self) -> None:
        catalog = build_model_catalog_state(
            "catalog-provider",
            [
                {
                    "id": "alpha",
                    "wire_name": "alpha",
                    "provider": "catalog-provider",
                    "context_tokens": 4096,
                    "max_output_tokens": 512,
                    "best_for": "draft",
                    "cost": "free",
                    "available": False,
                },
                {
                    "id": "beta",
                    "wire_name": "beta",
                    "provider": "catalog-provider",
                    "context_tokens": 8192,
                    "max_output_tokens": 1024,
                    "best_for": "final",
                    "cost": "free",
                    "available": True,
                },
            ],
            selected_model="beta",
            effective_model="beta",
        )

        self.assertEqual(catalog["provider"], "catalog-provider")
        self.assertEqual(catalog["selected_model"], "beta")
        self.assertEqual(catalog["effective_model"], "beta")
        self.assertEqual([item["id"] for item in catalog["items"]], ["alpha", "beta"])
        self.assertFalse(catalog["items"][0]["available"])
        self.assertTrue(catalog["items"][1]["available"])
        self.assertEqual(catalog["selected_model"], "beta")
        self.assertEqual(catalog["effective_model"], "beta")

    def test_session_manager_filters_unavailable_models_in_available_only_mode(self) -> None:
        class CatalogAdapter(ProviderAdapter):
            def __init__(self, config=None):
                super().__init__("catalog-provider", config)

            def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
                return ProviderResponse(content="ok", model_used=model, provider=self.provider_name, finish_reason="stop")

            def list_models(self):
                return [
                    ModelInfo("alpha", "alpha", self.provider_name, 4096, 512, "draft", "free", available=False),
                    ModelInfo("beta", "beta", self.provider_name, 8192, 1024, "final", "free", available=True),
                ]

            def health_check(self, timeout=5.0):
                return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

            def is_configured(self):
                return True

            def supports_tools(self):
                return False

            def supports_streaming(self):
                return False

        sm.ADAPTER_REGISTRY["catalog-provider"] = CatalogAdapter
        try:
            with tempfile.TemporaryDirectory() as td:
                workspace = Path(td) / "workspace"
                workspace.mkdir()
                state_root = Path(td) / "state"
                mgr = sm.SessionManager(
                    session_id="rc5-catalog",
                    provider="catalog-provider",
                    model="beta",
                    base_path=str(workspace),
                    state_root=str(state_root),
                )
                try:
                    available_only = mgr.list_model_catalog("catalog-provider", mode="available-only")
                    self.assertEqual([item["id"] for item in available_only], ["beta"])

                    state = mgr.model_catalog_state("catalog-provider")
                    self.assertEqual(state["selected_model"], "beta")
                    self.assertEqual(state["effective_model"], "beta")
                    self.assertEqual([item["id"] for item in state["items"]], ["alpha", "beta"])
                finally:
                    mgr.close()
        finally:
            sm.ADAPTER_REGISTRY.pop("catalog-provider", None)


if __name__ == "__main__":
    unittest.main()
