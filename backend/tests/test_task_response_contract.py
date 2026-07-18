from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage  # noqa: E402
from task_response_contract import validate_task_response  # noqa: E402
import session_manager  # noqa: E402


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
            data = json.loads(response)
            assert adapter.calls == 2
            assert data["intent"] == "work"
            assert data["confidence"] == 0.8
            assert data["files_required"] == ["src/parser.py"]
            assert mgr.last_receipt is not None
            assert mgr.last_receipt.metadata.get("task_contract", {}).get("ok") is True
        finally:
            mgr.close()
