from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT.parent / "frontend" / "src"


class UiCognitiveLoadContractTests(unittest.TestCase):
    def test_header_keeps_destination_navigation_out_of_the_chrome(self) -> None:
        header = (UI_SRC / "layout" / "GlobalHeader.tsx").read_text(encoding="utf-8")
        sidebar = (UI_SRC / "layout" / "MainSidebar.tsx").read_text(encoding="utf-8")
        registry = (UI_SRC / "navigation" / "actionRegistry.ts").read_text(encoding="utf-8")
        self.assertNotIn("onNavigate", header)
        self.assertNotIn("SECTIONS", header)
        self.assertIn("Navegación principal", sidebar)
        self.assertIn("sidebar-item", sidebar)
        self.assertIn("SECTION_LABELS", header)
        self.assertIn("NAVIGATION_GROUPS", sidebar)
        self.assertIn("NAVIGATION_GROUPS", registry)
        self.assertLess(registry.index("id: 'context'"), registry.index("id: 'pipeline'"))

    def test_review_defines_required_cognitive_load_methods(self) -> None:
        review = (ROOT / "docs" / "ui-cognitive-load-review.md").read_text(encoding="utf-8")
        for phrase in [
            "one canonical destination navigator",
            "Progressive disclosure",
            "Recognition over recall",
            "focus",
            "review",
            "command palette",
            "MainSidebar",
            "GlobalHeader",
        ]:
            self.assertIn(phrase, review)


if __name__ == "__main__":
    unittest.main()
