#!/usr/bin/env python3
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    source_root = str(Path(__file__).resolve().parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = source_root if not existing else f"{source_root}{os.pathsep}{existing}"
    return subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True)


def _make_repo() -> Path:
    root = Path(tempfile.mkdtemp(prefix="bago_test_issue_take_"))
    repo = root / "repo"
    subprocess.run(["git", "init", str(repo)], check=True)
    cli = repo / "bago"
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "from bago_core.cli import main\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)
    return repo


class IssueTakeAgentTests(unittest.TestCase):
    def test_take_assigns_specific_agent_argument(self) -> None:
        repo = _make_repo()
        result = _run(["python3", "bago", "issues", "--dry-run", "take", "--agent", "codex"], repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("@codex", result.stdout)

    def test_take_defaults_to_copilot(self) -> None:
        repo = _make_repo()
        result = _run(["python3", "bago", "issues", "--dry-run", "take"], repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("@copilot", result.stdout)


if __name__ == "__main__":
    unittest.main()
