from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BAGO = ROOT / ".bago"
TOOLS = BAGO / "tools"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Sprint2ContractsTests(unittest.TestCase):
    def test_layout_roots_exist(self) -> None:
        expected = [
            ".bago/agents",
            ".bago/core",
            ".bago/extensions",
            ".bago/knowledge",
            ".bago/mcp",
            ".bago/prompts",
            ".bago/roles",
            ".bago/state",
            ".bago/state.example",
            ".bago/templates",
            ".bago/workflows",
        ]
        for rel in expected:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_registry_contract(self) -> None:
        manifest = json.loads((BAGO / "tools.manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["tool_count"], len(manifest["tools"]))

        taxonomy = load_module(TOOLS / "_registry_taxonomy.py", "bago_registry_taxonomy")
        for name, entry in taxonomy.REGISTRY.items():
            self.assertEqual(entry.cmd, name)
            self.assertTrue(entry.layer, name)
            self.assertTrue(entry.scope, name)

    def test_state_contract(self) -> None:
        state_file = BAGO / "state" / "global_state.json"
        if not state_file.exists():
            self.skipTest(".bago/state/global_state.json not present (normal in CI — state is gitignored)")
        runtime_state = json.loads(state_file.read_text(encoding="utf-8"))
        template_path = BAGO / "state.example" / "global_state.json"
        self.assertTrue(template_path.exists(), "state.example/global_state.json is the canonical template after 2026-Q2 cleanup")
        template_state = json.loads(template_path.read_text(encoding="utf-8"))
        for payload in (runtime_state, template_state):
            for key in ("version",):
                self.assertIn(key, payload)

    def test_clean_core_manifest_removed(self) -> None:
        # CLEAN_CORE_MANIFEST.json was a v3.5.0-rc1 snapshot — removed during 2026-Q2 cleanup.
        self.assertFalse((ROOT / "CLEAN_CORE_MANIFEST.json").exists(),
                         "CLEAN_CORE_MANIFEST.json was archived; it is no longer part of the active repo")


if __name__ == "__main__":
    unittest.main()

