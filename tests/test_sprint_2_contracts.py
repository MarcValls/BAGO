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
            ".bago/monitor",
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
        self.assertEqual(manifest["tool_count"], 170)

        taxonomy = load_module(TOOLS / "_registry_taxonomy.py", "bago_registry_taxonomy")
        self.assertEqual(len(taxonomy.REGISTRY), 165)
        for name, entry in taxonomy.REGISTRY.items():
            self.assertEqual(entry.cmd, name)
            self.assertTrue(entry.layer, name)
            self.assertTrue(entry.scope, name)

    def test_state_contract(self) -> None:
        state_file = BAGO / "state" / "global_state.json"
        if not state_file.exists():
            self.skipTest(".bago/state/global_state.json not present (normal in CI — state is gitignored)")
        runtime_state = json.loads(state_file.read_text(encoding="utf-8"))
        template_state = json.loads((BAGO / "state.example" / "global_state.clean.json").read_text(encoding="utf-8"))
        for payload in (runtime_state, template_state):
            for key in ("flow", "sprint", "health", "version"):
                self.assertIn(key, payload)
            self.assertNotIn("health=75", json.dumps(payload))
            self.assertNotIn("100/100", json.dumps(payload))

    def test_manifest_contract(self) -> None:
        manifest = json.loads((ROOT / "CLEAN_CORE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "3.5.0-rc1")
        self.assertIn("counts", manifest)
        self.assertIn("files_by_top_level_final", manifest["counts"])
        self.assertGreaterEqual(manifest["counts"]["files_by_top_level_final"].get("examples", 0), 71)


if __name__ == "__main__":
    unittest.main()

