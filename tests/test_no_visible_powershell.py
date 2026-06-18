from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NoVisiblePowerShellTests(unittest.TestCase):
    def test_electron_powershell_hidden_by_default(self) -> None:
        source = (ROOT / "electron" / "environment.cjs").read_text(encoding="utf-8")
        self.assertIn("const visible = options.visible === true;", source)
        self.assertIn("detached: visible", source)
        self.assertIn("windowsHide: !visible", source)

    def test_explicit_cli_and_dependency_actions_are_the_only_visible_powershell(self) -> None:
        runtime = (ROOT / "electron" / "runtime-service.cjs").read_text(encoding="utf-8")
        deps = (ROOT / "electron" / "dependency-service.cjs").read_text(encoding="utf-8")
        self.assertIn("runVisiblePowerShell(command, { visible: true, noExit: true, cwd: runtimeRoot })", runtime)
        self.assertIn("visible: true", deps)

    def test_windows_release_job_fixture_hides_powershell(self) -> None:
        source = (ROOT / "tests" / "test_release_job_manager.cjs").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("{ windowsHide: true }"), 2)


if __name__ == "__main__":
    unittest.main()
