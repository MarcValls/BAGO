"""Ask the configured BAGO agent for a read-only modularization review and trace it."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "backend" / ".bago" / "core"
for import_root in (REPO_ROOT / "backend", CORE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

os.environ["BAGO_OTEL_ENABLED"] = "1"
os.environ["BAGO_OTEL_PROPAGATE_CONTEXT"] = "0"
os.environ.setdefault("BAGO_OTEL_SERVICE_NAME", "bago-runtime")
os.environ.setdefault("BAGO_OTEL_ENDPOINT", "http://localhost:4318/v1/traces")

from runtime_observability import force_flush, set_attributes, traced_span
from session_manager import SessionManager

JAEGER_QUERY = os.environ.get("BAGO_JAEGER_QUERY", "http://localhost:16686").rstrip("/")
SERVICE_NAME = os.environ["BAGO_OTEL_SERVICE_NAME"]
PROVIDER = os.environ.get("BAGO_REVIEW_PROVIDER", "ollama-cloud")
MODEL = os.environ.get("BAGO_REVIEW_MODEL", "glm-5.3-flash")
FILES = (
    REPO_ROOT / "backend" / ".bago" / "core" / "session_turn_mixin.py",
    REPO_ROOT / "backend" / ".bago" / "core" / "execution_gateway.py",
)


def _structure(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    symbols: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append({
                "kind": type(node).__name__,
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "methods": [
                    child.name for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                ] if isinstance(node, ast.ClassDef) else [],
            })
    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "lines": len(text.splitlines()),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "symbols": symbols,
    }


def _jaeger_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Jaeger returned a non-object response")
    return payload


def _trace_for_session(session_id: str) -> dict | None:
    payload = _jaeger_json(
        f"{JAEGER_QUERY}/api/traces?service={quote(SERVICE_NAME)}&limit=100"
    )
    for trace in payload.get("data", []):
        for span in trace.get("spans", []):
            if any(
                tag.get("key") == "bago.session_id" and tag.get("value") == session_id
                for tag in span.get("tags", []) if isinstance(tag, dict)
            ):
                return trace
    return None


def main() -> int:
    session_id = "obs-review-" + uuid.uuid4().hex[:12]
    inventory = [_structure(path) for path in FILES]
    prompt = (
        "Haz una revisión técnica READ-ONLY de modularización para estos dos archivos de BAGO. "
        "No edites archivos, no ejecutes herramientas ni propongas una división por tamaño solamente.\n\n"
        "Evalúa cohesión, responsabilidades mezcladas, dependencias y riesgos de extraer módulos. "
        "Devuelve: (1) juicio por archivo: mantener/modularizar/posponer, (2) seams concretos con "
        "responsabilidad y dependencias, (3) orden incremental con módulos destino propuestos, "
        "(4) contratos/invariantes que deben quedar estables, (5) pruebas de caracterización, y "
        "(6) evidencia necesaria antes/después. Distingue hechos del inventario de inferencias.\n\n"
        "Determina especialmente si conviene separar el ciclo de turno, el manejo de herramientas, "
        "la validación de la respuesta y la observabilidad del SessionTurnMixin; y si en "
        "ExecutionGateway conviene extraer spans/helpers o responsabilidades semánticas sin "
        "mover autoridad de autorización, claims, leases ni dispatch. No declares BAGO fiable "
        "globalmente por esta revisión: explica qué prueba y qué no.\n\n"
        "Inventario AST calculado del checkout actual (rutas, hashes, líneas, símbolos y métodos):\n"
        + json.dumps(inventory, ensure_ascii=False, indent=2)
    )
    prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    manager = SessionManager(
        session_id=session_id,
        provider=PROVIDER,
        model=MODEL,
        base_path=str(REPO_ROOT),
    )
    try:
        with traced_span("bago.agent.request", {
            "bago.session_id": session_id,
            "bago.request.digest": prompt_digest,
            "bago.request.kind": "read_only_modularization_review",
            "bago.agent.provider": PROVIDER,
            "bago.agent.model": MODEL,
            "bago.review.file_count": len(FILES),
        }) as span:
            with traced_span("bago.agent.execute", {
                "bago.session_id": session_id,
                "bago.agent.mode": "internal_structured_review",
            }):
                response = manager.send_internal(prompt)
            provider_error = response.startswith("Error ")
            response_state = "provider_error" if provider_error else "completed_internal_review"
            set_attributes(span, {
                "bago.response.state": response_state,
                "bago.response.digest": hashlib.sha256(response.encode("utf-8", errors="replace")).hexdigest(),
                "bago.response.bytes": len(response.encode("utf-8", errors="replace")),
            })
        if not force_flush():
            raise RuntimeError("OpenTelemetry provider could not flush its spans")
    finally:
        manager.close()

    deadline = time.monotonic() + 20
    trace = None
    while time.monotonic() < deadline:
        trace = _trace_for_session(session_id)
        if trace:
            break
        time.sleep(0.3)
    if trace is None:
        raise RuntimeError("Jaeger did not expose the BAGO modularization review trace")

    operations = sorted({
        str(span.get("operationName")) for span in trace.get("spans", [])
        if span.get("operationName")
    })
    required = {
        "bago.agent.request",
        "bago.agent.execute",
        "bago.agent.model_call",
        "bago.artifact.final_response",
    }
    missing = sorted(required - set(operations))
    if missing:
        raise RuntimeError("Jaeger trace misses expected agent stages: " + ", ".join(missing))

    report = {
        "status": "FAIL_PROVIDER" if provider_error else "PASS",
        "trace_status": "PASS",
        "scope": "single-read-only-agent-modularization-review",
        "session_id": session_id,
        "trace_id": str(trace.get("traceID") or ""),
        "service_name": SERVICE_NAME,
        "provider": PROVIDER,
        "model": MODEL,
        "prompt_sha256": prompt_digest,
        "source_inventory": inventory,
        "operations": operations,
        "response_state": response_state,
        "review": response,
        "bago_reliability": "NOT_ESTABLISHED_BY_SINGLE_SELF_REVIEW",
        "artifact_kind": "agent_response_in_memory",
        "production_runtime": "NOT_VALIDATED",
    }
    path = REPO_ROOT / ".run" / "agentic-data-lab-jaeger" / "bago-modularization-review.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Jaeger trace: {JAEGER_QUERY}/trace/{report['trace_id']}")
    print(f"Review record: {path}")
    return 2 if provider_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
