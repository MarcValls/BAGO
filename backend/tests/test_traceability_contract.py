from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TraceabilityContractTests(unittest.TestCase):
    def test_snapshot_declares_non_git_traceability(self) -> None:
        doc = (ROOT / "docs" / "TRACEABILITY.md").read_text(encoding="utf-8")
        self.assertIn("file-manifest based", doc)
        self.assertIn("current.manifest.json", doc)
        self.assertIn("historical one-off material stays out of generated packages", doc)
        self.assertIn("package contents must match the manifest", doc)

    def test_runtime_traceability_inputs_exist(self) -> None:
        for relative in ["release_version.txt", "versions.json", "scripts/package_v4.py"]:
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_historical_sprints_are_excluded_from_packages(self) -> None:
        testing = (ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
        self.assertIn("python scripts\\package_v4.py --test", testing)
        self.assertIn("python scripts\\package_v4.py", testing)
        for script in [
            ROOT / "scripts" / "package_v4.py",
            ROOT / "scripts" / "package_user_bundle.py",
            ROOT / "scripts" / "package_audit_bundle.py",
        ]:
            self.assertIn('"tools/sprints"', script.read_text(encoding="utf-8"), str(script))

        package_json = (ROOT / "package.json").read_text(encoding="utf-8")
        self.assertIn('"!tools/sprints/**/*"', package_json)

    def test_removed_local_probe_script_stays_removed(self) -> None:
        self.assertFalse((ROOT / "scripts" / "_verify_new.py").exists())

    def test_verify_copies_is_not_bound_to_this_workspace(self) -> None:
        script = (ROOT / "scripts" / "verify-copies.ps1").read_text(encoding="utf-8")
        self.assertNotIn("C:\\Users\\AMTEC_Terminal_1º\\BAG4.8", script)
        self.assertIn("$RuntimeRoot", script)
        self.assertIn("CopyRoot", script)

    def test_repair_helpers_use_portable_roots(self) -> None:
        repo_map_md = (ROOT / ".gabo" / "context" / "repository_map.md").read_text(encoding="utf-8")
        repo_map_json = (ROOT / ".gabo" / "context" / "repository_map.json").read_text(encoding="utf-8")
        chk = (ROOT / ".gabo" / "api" / "_chk_handlers.py").read_text(encoding="utf-8")
        launcher = (ROOT / "bago_core" / "launcher.py").read_text(encoding="utf-8")
        repair = (ROOT / "scripts" / "repair_routing_runtime.py").read_text(encoding="utf-8")
        ssot = (ROOT / "bago_core" / "node_control_ssot.py").read_text(encoding="utf-8")
        seed = (ROOT / ".gabo" / "seed.py").read_text(encoding="utf-8")

        self.assertNotIn("C:\\Users\\AMTEC_Terminal_1º\\BAG4.8\\release\\v4\\current", repo_map_md)
        self.assertNotIn("C:\\Users\\AMTEC_Terminal_1º\\BAG4.8\\release\\v4\\current", repo_map_json)
        self.assertIn(f"project_root: `{ROOT}`", repo_map_md)
        self.assertEqual(json.loads(repo_map_json)["project_root"], str(ROOT))
        self.assertIn("sys.path.insert(0, _repo_root)", launcher)
        self.assertIn("from bago_core.workspace_paths import workspace_root", launcher)
        self.assertNotIn("C:\\Program Files\\BAGO", chk)
        self.assertNotIn("C:\\Users\\AMTEC_Terminal_1º", repair)
        self.assertNotIn("C:\\ProgramData\\BAGO", ssot)
        self.assertIn("_piece_store_root", ssot)
        self.assertIn("Path(__file__).resolve().parents[1]", repair)
        self.assertIn("API_ROOT", chk)
        self.assertIn("SKIP_DIRS", seed)
        self.assertIn('".gabo"', seed)
        self.assertIn("discover_api_canon", seed)


if __name__ == "__main__":
    unittest.main()
