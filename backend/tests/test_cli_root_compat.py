from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = (REPO / "release_version.txt").read_text(encoding="utf-8").strip()

from bago_core.parsers import build_parser  # noqa: E402


class CliRootCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = build_parser(EXPECTED_VERSION, str(REPO), "ollama-local", "llama3.2:3b")

    def _assert_root_before_and_after(self, argv_before: list[str], argv_after: list[str], expected_cmd: str, expected_subcmd: str) -> None:
        before = self.parser.parse_args(argv_before)
        after = self.parser.parse_args(argv_after)
        self.assertEqual(before.command, expected_cmd)
        self.assertEqual(after.command, expected_cmd)
        self.assertEqual(before.root, str(REPO))
        self.assertEqual(after.root, str(REPO))
        self.assertEqual(getattr(before, f"{expected_cmd}_cmd"), expected_subcmd)
        self.assertEqual(getattr(after, f"{expected_cmd}_cmd"), expected_subcmd)

    def test_scan_forced_accepts_root_before_and_after(self) -> None:
        self._assert_root_before_and_after(
            ["scan", "--root", str(REPO), "forced"],
            ["scan", "forced", "--root", str(REPO)],
            "scan",
            "forced",
        )

    def test_agent_route_accepts_root_before_and_after(self) -> None:
        self._assert_root_before_and_after(
            ["agent", "--root", str(REPO), "route", "--task", "review"],
            ["agent", "route", "--task", "review", "--root", str(REPO)],
            "agent",
            "route",
        )

    def test_toolsmith_assign_accepts_root_before_and_after(self) -> None:
        self._assert_root_before_and_after(
            ["toolsmith", "--root", str(REPO), "assign", "--task", "review"],
            ["toolsmith", "assign", "--task", "review", "--root", str(REPO)],
            "toolsmith",
            "assign",
        )


if __name__ == "__main__":
    unittest.main()
