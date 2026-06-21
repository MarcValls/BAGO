from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "BAGO_MIGRATION_SPRINTS.md"


class MigrationSprintPlanTests(unittest.TestCase):
    def test_plan_exists_and_has_all_sprints(self) -> None:
        text = PLAN.read_text(encoding="utf-8")
        self.assertIn("Status: completed", text)
        self.assertIn("BAGO_MIGRATE_TARGET.md", text)
        for sprint in range(0, 6):
            self.assertIn(f"Sprint {sprint}", text)

    def test_plan_tracks_row_groups(self) -> None:
        text = PLAN.read_text(encoding="utf-8")
        expected_groups = [
            "1, 18, 19, 22",
            "2, 3, 4, 5, 20, 25",
            "6, 7, 9, 10, 11, 12, 13, 15, 16",
            "8, 14, 17, 21, 23, 24",
        ]
        for group in expected_groups:
            self.assertIn(group, text)

    def test_sprint_one_lists_current_tree_files(self) -> None:
        text = PLAN.read_text(encoding="utf-8")
        expected_files = [
            ".bago/BOOTSTRAP.md",
            ".bago/AGENT_START.md",
            ".bago/START_AGENT.md",
            "bago.ps1",
            "electron/environment.cjs",
            "electron/runtime-service.cjs",
            "tests/test_system_prompt_bootstrap.py",
            "tests/test_no_visible_powershell.py",
        ]
        for file_name in expected_files:
            self.assertIn(file_name, text)


if __name__ == "__main__":
    unittest.main()
