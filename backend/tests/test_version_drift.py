from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_UI = ROOT.parent / "frontend"
EXPECTED_VERSION = (ROOT / "release_version.txt").read_text(encoding="utf-8").strip()


class VersionDriftTests(unittest.TestCase):
    def test_new_session_metadata_uses_release_version(self) -> None:
        from session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmp:
            state_root = Path(tmp) / "state"
            old = os.environ.get("BAGO_STATE_ROOT")
            os.environ["BAGO_STATE_ROOT"] = str(state_root)
            try:
                mgr = SessionManager(base_path=tmp, state_root=str(state_root))
                try:
                    meta_path = state_root / "sessions" / mgr.session_id / "meta.json"
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    self.assertEqual(meta.get("bago_version"), EXPECTED_VERSION)
                finally:
                    mgr.close()
            finally:
                if old is None:
                    os.environ.pop("BAGO_STATE_ROOT", None)
                else:
                    os.environ["BAGO_STATE_ROOT"] = old

    def test_runtime_entrypoints_do_not_declare_legacy_release_version(self) -> None:
        paths = [
            ROOT / ".bago" / "core" / "session_manager.py",
            ROOT / ".bago" / "core" / "context_store.py",
            ROOT / ".bago" / "tools" / "orchestrator_v4.py",
            ROOT / "scripts" / "bago_supervisor.py",
            ROOT / "bago_core" / "evidence_report.py",
            ROOT / "bago.ps1",
            ROOT / "test_e2e.py",
        ]
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("4.1.5", text)
                self.assertNotIn("BAGO launcher (4.2.0)", text)

    def test_visible_metadata_matches_release_version(self) -> None:
        if not (CANONICAL_UI / "package.json").is_file():
            self.skipTest("canonical frontend source is not shipped in installed runtimes")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        ui_package = json.loads((CANONICAL_UI / "package.json").read_text(encoding="utf-8"))
        ui_config = json.loads((CANONICAL_UI / "public" / "ui_config.json").read_text(encoding="utf-8"))
        versions = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], EXPECTED_VERSION)
        self.assertEqual(ui_package["version"], EXPECTED_VERSION)
        self.assertEqual(ui_config["version"], EXPECTED_VERSION)
        self.assertEqual(versions["current"], EXPECTED_VERSION)

        current_entry = next(item for item in versions["history"] if item["version"] == EXPECTED_VERSION)
        current_notes = current_entry["notes"].lower()
        self.assertNotIn("beta", current_notes)
        self.assertNotIn("prerelease", current_notes)
        self.assertEqual(
            [item["version"] for item in versions["history"] if item["ended"] is None],
            [EXPECTED_VERSION],
        )
        readme = (ROOT.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"# BAGO v{EXPECTED_VERSION}", readme)
        self.assertIn(f"badge/version-{EXPECTED_VERSION}-blue", readme)
        self.assertIn(f"releases/tag/v{EXPECTED_VERSION}", readme)

    def test_canonical_frontend_is_the_only_ui_toolchain(self) -> None:
        if not (CANONICAL_UI / "src" / "main.tsx").is_file():
            self.skipTest("canonical frontend source is not shipped in installed runtimes")
        self.assertTrue((CANONICAL_UI / "src" / "main.tsx").is_file())
        self.assertFalse((ROOT / "ui-react" / "package.json").exists())
        build_script = (ROOT / "scripts" / "build_ui_dist.py").read_text(encoding="utf-8")
        self.assertIn('FRONTEND_ROOT = ROOT.parent / "frontend"', build_script)

    def test_local_visible_entrypoints_do_not_advertise_stale_runtime(self) -> None:
        home = Path.home()
        paths = [
            home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
            home / "AppData" / "Local" / "BAGO" / "bago.ps1",
            Path("C:/Program Files/BAGO/bago.ps1"),
        ]
        for path in paths:
            if not path.exists():
                continue
            with self.subTest(path=str(path)):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("BAGO launcher (4.2.0)", text)
                self.assertNotIn('bagoVersion = "4.2.2"', text)
                self.assertNotIn(r"\.bago\active", text)


if __name__ == "__main__":
    unittest.main()
