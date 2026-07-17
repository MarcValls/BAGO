from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
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
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        ui_package = json.loads((ROOT / "ui-react" / "package.json").read_text(encoding="utf-8"))
        ui_config = json.loads((ROOT / "ui-react" / "public" / "ui_config.json").read_text(encoding="utf-8"))
        versions = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], EXPECTED_VERSION)
        self.assertEqual(ui_package["version"], EXPECTED_VERSION)
        self.assertEqual(ui_config["version"], EXPECTED_VERSION)
        self.assertEqual(versions["current"], EXPECTED_VERSION)

    def test_workspace_and_runtime_ui_toolchains_match(self) -> None:
        workspace_ui = ROOT.parents[2] / "ui-react"
        runtime_ui = ROOT / "ui-react"
        if not workspace_ui.exists():
            self.skipTest("workspace ui-react not available in standalone release tree")

        workspace_package = json.loads((workspace_ui / "package.json").read_text(encoding="utf-8"))
        runtime_package = json.loads((runtime_ui / "package.json").read_text(encoding="utf-8"))
        for key in ("scripts", "dependencies", "devDependencies"):
            with self.subTest(key=key):
                self.assertEqual(runtime_package.get(key), workspace_package.get(key))

        workspace_lock = json.loads((workspace_ui / "package-lock.json").read_text(encoding="utf-8"))
        runtime_lock = json.loads((runtime_ui / "package-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime_lock, workspace_lock)

        workspace_tsconfig = json.loads((workspace_ui / "tsconfig.json").read_text(encoding="utf-8"))
        runtime_tsconfig = json.loads((runtime_ui / "tsconfig.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime_tsconfig, workspace_tsconfig)

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
