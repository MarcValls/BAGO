"""Tests for the BAGO Code Forge 3B context builder."""
from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from bago_core.codegen.context_builder import (
    MAX_FILE_BYTES,
    CodeContext,
    build_code_context,
)
from bago_core.codegen.task_classifier import classify_code_request
from bago_core.codegen.task_compiler import compile_code_task


def _classify_and_compile(tmp: Path, request: str, **kwargs):
    cls = classify_code_request(request, workspace_root=tmp)
    return compile_code_task(cls, objective=request, **kwargs)  # type: ignore[arg-type]


class ContextBuilderTests(unittest.TestCase):
    def test_build_context_extracts_symbols_and_imports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            target = root / "src" / "demo.py"
            target.write_text(
                textwrap.dedent(
                    """\
                    import os
                    from pathlib import Path

                    CONSTANT = 1

                    def greet(name: str) -> str:
                        return f"hi {name}"

                    class Greeter:
                        def __init__(self, name: str) -> None:
                            self.name = name
                    """
                ),
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests" / "test_demo.py").write_text(
                "from src.demo import greet\n\n\ndef test_greet():\n    assert greet('a') == 'hi a'\n",
                encoding="utf-8",
            )
            (root / "src" / "demo_other.py").write_text(
                "def other() -> None:\n    return None\n",
                encoding="utf-8",
            )
            contract = _classify_and_compile(
                root, "modifica src/demo.py para añadir validación"
            )
            ctx = build_code_context(contract, workspace_root=root)
            self.assertIsInstance(ctx, CodeContext)
            self.assertEqual(len(ctx.target_summaries), 1)
            summary = ctx.target_summaries[0]
            self.assertTrue(summary.exists)
            self.assertIn("greet", {s.name for s in summary.symbols})
            self.assertIn("Greeter", {s.name for s in summary.symbols})
            self.assertIn("os", summary.imports)
            self.assertIn("pathlib.Path", summary.imports)
            self.assertTrue(ctx.related_tests, "expected related tests to be discovered")
            self.assertTrue(
                any("test_demo.py" in t.path for t in ctx.related_tests)
            )
            # JSON-serializable
            json.dumps(ctx.to_dict())

    def test_missing_target_surfaces_as_exists_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = _classify_and_compile(
                root, "crea archivo src/brand_new.py vacío"
            )
            ctx = build_code_context(contract, workspace_root=root)
            self.assertEqual(len(ctx.target_summaries), 1)
            self.assertFalse(ctx.target_summaries[0].exists)
            self.assertEqual(ctx.target_summaries[0].body, "")

    def test_error_excerpt_is_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            (root / "src" / "broken.py").write_text("x = 1\n", encoding="utf-8")
            huge = "Traceback (most recent call last):\n" + ("a" * 5000)
            contract = _classify_and_compile(
                root, "corrige src/broken.py: " + huge
            )
            ctx = build_code_context(
                contract, workspace_root=root, error_excerpt=huge
            )
            self.assertLessEqual(len(ctx.error_excerpt), 2048)
            self.assertTrue(ctx.error_excerpt.startswith("Traceback"))

    def test_max_file_bytes_is_respected(self) -> None:
        # Sanity check on the constant itself. The context builder must
        # never feed an unbounded blob to a 3B model.
        self.assertEqual(MAX_FILE_BYTES, 64 * 1024)


if __name__ == "__main__":
    unittest.main()
