"""Opt-in OpenTelemetry projection for BAGO runtime execution.

Jaeger/OTel are observational only. This module never authorizes, dispatches,
or changes an ExecutionRequest, and telemetry errors are swallowed so they
cannot alter the governed execution path.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse


_LOCK = threading.RLock()
_PROVIDER: Any = None
_TRACER: Any = None


def capture_trace_context() -> Any:
    """Capture the current OTel context for BAGO's worker-thread turn runner."""
    if not _enabled():
        return None
    try:
        from opentelemetry import context

        return context.get_current()
    except Exception:
        return None


@contextmanager
def attach_trace_context(value: Any) -> Iterator[None]:
    """Restore a captured context in a worker thread; telemetry stays optional."""
    token = None
    try:
        if value is not None:
            from opentelemetry import context

            token = context.attach(value)
        yield
    finally:
        if token is not None:
            try:
                from opentelemetry import context

                context.detach(token)
            except Exception:
                pass


def _enabled() -> bool:
    return os.environ.get("BAGO_OTEL_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _endpoint() -> str:
    value = (
        os.environ.get("BAGO_OTEL_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "http://localhost:4318"
    ).strip().rstrip("/")
    if not value:
        return "http://localhost:4318/v1/traces"
    return value if value.endswith("/v1/traces") else value + "/v1/traces"


def _tracer() -> Any:
    global _PROVIDER, _TRACER
    if not _enabled():
        return None
    with _LOCK:
        if _TRACER is not None:
            return _TRACER
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": os.environ.get("BAGO_OTEL_SERVICE_NAME", "bago-runtime"),
                        "bago.observability.scope": "execution-runtime",
                    }
                )
            )
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=_endpoint()))
            )
            trace.set_tracer_provider(provider)
            _PROVIDER = provider
            _TRACER = trace.get_tracer("bago.execution", "1.0.0")
            return _TRACER
        except Exception:
            # Missing optional dependencies or a broken exporter must not
            # block authorization or material execution.
            return None


def _set(span: Any, key: str, value: Any) -> None:
    if span is None or value is None:
        return
    try:
        if isinstance(value, (bool, int, float, str)):
            span.set_attribute(key, value)
        elif isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value):
            span.set_attribute(key, tuple(value))
    except Exception:
        pass


def set_attributes(span: Any, attributes: Mapping[str, Any]) -> None:
    for key, value in attributes.items():
        _set(span, str(key), value)


def record_error(span: Any, error: BaseException) -> None:
    """Record error type/code only; exception messages may contain secrets."""
    if span is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode

        span.set_status(Status(StatusCode.ERROR))
    except Exception:
        pass
    _set(span, "error.type", type(error).__name__)
    _set(span, "bago.error.code", getattr(error, "code", None))
    _set(span, "bago.error.pre_dispatch", getattr(error, "pre_dispatch", None))


@contextmanager
def traced_span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    *,
    kind: str = "INTERNAL",
) -> Iterator[Any]:
    """Create an optional span while making telemetry failure non-blocking."""
    tracer = _tracer()
    manager = None
    span = None
    try:
        if tracer is not None:
            from opentelemetry.trace import SpanKind

            selected_kind = getattr(SpanKind, kind.upper(), SpanKind.INTERNAL)
            manager = tracer.start_as_current_span(
                name,
                kind=selected_kind,
                attributes=dict(attributes or {}),
                record_exception=False,
                set_status_on_exception=False,
            )
            span = manager.__enter__()
    except Exception:
        manager = None
        span = None

    try:
        yield span
    except BaseException as exc:
        record_error(span, exc)
        if manager is not None:
            try:
                manager.__exit__(type(exc), exc, exc.__traceback__)
            except Exception:
                pass
        raise
    else:
        if manager is not None:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                pass


def execution_attributes(request: Any) -> dict[str, Any]:
    """Safe correlation fields; never attach raw arguments or target paths."""
    return {
        "bago.request_id": str(getattr(request, "request_id", "") or ""),
        "bago.parent_execution_id": str(getattr(request, "parent_execution_id", "") or ""),
        "bago.effect_id": str(getattr(request, "effect_id", "") or ""),
        "bago.source_surface": str(getattr(request, "source_surface", "") or ""),
        "bago.operation_fingerprint": str(getattr(request, "fingerprint", "") or ""),
        "bago.target_digest": str(getattr(request, "target_digest", "") or ""),
        "bago.arguments_digest": str(getattr(request, "arguments_digest", "") or ""),
        "bago.world_state_digest": str(getattr(request, "world_state_digest", "") or ""),
    }


def result_receipt_id(result: Any) -> str:
    value = result
    if not isinstance(value, Mapping):
        to_dict = getattr(value, "to_dict", None)
        if not callable(to_dict):
            return ""
        try:
            value = to_dict()
        except Exception:
            return ""
    if not isinstance(value, Mapping):
        return ""
    receipt_id = value.get("receipt_id")
    if receipt_id:
        return str(receipt_id)
    receipt = value.get("receipt")
    if isinstance(receipt, Mapping):
        return str(receipt.get("receipt_id") or "")
    return ""


def external_http_attributes(url: str, method: str, network_class: str) -> dict[str, Any]:
    parsed = urlparse(str(url or ""))
    return {
        "http.request.method": str(method or "GET").upper(),
        "server.address": str(parsed.hostname or ""),
        "url.scheme": str(parsed.scheme or ""),
        "bago.network.class": str(network_class or ""),
    }


def inject_trace_context(headers: Mapping[str, Any]) -> dict[str, str]:
    """Optionally add W3C trace context to approved outbound network calls.

    Propagation is opt-in because it discloses a correlation identifier to the
    destination service. It never includes BAGO arguments, permits or receipts.
    """
    result = {str(key): str(value) for key, value in headers.items()}
    enabled = os.environ.get("BAGO_OTEL_PROPAGATE_CONTEXT", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if not enabled or not _enabled():
        return result
    try:
        from opentelemetry.propagate import inject

        carrier: dict[str, str] = {}
        inject(carrier)
        for key, value in carrier.items():
            if key.lower() in {"traceparent", "tracestate"}:
                result[key] = str(value)
    except Exception:
        pass
    return result


def force_flush(timeout_millis: int = 5000) -> bool:
    """Flush current-process spans for bounded CLI runs; safe for shutdown."""
    if _PROVIDER is None:
        return True
    try:
        return bool(_PROVIDER.force_flush(timeout_millis=timeout_millis))
    except Exception:
        return False


__all__ = [
    "attach_trace_context",
    "capture_trace_context",
    "execution_attributes",
    "external_http_attributes",
    "force_flush",
    "inject_trace_context",
    "record_error",
    "result_receipt_id",
    "set_attributes",
    "traced_span",
]
