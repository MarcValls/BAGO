from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / ".bago" / "tools"
PYTHON = sys.executable


class ContextDetectorTests(unittest.TestCase):
    def _run(self, root: Path, *args: str) -> dict:
        completed = subprocess.run(
            [PYTHON, str(TOOLS_DIR / "context_detector.py"), "--root", str(root), *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"_stdout": completed.stdout, "_stderr": completed.stderr, "_rc": completed.returncode}

    def test_harvest_when_decision_discard_next_step_and_evidence_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".bago" / "runtime").mkdir(parents=True)
            (root / ".bago" / "runtime" / "ACTIVE_HANDOFF.md").write_text(
                "Decision: semantic trigger.\n"
                "Discard: time-based trigger.\n"
                "Next step: implement context_detector.py.\n"
                "Evidence: tests and runtime sync.\n",
                encoding="utf-8",
            )
            result = self._run(root, "--json")
            self.assertEqual(result["verdict"], "HARVEST")
            self.assertGreaterEqual(result["score"], 4)

    def test_continue_for_ambiguous_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".bago" / "state").mkdir(parents=True)
            (root / ".bago" / "state" / "PROJECT_STATE.json").write_text(
                json.dumps({"notes": [{"note": "still exploring, nothing decided yet"}]}),
                encoding="utf-8",
            )
            result = self._run(root, "--json")
            self.assertEqual(result["verdict"], "CONTINUE")
            self.assertLess(result["score"], 4)

    def test_text_override_triggers_harvest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = self._run(root, "--text", "decision discard next step evidence", "--json")
            self.assertEqual(result["verdict"], "HARVEST")


if __name__ == "__main__":
    unittest.main()
