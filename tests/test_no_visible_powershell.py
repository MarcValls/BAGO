from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NoVisiblePowerShellTests(unittest.TestCase):
    def test_electron_powershell_hidden_by_default(self) -> None:
        source = (ROOT / "electron" / "environment.cjs").read_text(encoding="utf-8")
        self.assertIn("const visible = options.visible === true;", source)
        self.assertIn("detached: visible", source)
        self.assertIn("windowsHide: !visible", source)

    def test_manager_does_not_spawn_visible_powershell_for_cli_or_dependencies(self) -> None:
        runtime = (ROOT / "electron" / "runtime-service.cjs").read_text(encoding="utf-8")
        deps = (ROOT / "electron" / "dependency-service.cjs").read_text(encoding="utf-8")
        self.assertIn("mode: 'manual-command'", runtime)
        self.assertNotIn("visible: true", runtime)
        self.assertIn("mode: 'manual-command'", deps)
        self.assertNotIn("visible: true", deps)

    def test_windows_release_job_fixture_hides_powershell(self) -> None:
        source = (ROOT / "tests" / "test_release_job_manager.cjs").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("{ windowsHide: true }"), 2)

    def test_dev_terminal_prefers_workspace_root(self) -> None:
        ps = (ROOT / "bago.ps1").read_text(encoding="utf-8")
        env = (ROOT / "electron" / "environment.cjs").read_text(encoding="utf-8")
        runtime = (ROOT / "electron" / "runtime-service.cjs").read_text(encoding="utf-8")
        self.assertIn("Join-Path $env:USERPROFILE 'bago_fw'", ps)
        self.assertIn("elseif ($first -eq 'dev')", ps)
        self.assertIn("resolveDevelopmentRuntimeRoot", env)
        self.assertIn("development_root: developmentRoot || ''", runtime)
        self.assertIn("resolveDevelopmentRuntimeRoot()", runtime)


if __name__ == "__main__":
    unittest.main()
