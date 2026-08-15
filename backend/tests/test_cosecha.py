from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent.parent / ".bago" / "tools"
PYTHON = sys.executable


def _run_cosecha(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [PYTHON, str(TOOLS_DIR / "cosecha.py"), *args],
        capture_output=True,
        text=True,
        input=input_text,
        env=env,
        timeout=30,
    )


def _parse_last_json(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return {}
    return json.loads(lines[-1])


class TestCosechaTool(unittest.TestCase):
    def test_cli_answers_create_closed_harvest_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "project"
            state = root / "state"
            project.mkdir()
            (project / "src").mkdir()
            (project / "src" / "app.py").write_text("print('hola')\n", encoding="utf-8")

            result = _run_cosecha(
                [
                    "--root", str(project),
                    "--state-root", str(state),
                    "--decision", "Usar disparador semántico",
                    "--discard", "Descartar el reloj fijo de 120s",
                    "--next-step", "Integrar cosecha portable",
                    "--modified-file", "src/app.py",
                    "--modified-file", "README.md",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = _parse_last_json(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["task_type"], "harvest")
            self.assertEqual(payload["status"], "closed")
            self.assertEqual(payload["workflow"], "w9_cosecha")
            self.assertIn("Usar disparador semántico", payload["summary"])

            session_id = payload["session_id"]
            change_id = payload["change_id"]
            evidence_id = payload["evidence_id"]

            session_json = state / "sessions" / f"{session_id}.json"
            session_meta = state / "sessions" / session_id / "meta.json"
            change_json = state / "changes" / f"{change_id}.json"
            evidence_json = state / "evidences" / f"{evidence_id}.json"
            global_state_json = state / "global_state.json"

            self.assertTrue(session_json.exists())
            self.assertTrue(session_meta.exists())
            self.assertTrue(change_json.exists())
            self.assertTrue(evidence_json.exists())
            self.assertTrue(global_state_json.exists())

            session_payload = json.loads(session_json.read_text(encoding="utf-8"))
            self.assertEqual(session_payload["task_type"], "harvest")
            self.assertEqual(session_payload["status"], "closed")
            self.assertEqual(session_payload["selected_workflow"], "w9_cosecha")

            change_payload = json.loads(change_json.read_text(encoding="utf-8"))
            self.assertEqual(change_payload["scope"], ["src/app.py", "README.md"])
            self.assertEqual(change_payload["status"], "validated")

            evidence_payload = json.loads(evidence_json.read_text(encoding="utf-8"))
            self.assertEqual(
                evidence_payload["details"],
                {
                    "decision": "Usar disparador semántico",
                    "discard": "Descartar el reloj fijo de 120s",
                    "next_step": "Integrar cosecha portable",
                },
            )
            self.assertEqual(evidence_payload["status"], "recorded")

            global_state = json.loads(global_state_json.read_text(encoding="utf-8"))
            self.assertEqual(global_state["inventory"], {"sessions": 1, "changes": 1, "evidences": 1})
            self.assertEqual(global_state["knowledge_base"]["last_harvest_session_id"], session_id)
            self.assertEqual(global_state["last_validation"]["session_id"], session_id)

    def test_interactive_mode_prompts_three_questions_and_detects_git_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "project"
            state = root / "state"
            project.mkdir()
            subprocess.run(["git", "init"], cwd=project, capture_output=True, text=True, check=True)
            (project / "notes.md").write_text("pendiente\n", encoding="utf-8")

            result = _run_cosecha(
                [
                    "--root", str(project),
                    "--state-root", str(state),
                ],
                input_text=(
                    "Decidí usar el detector semántico\n"
                    "Descarté el reloj fijo porque es un proxy malo\n"
                    "El próximo paso es cerrar la cosecha\n"
                ),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("1/3 ¿Qué decidiste en esta exploración?", result.stdout)
            self.assertIn("2/3 ¿Qué descartaste y por qué?", result.stdout)
            self.assertIn("3/3 ¿Cuál es el próximo paso concreto?", result.stdout)

            payload = _parse_last_json(result.stdout)
            self.assertTrue(payload["ok"], payload)
            self.assertIn("notes.md", payload["modified_files"])


if __name__ == "__main__":
    unittest.main()
