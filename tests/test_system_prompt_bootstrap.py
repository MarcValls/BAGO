from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".bago" / "chat"))

import system_prompt as system_prompt_module  # noqa: E402


class SystemPromptBootstrapTests(unittest.TestCase):
    def test_get_system_prompt_appends_bootstrap_and_agent_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bootstrap = root / "BOOTSTRAP.md"
            agent_start = root / "AGENT_START.md"
            bootstrap.write_text("BOOTSTRAP", encoding="utf-8")
            agent_start.write_text("AGENT_START", encoding="utf-8")

            old_bootstrap = system_prompt_module._BOOTSTRAP_PATH
            old_agent_start = system_prompt_module._AGENT_START_PATH
            system_prompt_module._BOOTSTRAP_PATH = bootstrap
            system_prompt_module._AGENT_START_PATH = agent_start
            try:
                prompt = system_prompt_module.get_system_prompt()
            finally:
                system_prompt_module._BOOTSTRAP_PATH = old_bootstrap
                system_prompt_module._AGENT_START_PATH = old_agent_start

            self.assertIn("BOOTSTRAP", prompt)
            self.assertIn("AGENT_START", prompt)
            self.assertLess(prompt.index("BOOTSTRAP"), prompt.index("AGENT_START"))


if __name__ == "__main__":
    unittest.main()
