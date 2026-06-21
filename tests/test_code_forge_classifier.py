from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bago_core.codegen.task_classifier import CodeTaskClassification, classify_code_request


class CodeForgeClassifierTests(unittest.TestCase):
    def test_explain_request(self) -> None:
        result = classify_code_request("explica el archivo bago_core/codegen/task_classifier.py")
        self.assertEqual(result.kind, "explain")
        self.assertTrue(result.is_code_request)
        self.assertIn("file_mentioned", result.reasons)

    def test_modify_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "src" / "demo.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("print('ok')\n", encoding="utf-8")
            result = classify_code_request(
                "modifica src/demo.py para añadir validación",
                workspace_root=root,
            )
            self.assertEqual(result.kind, "modify_file")
            self.assertIn("src\\demo.py", {p.replace("/", "\\") for p in result.target_files})
            self.assertTrue(result.existing_files)
            self.assertFalse(result.blocked)

    def test_create_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = classify_code_request(
                "crea tests/test_forge_classifier.py",
                workspace_root=root,
            )
            self.assertEqual(result.kind, "create_file")
            self.assertTrue(result.missing_files)
            self.assertFalse(result.blocked)

    def test_fix_error_request(self) -> None:
        result = classify_code_request(
            "traceback en bago_core/codegen/task_classifier.py con SyntaxError expected ':'",
        )
        self.assertEqual(result.kind, "fix_error")
        self.assertTrue(result.is_code_request)

    def test_add_test_request(self) -> None:
        result = classify_code_request("añade un test para el clasificador determinista")
        self.assertEqual(result.kind, "add_test")

    def test_refactor_request(self) -> None:
        result = classify_code_request("refactoriza el módulo sin cambiar la API pública")
        self.assertEqual(result.kind, "refactor_local")

    def test_generate_project_request(self) -> None:
        result = classify_code_request("genera un proyecto nuevo desde cero")
        self.assertEqual(result.kind, "generate_project")

    def test_dangerous_shell_request_is_blocked(self) -> None:
        result = classify_code_request("powershell -c Remove-Item -Recurse -Force C:\\temp")
        self.assertEqual(result.kind, "unsafe_or_unsupported")
        self.assertTrue(result.blocked)
        self.assertTrue(result.is_code_request)

    def test_non_code_chat_is_not_blocked(self) -> None:
        result = classify_code_request("hola, ¿qué tal?")
        self.assertEqual(result.kind, "unsafe_or_unsupported")
        self.assertFalse(result.is_code_request)
        self.assertFalse(result.blocked)

    def test_session_manager_blocks_before_adapter(self) -> None:
        import sys

        core = Path(__file__).resolve().parents[1] / ".bago" / "core"
        if str(core) not in sys.path:
            sys.path.insert(0, str(core))

        from session_manager import SessionManager

        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mgr = SessionManager(base_path=td, state_root=str(state_root), provider="ollama-local", model="llama3.2:3b")
            try:
                def _boom(*args, **kwargs):
                    raise AssertionError("adapter should not be used for blocked requests")

                mgr._ensure_adapter = _boom  # type: ignore[method-assign]
                result = mgr.send("powershell -c Remove-Item -Recurse -Force C:\\temp")
                self.assertIn("rechazada", result.lower())
                self.assertIsNotNone(mgr.last_code_task)
                self.assertTrue(mgr.last_code_task["blocked"])
                self.assertEqual(mgr.last_code_task["kind"], "unsafe_or_unsupported")
            finally:
                mgr.close()


if __name__ == "__main__":
    unittest.main()
