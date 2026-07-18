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

    def test_pasted_document_with_paths_is_not_treated_as_code_request(self) -> None:
        text = """
# Auditoría fina de `src.zip`

Fecha de auditoría: 26 de junio de 2026.

## 1. Dictamen

El proyecto es un prototipo React visualmente funcional, pero no es todavía una aplicación Android fiable.

## 2. Verificaciones ejecutadas

- `npm ci --ignore-scripts`
- `npm run build`
- `npx tsc -b`
- `npm audit --json`
- `src/App.tsx`
- `src/components/PushBootstrap.tsx`

## 3. Bloqueos P0

### P0.1. La persistencia no está resuelta para Android

Evidencia:

- `src/lib/types.ts:15-22`
- `src/App.tsx:107-113`
- `capacitor.config.ts:6`

Corrección obligatoria:

1. Crear una interfaz de almacenamiento independiente del framework.
2. Implementar un adaptador Android real.
3. Eliminar `useKV` de la lógica de dominio móvil.
"""
        result = classify_code_request(text)
        self.assertEqual(result.kind, "unsafe_or_unsupported")
        self.assertFalse(result.is_code_request)
        self.assertFalse(result.blocked)
        self.assertIn("pasted_document_detected", result.reasons)

    def test_session_manager_blocks_before_adapter(self) -> None:
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

    def test_session_manager_ignores_pasted_documents(self) -> None:
        from session_manager import SessionManager

        text = """
# Auditoría fina de `src.zip`

Fecha de auditoría: 26 de junio de 2026.

## 1. Dictamen

El proyecto es un prototipo React visualmente funcional, pero no es todavía una aplicación Android fiable ni una base preparada para producción.

Estado estimado:

- Interfaz y flujo básico: aceptables como prototipo.
- Integridad de los cálculos: no aceptable.
- Persistencia móvil: no resuelta.
- Validación de calidad: no operativa.
- Seguridad de producción Android: no aceptable.
- Accesibilidad: insuficiente.

## 2. Verificaciones ejecutadas

- `npm ci --ignore-scripts`
- `npm run build`
- `npx tsc -b`
- `npm audit --json`

## 3. Bloqueos P0

### P0.1. La persistencia no está resuelta para Android

Evidencia:

- `src/App.tsx:17` usa `useKV` de `@github/spark` para guardar contactos.
- `src/components/PushBootstrap.tsx:7` usa el mismo sistema para guardar el token push.
- `capacitor.config.ts:6` empaqueta únicamente los archivos estáticos de `dist` dentro del WebView.

Corrección obligatoria:

1. Crear una interfaz de almacenamiento independiente del framework.
2. Implementar un adaptador Android real.
3. Eliminar `useKV` de la lógica de dominio móvil.

### P0.2. La puerta de calidad de compilación es falsa

Evidencia:

- `package.json:9` ejecuta `tsc -b --noCheck` antes de Vite.
- `package.json:10` define lint, pero no existe configuración ESLint compatible con la versión nueve.
"""

        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            mgr = SessionManager(base_path=td, state_root=str(state_root), provider="ollama-local", model="llama3.2:3b")
            try:
                task = mgr._classify_code_request(text)
                self.assertIsNone(task)
            finally:
                mgr.close()

    def test_session_manager_status_exposes_code_task_contract(self) -> None:
        from types import SimpleNamespace

        from session_manager import SessionManager

        mgr = SessionManager.__new__(SessionManager)
        mgr.provider = "ollama-local"
        mgr.model = "llama3.2:3b"
        mgr.bago_mode = "B"
        mgr.base_path = Path("C:/temp")
        mgr.framework_root = Path("C:/temp/.bago")
        mgr.project_root = Path("C:/temp")
        mgr.workspace_state_root = Path("C:/temp/.gabo")
        mgr.workspace_scope_root = Path("C:/temp")
        mgr.workspace_id = "ws-test"
        mgr.session_id = "session-test"
        mgr.persistent_goal = ""
        mgr.active_bridges = ["ollama-local"]
        mgr.created_at = 0
        mgr.total_tokens = 0
        mgr.total_calls = 0
        mgr.last_switch_at = None
        mgr.switch_log = []
        mgr.last_receipt = None
        mgr.last_context_envelope = None
        mgr.last_context_benchmark = None
        mgr.last_cognitive_benchmark = None
        mgr.last_context_certification = None
        mgr.last_global_review = {"required": False, "reasons": []}
        mgr.last_code_task = {"kind": "modify_file"}
        mgr.last_code_task_contract = {
            "operation": "modify_file",
            "plan": {"read_files": ["src/demo.py"], "edit_files": ["src/demo.py"], "create_files": [], "verify_steps": ["check"]},
        }
        mgr.config = SimpleNamespace(get=lambda *_args, **_kwargs: False)
        mgr.store = SimpleNamespace(get_meta=lambda: {}, get_history=lambda: [])
        mgr.agent_gateway = SimpleNamespace(active=SimpleNamespace(name="default"))
        mgr._ensure_adapter = lambda: SimpleNamespace(health_check=lambda: SimpleNamespace(ok=True, detail="ok", latency_ms=0.0))
        mgr._git_info = lambda: ("repo", "main")
        mgr.measure_context = lambda: {"ok": True}
        mgr._binding_state = lambda: {"binding_confirmed": True, "binding_reason": "ok"}
        mgr.workspace_state = lambda: {"state": "linked_confirmed"}
        mgr.welcome_state = lambda: {}
        mgr.menu_state = lambda: {}
        mgr.roadmap_state = lambda: {}
        mgr._global_review_state = lambda: {"required": False, "reasons": []}

        status = mgr.status()
        self.assertEqual(status["code_task_contract"]["operation"], "modify_file")
        self.assertEqual(status["code_task_contract"]["plan"]["read_files"], ["src/demo.py"])


if __name__ == "__main__":
    unittest.main()
