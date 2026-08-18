from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace


from reflexive_interpreter import analyze_question, format_reflexive_report, rules_contract_info, validate_rules_contract  # noqa: E402


def test_reflexive_interpreter_formalizes_self_referential_question():
    result = analyze_question(
        "Como traducirias esta pregunta a una formula matematica para entender lo que te estoy preguntando?",
        {"domain": "comprension", "constraints": ["conservar intencion"]},
    )

    payload = result.to_dict()
    assert payload["intent"] == "formalizar"
    assert payload["formalization"]["schema"] == "Q = D + X + C + R + O"
    assert "F(R*) ~= R*" in payload["formalization"]["relations"]
    assert payload["self_reference"]["detected"] is True
    assert payload["self_reference"]["depth"] == 2
    assert payload["fixed_point"]["applies"] is True
    assert payload["metrics"]["fidelity"] > 0
    assert payload["metrics"]["traceability"] > 0
    assert payload["rules"]["contract_version"] == "bago.reflexive.rules.v1"
    assert payload["rules"]["source"] == "file"
    assert payload["confidence"] >= 0.65


def test_reflexive_interpreter_marks_missing_referent_as_ambiguity():
    result = analyze_question("Haz eso sin romper lo anterior")
    payload = result.to_dict()

    assert payload["intent"] == "implementar"
    assert "missing_referent" in payload["evidence"][2]["value"]
    assert any(item["status"] == "needs_context" for item in payload["alternatives"])
    assert any("ambiguedad" in limit for limit in payload["limits"])


def test_format_reflexive_report_is_terminal_friendly():
    result = analyze_question("Que informacion falta para responder esto?")
    report = format_reflexive_report(result)

    assert "INTERPRETE REFLEXIVO" in report
    assert "Estructura Q=(D,X,C,R,O)" in report
    assert "Reglas:" in report
    assert "Metricas:" in report
    assert "Confianza:" in report


def test_reflexive_rules_contract_is_loaded_from_file():
    info = rules_contract_info()
    assert info["contract_version"] == "bago.reflexive.rules.v1"
    assert info["source"] == "file"
    assert info["validation"]["ok"] is True
    assert info["objective_count"] >= 8


def test_reflexive_rules_contract_validation_rejects_invalid_data():
    report = validate_rules_contract({"contract_version": "", "objective_hints": {}})
    assert report["ok"] is False
    assert any(item["name"] == "missing_contract_version" for item in report["errors"])


def test_interpret_command_is_registered_and_returns_contract():
    import commands  # noqa: E402

    mgr = SimpleNamespace(provider="test-provider", model="test-model", session_id="test-session")
    response = commands.execute(
        "/interpret Como formalizo esta pregunta para conservar la intencion?",
        mgr,
        SimpleNamespace(),
    )

    assert "interpret" in commands.COMMAND_REGISTRY
    assert response["ok"] is True
    assert "INTERPRETE REFLEXIVO" in response["message"]
    assert response["data"]["formalization"]["schema"] == "Q = D + X + C + R + O"
    rules = commands.execute("/interpret rules", mgr, SimpleNamespace())
    assert rules["ok"] is True
    assert rules["data"]["contract_version"] == "bago.reflexive.rules.v1"
    assert "Reglas del Interprete Reflexivo" in rules["message"]


def test_interpret_command_uses_session_reflexive_context_when_available():
    import commands  # noqa: E402

    class ContextAwareManager(SimpleNamespace):
        def analyze_reflexive_turn(self, text):
            return analyze_question(
                text,
                {
                    "domain": "bago-session",
                    "conversation_history": ["user: antes hablamos del canon"],
                    "constraints": ["provider=test-provider"],
                    "metadata": {"session_id": "ctx-session"},
                },
            ).to_dict()

    mgr = ContextAwareManager(provider="test-provider", model="test-model", session_id="ctx-session")
    response = commands.execute("/interpret Que falta aqui?", mgr, SimpleNamespace())

    assert response["ok"] is True
    assert any(item["kind"] == "recent_history" for item in response["data"]["context_factors"])


def test_session_receipt_stores_final_response_and_reflexive_analysis(tmp_path):
    import commands  # noqa: E402
    import session_manager  # noqa: E402
    from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage  # noqa: E402

    class ReceiptAdapter(ProviderAdapter):
        def __init__(self, config=None):
            super().__init__("reflexive-receipt", config)

        def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
            return ProviderResponse(
                content="he creado el archivo demo.py",
                model_used=model,
                provider=self.provider_name,
                finish_reason="stop",
                usage=TokenUsage(input_tokens=5, output_tokens=7, total_tokens=12),
            )

        def list_models(self):
            return [ModelInfo("receipt-model", "receipt-model", self.provider_name, 4096, 1024, "test", "free")]

        def health_check(self, timeout=5.0):
            return HealthStatus(ok=True, provider=self.provider_name, detail="ok")

        def is_configured(self):
            return True

        def supports_tools(self):
            return False

        def supports_streaming(self):
            return False

    session_manager.ADAPTER_REGISTRY["reflexive-receipt"] = ReceiptAdapter
    with tempfile.TemporaryDirectory() as state_dir:
        mgr = session_manager.SessionManager(
            session_id="reflexive-receipt-test",
            provider="reflexive-receipt",
            model="receipt-model",
            base_path=str(tmp_path),
            state_root=state_dir,
        )
        try:
            response = mgr.send("hola")
            receipt = mgr.last_receipt
            assert receipt is not None
            assert receipt.response_content == response
            assert receipt.metadata["claim_warning"] is True
            reflexive = receipt.metadata["reflexive_interpretation"]
            assert reflexive["literal_reading"] == "hola"
            assert reflexive["formalization"]["schema"] == "Q = D + X + C + R + O"
            assert reflexive["metrics"]["traceability"] > 0
            audit = receipt.metadata["reflexive_audit"]
            audit_path = Path(audit["path"])
            assert audit_path.exists()
            rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            assert rows[-1]["audit_id"] == audit["audit_id"]
            assert rows[-1]["receipt_id"] == receipt.envelope_id
            assert rows[-1]["analysis"]["literal_reading"] == "hola"
            history = commands.execute("/interpret history 5", mgr, SimpleNamespace())
            assert history["ok"] is True
            assert audit["audit_id"] in history["message"]
            interpreted = commands.execute("/interpret Que falta aqui?", mgr, SimpleNamespace())
            assert interpreted["ok"] is True
            command_audit = interpreted["data"]["reflexive_audit"]
            history_after_command = commands.execute("/interpret history 5", mgr, SimpleNamespace())
            assert command_audit["audit_id"] in history_after_command["message"]
        finally:
            mgr.close()
            session_manager.ADAPTER_REGISTRY.pop("reflexive-receipt", None)
