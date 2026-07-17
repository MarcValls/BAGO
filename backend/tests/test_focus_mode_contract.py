from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT.parent / "frontend" / "src"


class FocusModeContractTests(unittest.TestCase):
    def test_focus_and_review_modes_are_canonical(self) -> None:
        app = (UI_SRC / "app" / "ControlPlane.tsx").read_text(encoding="utf-8")
        header = (UI_SRC / "layout" / "GlobalHeader.tsx").read_text(encoding="utf-8")
        shell = (UI_SRC / "layout" / "WorkspaceShell.tsx").read_text(encoding="utf-8")

        self.assertIn("globalMode: 'normal' | 'focus' | 'review'", header)
        self.assertIn("uiState.globalMode === 'normal' && (", app)
        self.assertIn("uiState.globalMode === 'focus'", app)
        self.assertIn("uiState.globalMode === 'review'", app)
        self.assertIn("mode-${props.mode}", shell)
        self.assertIn("focus-header", header)
        self.assertIn("Salir de Focus", header)
        self.assertIn("Modo Lectura", header)

    def test_normal_mode_is_the_only_mode_with_sidebar_and_inspector(self) -> None:
        app = (UI_SRC / "app" / "ControlPlane.tsx").read_text(encoding="utf-8")
        self.assertIn("{uiState.globalMode === 'normal' && (", app)
        self.assertIn("<MainSidebar", app)
        self.assertIn("<InspectorDrawer", app)
        self.assertIn("<ActivityToast", app)


if __name__ == "__main__":
    unittest.main()
