from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BAGO = ROOT / ".bago"


class Sprint3AssetTests(unittest.TestCase):
    def test_workflows_index_lists_expected_files(self) -> None:
        text = (BAGO / "workflows" / "WORKFLOWS_INDEX.md").read_text(encoding="utf-8")
        expected = [
            "WORKFLOW_MAESTRO_BAGO",
            "W0_FREE_SESSION",
            "W1_COLD_START",
            "W2_IMPLEMENTACION_CONTROLADA",
            "W3_REFACTOR_SENSIBLE",
            "W4_DEBUG_MULTICAUSA",
            "W5_CIERRE_Y_CONTINUIDAD",
            "W6_IDEACION_APLICADA",
            "W7_FOCO_SESION",
            "W8_EXPLORACION",
            "W9_COSECHA",
            "W10_AUDITORIA_SINCERIDAD",
        ]
        for item in expected:
            self.assertIn(item, text)
        self.assertIn("music-score-transposition", text)

    def test_templates_and_prompts_are_restored(self) -> None:
        templates = sorted((BAGO / "templates").glob("*.md"))
        self.assertEqual(len(templates), 5)
        for path in templates:
            text = path.read_text(encoding="utf-8")
            self.assertIn("## Output", text, path.name)

        prompts = sorted((BAGO / "prompts").glob("*.md"))
        self.assertEqual(len(prompts), 12)
        for path in prompts:
            self.assertRegex(path.name, r"^(?:\d\d_[A-Z_]+|activar_[a-z_]+)\.md$")

    def test_core_docs_and_kernel_docs_exist(self) -> None:
        # 2026-Q2 cleanup: 00-07 v3.5.0-rc1 canon was archived. Active canon lives in
        # subdirs (canon/, architecture/, orchestrator/, supervision/, workflows/).
        for subdir in ["architecture", "canon", "orchestrator", "supervision", "workflows"]:
            files = [p for p in (BAGO / "core" / subdir).iterdir() if p.is_file()]
            self.assertGreaterEqual(len(files), 1, subdir)
        # Spot-check that the canonical entry points are still present.
        for path in [
            BAGO / "core" / "canon" / "CANON.md",
            BAGO / "core" / "orchestrator" / "ORQUESTADOR_CENTRAL.md",
            BAGO / "core" / "workflows" / "workflow_ejecucion.md",
        ]:
            self.assertTrue(path.exists(), str(path))

        commands = (ROOT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
        self.assertIn("# BAGO Commands", commands)
        self.assertIn("AUTO-GENERATED", commands)

        testing = (ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
        self.assertIn("# BAGO Testing", testing)
        self.assertIn("Required Gates", testing)
        self.assertIn("Optional Gates", testing)

        security = (ROOT / "docs" / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("# BAGO Security", security)
        self.assertIn("Command Policy", security)
        self.assertIn("Interface Authority", security)
        self.assertIn("RL Authority", security)
        self.assertIn("Agents And Automation", security)
        self.assertIn("Stop Rules", security)

        mvp = (ROOT / "docs" / "MVP.md").read_text(encoding="utf-8")
        self.assertIn("# BAGO MVP Boundary", mvp)
        self.assertIn("Stable MVP", mvp)
        self.assertIn("Outside The MVP", mvp)
        self.assertIn("Product Rule", mvp)
        self.assertIn("docs/CLAIMS.md", mvp)
        self.assertIn("docs/SECURITY.md", mvp)

        resolver = (ROOT / "docs" / "RESOLVER_ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("# BAGO Resolver Architecture", resolver)
        self.assertIn("Live Authority", resolver)
        self.assertIn("Responsibilities", resolver)
        self.assertIn("docs/contracts/resolver_contract.json", resolver)
        self.assertNotIn("## Goal", resolver)
        self.assertNotIn("## Implementation Phases", resolver)

        rl = (ROOT / "docs" / "RL_ENGINE.md").read_text(encoding="utf-8")
        self.assertIn("# BAGO RL Engine", rl)
        self.assertIn("Live Authority", rl)
        self.assertIn("Current Contract", rl)
        self.assertIn("shadow/off", rl)
        self.assertIn("docs/SECURITY.md", rl)
        self.assertNotIn("## Policy Layer", rl)
        self.assertNotIn("## Authority Model", rl)

    def test_knowledge_examples_and_makefile(self) -> None:
        learned = (BAGO / "knowledge" / "learned_lessons.md").read_text(encoding="utf-8")
        self.assertIn("LL-001", learned)
        self.assertIn("CONTENIDO FUSIONADO DESDE RAÍZ", learned)

        evidence = ROOT / "docs" / "evidence" / "ui_shell_current"
        self.assertTrue((evidence / "report.md").exists())
        self.assertTrue((evidence / "manifest.json").exists())

        resolver_contract = ROOT / "docs" / "contracts" / "resolver_contract.json"
        self.assertTrue(resolver_contract.exists())
        self.assertIn("resolver", resolver_contract.read_text(encoding="utf-8"))

        # bago_wizard.py and BAGO_PAUSE.md were removed during 2026-Q2 cleanup.
        self.assertFalse((ROOT / "bago_wizard.py").exists(),
                         "bago_wizard.py was a v3.5.0-rc1 asset; removed in 2026-Q2 cleanup")
        self.assertFalse((BAGO / "tools" / "BAGO_PAUSE.md").exists(),
                         "BAGO_PAUSE.md was a v3.5.0-rc1 stub; removed in 2026-Q2 cleanup")
        # Makefile was removed (replaced by pyproject.toml + npm scripts).
        self.assertFalse((ROOT / "Makefile").exists(),
                         "Makefile removed in 2026-Q2 cleanup; use pyproject.toml / npm scripts")


if __name__ == "__main__":
    unittest.main()
