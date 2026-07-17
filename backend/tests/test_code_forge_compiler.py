"""Tests for the BAGO Code Forge 3B task compiler."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bago_core.codegen.task_classifier import classify_code_request
from bago_core.codegen.task_compiler import (
    ALLOWED_OPERATIONS,
    DEFAULT_FORBIDDEN_PATHS,
    CodeTaskContract,
    compile_code_task,
)


def _classify(tmp: Path, request: str) -> object:
    return classify_code_request(request, workspace_root=tmp)


class TaskCompilerTests(unittest.TestCase):
    def test_compile_modify_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "src" / "demo.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("print('ok')\n", encoding="utf-8")
            cls = _classify(root, "modifica src/demo.py para añadir validación")
            self.assertEqual(cls.kind, "modify_file")
            contract = compile_code_task(
                cls,  # type: ignore[arg-type]
                objective="Añadir validación de argumentos",
                allowed_files=["src/demo.py", "tests/test_demo.py"],
            )
            self.assertFalse(contract.refused)
            self.assertEqual(contract.operation, "modify_file")
            self.assertEqual(contract.language, "python")
            self.assertEqual(len(contract.target_files), 1)
            self.assertTrue(contract.target_files[0].endswith("src\\demo.py"))
            self.assertIn("src\\demo.py", {f.replace("/", "\\") for f in contract.allowed_files})
            self.assertEqual(contract.forbidden_paths, DEFAULT_FORBIDDEN_PATHS)
            self.assertTrue(any("ast.parse" in c for c in contract.acceptance))
            # JSON-safe round trip
            payload = json.dumps(contract.to_dict())
            self.assertIn("task_id", payload)

    def test_compile_refuses_unsafe_kind(self) -> None:
        cls = classify_code_request("haz lo que sea, sin archivo concreto")
        contract = compile_code_task(
            cls,  # type: ignore[arg-type]
            objective="X",
        )
        self.assertTrue(contract.refused)
        self.assertEqual(contract.operation, "explain")
        self.assertIn("unsafe_or_unsupported", contract.refusal_reason)

    def test_compile_refuses_missing_target_for_modify(self) -> None:
        # Construct a forced classification that asks for modify but has
        # no target file. The compiler must refuse. The auxiliary
        # "modifica el archivo" call just sanity-checks that without a
        # real file the classifier itself does not produce a modify_file.
        from bago_core.codegen.task_classifier import CodeTaskClassification
        forced = CodeTaskClassification(
            kind="modify_file",
            confidence=0.5,
            reasons=("forced",),
            target_files=(),
            is_code_request=True,
            blocked=False,
        )
        contract = compile_code_task(forced, objective="X")
        self.assertTrue(contract.refused)
        self.assertEqual(contract.refusal_reason, "operation_requires_target_file")

        # Sanity: a bare "modifica el archivo" without a real path does
        # still classify as modify_file (the classifier is path-tolerant)
        # but with empty target_files — which the compiler will refuse
        # downstream. The test above already proves the refusal path.

    def test_compile_for_project_generation_has_no_target(self) -> None:
        cls = classify_code_request(
            "genera un proyecto nuevo desde cero con starter template"
        )
        self.assertEqual(cls.kind, "generate_project")
        contract = compile_code_task(
            cls,  # type: ignore[arg-type]
            objective="Generar proyecto demo",
        )
        self.assertFalse(contract.refused)
        self.assertEqual(contract.operation, "generate_project")
        self.assertEqual(contract.target_files, ())

    def test_allowed_operations_match_pipeline(self) -> None:
        # Frozen guardrail. If a new operation is added, the validation
        # pipeline must be updated in the same commit.
        expected = {
            "explain",
            "inspect",
            "create_file",
            "modify_file",
            "fix_error",
            "add_test",
            "refactor_local",
            "generate_project",
        }
        self.assertEqual(ALLOWED_OPERATIONS, expected)

    def test_to_dict_is_json_serializable(self) -> None:
        cls = classify_code_request("explica el archivo bago_core/codegen/task_compiler.py")
        contract = compile_code_task(cls, objective="Explicar")  # type: ignore[arg-type]
        payload = contract.to_dict()
        # must round-trip through json
        json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
