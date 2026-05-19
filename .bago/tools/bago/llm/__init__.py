"""bago.llm — Subpaquete LLM de BAGO.

Re-exporta todos los símbolos públicos para mantener compatibilidad con el
import anterior: ``from bago.llm import chat``, ``from bago.llm import _is_cloud_auth_error``,
etc.
"""

# ── Excepciones ───────────────────────────────────────────────────────────────
from .errors import (
    OllamaNoModelAvailable,
    _is_ctx_overflow,
    _is_cloud_auth_error,
    _is_cloud_connection_error,
    _is_cloud_quota_error,
    _is_ollama_model_not_found,
    _is_ollama_unreachable,
    classify_provider_error,
)

# ── Calidad ───────────────────────────────────────────────────────────────────
from .quality import (
    _jaccard,
    _dedup_paragraphs,
    _last_assistant,
    _REPEAT_THRESHOLD,
    _response_is_garbage,
    _contains_url,
    _needs_cloud_for_url,
)

# ── Routing ───────────────────────────────────────────────────────────────────
from .routing import (
    _model_size_score,
    _ollama_fallback_model,
    _CLOUD_EQUIV,
    _build_escalation_chain,
    _ESCALATE_PROV_ORDER,
    _TASK_CLOUD_HINTS,
    _deduce_cloud_provider,
    _escalate_model,
    _cloud_escalation_for_quality,
    _provider_error_fallbacks,
)

# ── Llamada de bajo nivel ─────────────────────────────────────────────────────
from .call import _llm_call

# ── Estrategias ───────────────────────────────────────────────────────────────
from .strategies import run_chain, run_ensemble

# ── Orquestador ───────────────────────────────────────────────────────────────
from .orchestrator import chat

__all__ = [
    # errors
    "OllamaNoModelAvailable",
    "_is_ctx_overflow",
    "_is_cloud_auth_error",
    "_is_cloud_connection_error",
    "_is_cloud_quota_error",
    "_is_ollama_model_not_found",
    "_is_ollama_unreachable",
    "classify_provider_error",
    # quality
    "_jaccard",
    "_dedup_paragraphs",
    "_last_assistant",
    "_REPEAT_THRESHOLD",
    "_response_is_garbage",
    "_contains_url",
    "_needs_cloud_for_url",
    # routing
    "_model_size_score",
    "_ollama_fallback_model",
    "_CLOUD_EQUIV",
    "_build_escalation_chain",
    "_ESCALATE_PROV_ORDER",
    "_TASK_CLOUD_HINTS",
    "_deduce_cloud_provider",
    "_escalate_model",
    "_cloud_escalation_for_quality",
    "_provider_error_fallbacks",
    # call
    "_llm_call",
    # strategies
    "run_chain",
    "run_ensemble",
    # orchestrator
    "chat",
]
