from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage  # noqa: E402
from task_response_contract import validate_task_response  # noqa: E402
from task_response_presenter import present_legacy_task_content, present_task_response, task_response_state  # noqa: E402
import session_manager  # noqa: E402
from session_turn_mixin import _requests_no_execution  # noqa: E402


def test_task_response_contract_validates_json_payload():
    payload = """
    ```json
    {
      "intent": "work",
      "objective": "modificar el parser",
      "facts": ["hay un engine de contexto"],
      "assumptions": [],
      "files_required": ["src/parser.py"],
      "symbols_required": ["Parser.parse"],
      "evidence": [{"type": "file", "path": "src/parser.py"}],
      "risks": [],
      "proposed_changes": ["actualizar el flujo"],
      "validation_actions": ["python -m pytest"],
      "missing_information": [],
      "confidence": 0.9
    }
    ```
    """
    report = validate_task_response(payload, intent="work")
    assert report.ok is True
    assert report.data["intent"] == "work"
    assert report.data["confidence"] == 0.9


def test_task_response_contract_rejects_empty_objective():
    payload = {key: [] for key in (
        "facts", "assumptions", "files_required", "symbols_required", "evidence", "risks",
        "proposed_changes", "validation_actions", "missing_information",
    )}
    payload.update({"intent": "work", "objective": "", "confidence": 1.0})
    report = validate_task_response(json.dumps(payload), intent="work")
    assert report.ok is False
    assert any(error.get("key") == "objective" for error in report.errors)


def test_explicit_read_only_request_does_not_enable_tools():
    assert _requests_no_execution("Traza un plan, sin ejecutar cambios.") is True
    assert _requests_no_execution("Corrige el archivo y ejecuta las pruebas") is False


def test_task_response_presenter_hides_internal_json():
    data = {
        "intent": "work", "objective": "Actualizar el flujo", "facts": [], "assumptions": [],
        "files_required": [], "symbols_required": [], "evidence": ["prueba ejecutada"], "risks": [],
        "proposed_changes": ["Separar contrato y respuesta"], "validation_actions": ["pytest"],
        "missing_information": [], "confidence": 0.9,
    }
    text = present_task_response(data)
    assert task_response_state(data) == "done"
    assert text.startswith("Actualizar el flujo")
    assert '"intent"' not in text
    legacy_text, state, parsed = present_legacy_task_content(json.dumps(data))
    assert legacy_text == text
    assert state == "done"
    assert parsed == data


def test_session_manager_repairs_invalid_task_json_once(tmp_path, monkeypatch):
    class JsonRetryAdapter(ProviderAdapter):
        def __init__(self, config=None):
            super().__init__("json-provider", config)
            self.calls = 0

        def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
            self.calls += 1
            if self.calls == 1:
                return ProviderResponse(
                    content="respuesta libre sin json",
                    model_used=model,
                    provider=self.provider_name,
                    finish_reason="stop",
                    usage=TokenUsage(input_tokens=12, output_tokens=8, total_tokens=20),
                )
            return ProviderResponse(
                content=(
                    "{"
                    '"intent":"work",'
                    '"objective":"actualizar el flujo",'
                    '"facts":["hay que validar JSON"],'
                    '"assumptions":[],'
                    '"files_required":["src/parser.py"],'
                    '"symbols_required":["Parser.parse"],'
                    '"evidence":[{"type":"tool","name":"read_lines"}],'
                    '"risks":[],'
                    '"proposed_changes":["reintentar con JSON valido"],'
                    '"validation_actions":["validate_task_response"],'
                    '"missing_information":[],'
                    '"confidence":0.8'
                    "}"
                ),
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=14, output_tokens=9, total_tokens=23),
            )

        def list_models(self):
            return [ModelInfo("json-model", "json-model", self.provider_name, 8192, 1024, "test", "free")]

        def health_check(self, timeout=5.0):
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok", latency_ms=1.0)

        def is_configured(self):
            return True

        def supports_tools(self):
            return False

        def supports_streaming(self):
            return False

    adapter = JsonRetryAdapter()

    def _init_adapter(self):
        self._adapter = adapter
        return {"corrected": False, "requested": self.model, "actual": self.model, "available": []}

    monkeypatch.setattr(session_manager.SessionManager, "_init_adapter", _init_adapter)

    with tempfile.TemporaryDirectory() as state_dir:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        mgr = session_manager.SessionManager(
            session_id="json-contract-test",
            provider="json-provider",
            model="json-model",
            base_path=str(workspace),
            state_root=state_dir,
        )
        try:
            response = mgr.send("crea un plan para actualizar el flujo")
            assert adapter.calls == 2
            assert response.startswith("actualizar el flujo")
            assert '"intent"' not in response
            assert mgr.last_receipt is not None
            contract = mgr.last_receipt.metadata.get("task_contract", {})
            assert contract.get("ok") is True
            assert contract.get("data", {}).get("intent") == "work"
            assert mgr.last_receipt.metadata.get("response_state") == "done"
            history_count = len(mgr.store.get_history())
            receipt = mgr.last_receipt
            internal = mgr.send_internal("devuelve el JSON solicitado")
            assert json.loads(internal)["intent"] == "work"
            assert len(mgr.store.get_history()) == history_count
            assert mgr.last_receipt is receipt
        finally:
            mgr.close()
