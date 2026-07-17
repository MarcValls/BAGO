"""test_fix_direct.py — Validación directa del fix, sin depender del
SessionManager real. Simulamos exactamente el caso: el session_mgr emite
un payload canónico de error, y el handler debe interceptarlo.
"""
import json
import sys
import time
import urllib.request

# Pegamos el payload maldito idéntico al que reportaste
LEAKED = json.dumps({
    "assumptions": [],
    "confidence": 0.0,
    "evidence": [{
        "errors": [{
            "detail": "Expecting value: line 1 column 1 (char 0)",
            "name": "json_parse"
        }],
        "previous_response_excerpt": (
            "\n\nPor favor, espera un momento mientras genero el texto con "
            "diagramas Mermaid para ti.\n\n\n```mermaid\ngraph LR\n participan..."
        ),
        "type": "validation_error"
    }],
    "files_required": [],
    "intent": "work",
    "missing_information": ["Expecting value: line 1 column 1 (char 0)"],
    "objective": "genera un texto hablando sobre bago con diagramas mermaid",
    "proposed_changes": [],
    "risks": ["invalid_model_response"],
    "symbols_required": [],
    "validation_actions": ["repair_response", "revalidate_contract"],
}, ensure_ascii=False, indent=2)

# Nos saltamos el router y vamos directo al detector. Esto es lo que haría
# el session_mgr.send_stream() si el routing hubiera funcionado.
import importlib.util
spec = importlib.util.spec_from_file_location(
    "epf",
    r".bago\api\error_payload_filter.py",
)
epf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epf)

print("=" * 60)
print("TEST 1: detector")
print("=" * 60)
detected = epf.is_canonical_error_payload(LEAKED)
print(f"  is_canonical_error_payload(payload maldito) = {detected}")
assert detected, "FALLO: el detector no pilló el payload"

print()
print("=" * 60)
print("TEST 2: rewrite a user-friendly")
print("=" * 60)
friendly = epf.rewrite_to_user_friendly(LEAKED)
print(f"  friendly = {friendly!r}")
assert friendly.startswith("⚠️"), "FALLO: mensaje friendly no empieza con ⚠️"
assert "Expecting value" in friendly, "FALLO: falta el detalle del error"
assert "repair_response" not in friendly, "FALLO: filtró metadatos internos"
assert "validation_actions" not in friendly, "FALLO: filtró clave interna"
assert "mermaid" not in friendly.lower() or "Detalle" in friendly, "FALLO: filtra excerpt crudo"

print()
print("=" * 60)
print("TEST 3: diagnostic estructurado")
print("=" * 60)
diag = epf.extract_diagnostic(LEAKED)
print(f"  diag = {json.dumps(diag, ensure_ascii=False, indent=2)}")
assert diag["diagnostic"] is True
assert diag["kind"] == "validation_error"
assert diag["detail"] == "Expecting value: line 1 column 1 (char 0)"
assert "validation_actions" not in diag or diag.get("detail"), "FALLO: diagnostic demasiado verboso"

print()
print("=" * 60)
print("TEST 4: no falsos positivos")
print("=" * 60)

negatives = [
    "Aquí va un texto normal con un Mermaid válido.",
    "# Título\n\nTexto en markdown",
    "```mermaid\ngraph LR\n  A --> B\n```",
    '{"foo": "bar"}',
    '{"evidence": [{"type": "user_message", "content": "hola"}]}',  # evidence sin type=validation_error
    '{"validation_actions": ["something_else"]}',  # actions distintas
    "1234",
    "null",
    "",
    None,
]
for n in negatives:
    got = epf.is_canonical_error_payload(n)
    print(f"  {type(n).__name__:8} {str(n)[:50]:50} -> {got}")
    assert not got, f"FALLO: falso positivo en {n!r}"

print()
print("=" * 60)
print("TODOS LOS TESTS PASADOS")
print("=" * 60)
