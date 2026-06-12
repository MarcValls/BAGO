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

    def test_manager_chat_bridge_is_local_and_origin_bound(self):
        index = (ROOT / "manager" / "index.html").read_text(encoding="utf-8")
        bridge = (ROOT / "manager" / "js" / "bago-chat.js").read_text(encoding="utf-8")
        receiver = (ROOT / "ui-react" / "src" / "useManagerContext.js").read_text(encoding="utf-8")
        self.assertIn('id="pm-bago-frame"', index)
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-forms allow-modals"', index)
        self.assertIn("targetOrigin", bridge)
        self.assertNotIn("postMessage({ source: 'bago-manager', type, data }, '*')", bridge)
        self.assertIn("event.source !== window.parent", receiver)
        self.assertIn("isTrustedManagerOrigin(event.origin)", receiver)

    def test_runtime_contract_references_surface_contract(self):
        runtime = (ROOT / "docs" / "contracts" / "bago_v4_runtime_contract.json").read_text(encoding="utf-8")
        self.assertIn("bago_v4_surfaces_contract.md", runtime)


if __name__ == "__main__":
    unittest.main()
