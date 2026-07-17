from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT / "ui-react" / "src"


class CommandPaletteContractTests(unittest.TestCase):
    def test_palette_surface_exists(self) -> None:
        app = (UI_SRC / "app" / "ControlPlane.tsx").read_text(encoding="utf-8")
        header = (UI_SRC / "layout" / "GlobalHeader.tsx").read_text(encoding="utf-8")
        self.assertIn("command-palette-backdrop", app)
        self.assertIn("Comandos rápidos", app)
        self.assertIn("WorkspacePickerDialog", app)
        self.assertIn("Abrir comandos con Ctrl K", header)

    def test_app_wires_palette_and_shortcut(self) -> None:
        app = (UI_SRC / "app" / "ControlPlane.tsx").read_text(encoding="utf-8")
        header = (UI_SRC / "layout" / "GlobalHeader.tsx").read_text(encoding="utf-8")
        self.assertIn("commandPaletteOpen", app)
        self.assertIn("setAndPersistUiState({ commandPaletteOpen: true })", app)
        self.assertIn("onOpenPalette", header)
        self.assertIn("Ctrl K", header)
        self.assertIn("focus", app)
        self.assertIn("review", app)


if __name__ == "__main__":
    unittest.main()
