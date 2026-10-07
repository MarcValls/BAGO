"""Packaging selection and output contract tests; no BAGO capabilities run."""

import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("build_pack", Path(__file__).with_name("build_pack.py"))
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)


class PackContractTests(unittest.TestCase):
    def test_sources_have_unique_destinations_and_no_live_state(self):
        selected = PACK.select_sources()
        names = [archive for archive, _ in selected]
        self.assertEqual(len(names), len(set(names)))
        for _, path in selected:
            parts = path.relative_to(PACK.ROOT).parts
            self.assertFalse(set(parts) & PACK.SKIP, str(path))
            if "runtime" in parts:
                self.assertEqual(path.suffix, ".py")
            self.assertNotIn(".bak", path.name)
            self.assertFalse(PACK.is_live_source(path.relative_to(PACK.ROOT).as_posix()))

    def test_local_node_control_state_is_excluded_as_a_whole(self):
        self.assertTrue(PACK.is_live_source("backend/.bago/node_control/evidence.jsonl"))
        self.assertTrue(PACK.is_live_source("backend/.bago/node_control/compatibility.json"))
        self.assertTrue(PACK.is_live_source(".gabo/copilot/bin/bago.py"))
        self.assertFalse(PACK.is_live_source("backend/.bago/core/context_store.py"))

    def test_required_entities_are_present_and_integrations_are_isolated(self):
        selected = {path.relative_to(PACK.ROOT).as_posix(): archive
                    for archive, path in PACK.select_sources()}
        required = {
            ".github/agents/bago-repo-explorer.agent.md": "01-copilot",
            ".github/skills/bago-toolkit/SKILL.md": "01-copilot",
            "backend/.bago/tools/tool_registry.py": "02-framework",
            "backend/.bago/workflows/WORKFLOW_GRAPH.json": "02-framework",
            "backend/.bago/mcp/bago_mcp_server.py": "03-integrations-review",
            "backend/.bago/extensions/bash-runner/extension.mjs": "03-integrations-review",
            "plugins/bago-github-admin/plugin.json": "03-integrations-review",
        }
        for source, group in required.items():
            self.assertIn(source, selected)
            self.assertTrue(selected[source].startswith(group + "/"), source)
        self.assertFalse(any("/.github/extensions/" in path for path in selected.values()))

    def test_secret_barrier_detects_values_not_scanner_regex(self):
        self.assertIsNotNone(PACK.SECRET.search(("ghp_" + "a" * 36).encode()))
        self.assertIsNotNone(PACK.SECRET.search(
            ("-----BEGIN PRIVATE KEY-----\n" + "A" * 48).encode()))
        self.assertIsNone(PACK.SECRET.search(b"re.compile('-----BEGIN PRIVATE KEY-----')"))
        synthetic = b"AKIA" + b"FAKE123456789012"
        self.assertFalse(PACK.has_secret_pattern(synthetic, "backend/.bago/tools/bago_canary.py"))
        self.assertTrue(PACK.has_secret_pattern(synthetic, "unrelated.py"))

    def test_descriptions_and_semantic_categories(self):
        summary, line = PACK.description(Path("agent.md"), "---\ndescription: 'Explorer'\n---")
        self.assertEqual((summary, line), ("Explorer", 2))
        self.assertEqual(PACK.meaning(".github/agents/bago-final-verifier.agent.md"),
                         "Verificacion y evidencia")


if __name__ == "__main__":
    unittest.main()
