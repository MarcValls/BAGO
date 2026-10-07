"""Execute one read-only BAGO Gateway call and verify its Jaeger trace."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "backend" / ".bago" / "core"
for import_root in (REPO_ROOT / "backend", CORE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

os.environ["BAGO_OTEL_ENABLED"] = "1"
os.environ["BAGO_OTEL_PROPAGATE_CONTEXT"] = "1"
os.environ.setdefault("BAGO_OTEL_SERVICE_NAME", "bago-runtime")
os.environ.setdefault("BAGO_OTEL_ENDPOINT", "http://localhost:4318/v1/traces")

from authorization_boundary import AuthorizationBoundary  # noqa: E402
from execution_adapter_contract import ExecutionContext  # noqa: E402
from execution_gateway import ExecutionGateway  # noqa: E402
from execution_request import build_execution_request  # noqa: E402
from effect_registry import REGISTRY  # noqa: E402
from runtime_observability import force_flush  # noqa: E402


JAEGER_QUERY = os.environ.get("BAGO_JAEGER_QUERY", "http://localhost:16686").rstrip("/")
SERVICE_NAME = os.environ["BAGO_OTEL_SERVICE_NAME"]
EXPECTED_OPERATIONS = {
    "bago.execution_gateway.server_policy",
    "bago.authorization.server_policy",
    "bago.adapter.execute",
    "bago.external.http",
}


def _json_get(url: str, *, timeout: float = 3.0) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # local Jaeger query only
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Jaeger returned a non-object response")
    return payload


def _matching_trace(traces: list[dict], request_id: str) -> dict | None:
    for trace in traces:
        for span in trace.get("spans", []):
            tags = span.get("tags", []) if isinstance(span, dict) else []
            if any(
                isinstance(tag, dict)
                and tag.get("key") == "bago.request_id"
                and tag.get("value") == request_id
                for tag in tags
            ):
                return trace
    return None


def _operations(trace: dict) -> set[str]:
    return {
        str(span.get("operationName"))
        for span in trace.get("spans", [])
        if isinstance(span, dict) and span.get("operationName")
    }


def _attributes(trace: dict) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for span in trace.get("spans", []):
        if not isinstance(span, dict):
            continue
        result[str(span.get("operationName") or "")] = {
            str(tag.get("key")): tag.get("value")
            for tag in span.get("tags", [])
            if isinstance(tag, dict) and tag.get("key")
        }
    return result


def main() -> int:
    request = build_execution_request(
        effect_id="network.read",
        actor_kind="server",
        principal_id="bago-runtime-demo",
        session_id="observability-demo",
        source_surface="server.network.runtime_probe",
        target={
            "url": f"{JAEGER_QUERY}/api/services",
            "method": "GET",
            "network_class": "runtime_probe",
            "timeout": 5.0,
        },
        arguments={},
        scope="external-read",
        policy_version=REGISTRY.digest,
    )

    response, authorization = ExecutionGateway(AuthorizationBoundary()).execute_server_owned(
        request=request,
        context=ExecutionContext(),
    )
    try:
        service_payload = json.loads(response.read().decode("utf-8"))
    finally:
        response.close()
    flush_ok = force_flush()
    if not flush_ok:
        raise RuntimeError("OpenTelemetry provider could not flush its spans")

    deadline = time.monotonic() + 15.0
    trace = None
    while time.monotonic() < deadline:
        payload = _json_get(
            f"{JAEGER_QUERY}/api/traces?service={quote(SERVICE_NAME)}&limit=100"
        )
        traces = payload.get("data", [])
        traces = [item for item in traces if isinstance(item, dict)]
        trace = _matching_trace(traces, request.request_id)
        if trace is not None:
            break
        time.sleep(0.25)

    if trace is None:
        raise RuntimeError("Jaeger did not expose the BAGO Gateway request trace")
    observed = _operations(trace)
    missing = sorted(EXPECTED_OPERATIONS - observed)
    if missing:
        raise RuntimeError("Jaeger trace is missing operations: " + ", ".join(missing))
    attributes = _attributes(trace)
    root_attributes = attributes.get("bago.execution_gateway.server_policy", {})
    http_attributes = attributes.get("bago.external.http", {})
    if root_attributes.get("bago.request_id") != request.request_id:
        raise RuntimeError("Jaeger root span is not bound to the BAGO request_id")
    if root_attributes.get("bago.authorization.decision_id") != authorization.get("decision_id"):
        raise RuntimeError("Jaeger root span is not bound to the server-policy decision")
    if http_attributes.get("http.response.status_code") != 200:
        raise RuntimeError("Jaeger external HTTP span did not record HTTP 200")
    if http_attributes.get("bago.trace_context.injected") is not True:
        raise RuntimeError("W3C traceparent was not injected into the demo request")

    result = {
        "status": "PASS",
        "scope": "single-read-only-bago-gateway-request",
        "service_name": SERVICE_NAME,
        "jaeger_query": JAEGER_QUERY,
        "request_id": request.request_id,
        "parent_execution_id": request.parent_execution_id or None,
        "trace_id": str(trace.get("traceID") or ""),
        "operations": sorted(observed),
        "expected_operations": sorted(EXPECTED_OPERATIONS),
        "decision_id": authorization.get("decision_id"),
        "root_span_request_id": root_attributes.get("bago.request_id"),
        "external_http_status": http_attributes.get("http.response.status_code"),
        "traceparent_injected": http_attributes.get("bago.trace_context.injected"),
        "authorization_kind": authorization.get("kind"),
        "permit_id": authorization.get("permit_id"),
        "receipt_id": None,
        "jaeger_services_observed": service_payload.get("data", []),
        "trace_context_propagation": "W3C traceparent enabled for this local Jaeger request",
        "cost_usd": 0.0,
        "production_runtime": "NOT_VALIDATED",
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    observation_path = REPO_ROOT / ".run" / "agentic-data-lab-jaeger" / "bago-gateway-trace-observation.json"
    observation_path.parent.mkdir(parents=True, exist_ok=True)
    observation_path.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    print(f"Observation record: {observation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
