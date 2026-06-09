import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SurfaceContractTests(unittest.TestCase):
    def test_chat_api_has_no_manager_endpoints(self):
        source = (ROOT / "ui-react" / "src" / "api.js").read_text(encoding="utf-8")
        forbidden = (
            "/providers",
            "/catalog/",
            "/simulation/",
            "/rl/",
            "/credentials",
            "/installations",
            "/releases",
        )
        for endpoint in forbidden:
            self.assertNotIn(endpoint, source)

    def test_manager_does_not_embed_a_chat(self):
        index = (ROOT / "manager" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "manager" / "js" / "session-manager.js").read_text(encoding="utf-8")
        for marker in (
            "pm-session-chat",
            "pm-session-prompt",
            "pm-session-send",
            "pm-session-orchestrate",
        ):
            self.assertNotIn(marker, index)
            self.assertNotIn(marker, script)

    def test_runtime_contract_references_surface_contract(self):
        runtime = (ROOT / "docs" / "contracts" / "bago_v4_runtime_contract.json").read_text(encoding="utf-8")
        self.assertIn("bago_v4_surfaces_contract.md", runtime)


if __name__ == "__main__":
    unittest.main()
