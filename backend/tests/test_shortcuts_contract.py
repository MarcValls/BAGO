from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT.parent / "frontend" / "src"


class ShortcutContractTests(unittest.TestCase):
    def test_supported_shortcuts_exist(self) -> None:
        for path in [
            ROOT / "open-ui-bago.cmd",
            ROOT / "open-electron-bago.cmd",
        ]:
            self.assertTrue(path.exists(), str(path))

    def test_shortcuts_resolve_runtime_relatively(self) -> None:
        for path in [
            ROOT / "open-ui-bago.cmd",
            ROOT / "open-electron-bago.cmd",
        ]:
            text = path.read_text(encoding="utf-8")
            self.assertIn("%~dp0", text, str(path))
            self.assertNotRegex(text, re.escape(str(ROOT)), str(path))
            if path.name == "open-ui-bago.cmd":
                self.assertIn("launcher.py", text, str(path))
            else:
                self.assertIn("electron\\main.cjs", text, str(path))

    def test_runtime_shortcut_is_packaged(self) -> None:
        package_script = (ROOT / "scripts" / "package_v4.py").read_text(encoding="utf-8")
        package_json = (ROOT / "package.json").read_text(encoding="utf-8")
        self.assertIn('"open-ui-bago.cmd"', package_script)
        self.assertIn('"open-electron-bago.cmd"', package_script)
        self.assertIn('"open-ui-bago.cmd"', package_json)
        self.assertIn('"open-electron-bago.cmd"', package_json)

    def test_in_app_keyboard_shortcuts_are_wired(self) -> None:
        app = (UI_SRC / "app" / "ControlPlane.tsx").read_text(encoding="utf-8")
        self.assertIn("event.key.toLowerCase() === 'k'", app)
        self.assertIn("commandPaletteOpen", app)
        self.assertIn("event.key === 'Escape' && entered", app)
        self.assertIn("WorkspacePickerDialog", app)
        self.assertIn("focus", app)
        self.assertIn("review", app)


if __name__ == "__main__":
    unittest.main()
