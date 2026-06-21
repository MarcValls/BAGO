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
        for name in [
            "00_CEREBRO_BAGO.md",
            "01_PLANTILLA_PROMPT.md",
            "02_FABRICA_PROMPTS.md",
            "03_ESTADO_BAGO.md",
            "04_CONTRATOS_DE_ROL.md",
            "05_GOBERNANZA_DE_SESION.md",
            "06_MATRIZ_DE_ACTIVACION.md",
            "07_PROTOCOLO_DE_CAMBIO.md",
        ]:
            self.assertTrue((BAGO / "core" / name).exists(), name)

        for subdir in ["architecture", "canon", "orchestrator", "supervision", "workflows"]:
            files = [p for p in (BAGO / "core" / subdir).iterdir() if p.is_file()]
            self.assertGreaterEqual(len(files), 1, subdir)

        for doc in ["KERNEL_LOCKDOWN.md", "COMMAND_AUDIT.md"]:
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            self.assertIn("#", text, doc)

    def test_knowledge_examples_and_makefile(self) -> None:
        learned = (BAGO / "knowledge" / "learned_lessons.md").read_text(encoding="utf-8")
        self.assertIn("LL-001", learned)
        self.assertIn("CONTENIDO FUSIONADO DESDE RAÍZ", learned)

        examples = [p for p in (ROOT / "examples").rglob("*") if p.is_file()]
        self.assertGreaterEqual(len(examples), 79)
        self.assertTrue((ROOT / "bago_wizard.py").exists())
        self.assertTrue((BAGO / "tools" / "BAGO_PAUSE.md").exists())

        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        for target in ["help", "validate", "pack", "install", "uninstall", "clean"]:
            self.assertRegex(makefile, rf"(?m)^{target}:")


if __name__ == "__main__":
    unittest.main()

