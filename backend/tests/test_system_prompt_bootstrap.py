from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import system_prompt as system_prompt_module  # noqa: E402


class SystemPromptBootstrapTests(unittest.TestCase):
    def test_get_system_prompt_uses_manifest_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chat_dir = root / "chat"
            chat_dir.mkdir(parents=True, exist_ok=True)

            identity = chat_dir / "system_prompt_identity.md"
            workspace = chat_dir / "system_prompt_workspace.md"
            understanding = chat_dir / "system_prompt_understanding.md"
            evidence = chat_dir / "system_prompt_evidence.md"
            fmt = chat_dir / "system_prompt_format.md"
            bootstrap = root / "BOOTSTRAP.md"
            agent_start = root / "AGENT_START.md"
            manifest = chat_dir / "system_prompt_manifest.json"

            identity.write_text("You are BAGO, a session-persistent AI assistant.", encoding="utf-8")
            workspace.write_text("Treat .gabo as project workspace state.", encoding="utf-8")
            understanding.write_text(
                "Treat RC4 as the intake and output pattern: normalize the request first, then answer in RC4 order: state, evidence, change, validation, next step.\nFor complex requests, derive QuestionUnderstandingState and ResponseContract before acting.",
                encoding="utf-8",
            )
            evidence.write_text(
                "Claims need evidence, receipts need validation, and contradictions need explicit handling.\nManagerContext only counts when the backend receipt shows it was consumed.",
                encoding="utf-8",
            )
            fmt.write_text(
                "Prefer technical vocabulary, file names, and canonical contracts.\nAvoid line-number anchoring unless the user explicitly asks for it.",
                encoding="utf-8",
            )
            bootstrap.write_text("BOOTSTRAP", encoding="utf-8")
            agent_start.write_text("AGENT_START", encoding="utf-8")
            manifest.write_text(json.dumps({
                "sources": [
                    {"path": "system_prompt_identity.md", "required": True, "kind": "identity"},
                    {"path": "system_prompt_workspace.md", "required": True, "kind": "workspace"},
                    {"path": "system_prompt_understanding.md", "required": True, "kind": "understanding"},
                    {"path": "system_prompt_evidence.md", "required": True, "kind": "evidence"},
                    {"path": "system_prompt_format.md", "required": True, "kind": "format"},
                    {"path": "../BOOTSTRAP.md", "required": True, "kind": "bootstrap"},
                    {"path": "../AGENT_START.md", "required": True, "kind": "agent_start"},
                ],
                "validation": {
                    "required_phrases": [
                        "Treat RC4 as the intake and output pattern",
                        "state, evidence, change, validation, next step",
                        "QuestionUnderstandingState",
                        "ResponseContract",
                        "Prefer technical vocabulary, file names, and canonical contracts",
                        "Avoid line-number anchoring unless the user explicitly asks for it",
                    ]
                },
            }, ensure_ascii=False, indent=2), encoding="utf-8")

            old_manifest = system_prompt_module._MANIFEST_PATH
            system_prompt_module._MANIFEST_PATH = manifest
            try:
                prompt = system_prompt_module.get_system_prompt()
            finally:
                system_prompt_module._MANIFEST_PATH = old_manifest

            self.assertIn("You are BAGO, a session-persistent AI assistant.", prompt)
            self.assertIn("BOOTSTRAP", prompt)
            self.assertIn("AGENT_START", prompt)
            self.assertIn("Prefer technical vocabulary, file names, and canonical contracts", prompt)
            self.assertLess(prompt.index("You are BAGO, a session-persistent AI assistant."), prompt.index("BOOTSTRAP"))
            self.assertLess(prompt.index("BOOTSTRAP"), prompt.index("AGENT_START"))

    def test_validate_system_prompt_contract_rejects_missing_rc4(self) -> None:
        with self.assertRaises(ValueError):
            system_prompt_module.validate_system_prompt_contract("BASE only")


if __name__ == "__main__":
    unittest.main()
