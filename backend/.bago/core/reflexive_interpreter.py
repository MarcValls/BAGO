#!/usr/bin/env python3
"""Deterministic reflexive interpretation core for BAGO.

This module implements the first vertical slice of the Reflexive Interpreter:
question parsing, ambiguity detection, formalization, metacognitive audit,
self-reference detection, and a terminal-friendly report.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:
    from intent_engine import classify_intent
except Exception:  # pragma: no cover - keeps the module usable in isolation.
    classify_intent = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ReflexiveQuestionContext:
    domain: str = ""
    conversation_history: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    user_profile: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_any(cls, value: Mapping[str, Any] | None) -> "ReflexiveQuestionContext":
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        history = data.get("conversation_history") or data.get("history") or ()
        constraints = data.get("constraints") or ()
        if isinstance(history, str):
            history = (history,)
        if isinstance(constraints, str):
            constraints = (constraints,)
        return cls(
            domain=str(data.get("domain") or ""),
            conversation_history=tuple(str(item) for item in history if str(item).strip()),
            constraints=tuple(str(item) for item in constraints if str(item).strip()),
            user_profile=dict(data.get("user_profile") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ReflexiveInterpretationResult:
    question_id: str
    literal_reading: str
    intent: str
    operational_intent: str
    data: tuple[dict[str, Any], ...]
    unknowns: tuple[dict[str, Any], ...]
    context_factors: tuple[dict[str, Any], ...]
    restrictions: tuple[dict[str, Any], ...]
    assumptions: tuple[dict[str, Any], ...]
    alternatives: tuple[dict[str, Any], ...]
    selected_interpretation: dict[str, Any]
    formalization: dict[str, Any]
    evidence: tuple[dict[str, Any], ...]
    audit_trail: tuple[dict[str, Any], ...]
    self_reference: dict[str, Any]
    fixed_point: dict[str, Any]
    metrics: dict[str, float]
    rules: dict[str, Any]
    final_answer: str
    limits: tuple[str, ...]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_INTERROGATIVE_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("por que", "cause", "causa o justificacion solicitada"),
    ("para que", "purpose", "finalidad solicitada"),
    ("como", "method", "metodo o procedimiento solicitado"),
    ("que", "concept", "concepto o entidad solicitada"),
    ("cual", "selection", "seleccion entre opciones"),
    ("cuales", "selection_set", "conjunto de opciones"),
    ("quien", "agent", "persona o agente"),
    ("cuando", "time", "momento o secuencia temporal"),
    ("donde", "place", "ubicacion o ambito"),
    ("cuanto", "amount", "cantidad o medida"),
)

_OBJECTIVE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "formalizar",
        (
            "formula",
            "matematica",
            "formaliza",
            "formalizo",
            "formalizar",
            "formalizacion",
            "logica",
            "representacion",
            "representar",
            "traduce",
            "traducir",
            "traducirias",
        ),
    ),
    ("implementar", ("implementa", "haz", "hazlo", "crea", "construye", "genera", "desarrolla", "fusiona", "sustituye")),
    ("analizar", ("analiza", "revisa", "inspecciona", "compara", "audita", "evalua")),
    ("explicar", ("explica", "entiende", "comprende", "aclara", "define")),
    ("decidir", ("elige", "decide", "prioriza", "selecciona")),
    ("demostrar", ("demuestra", "prueba", "verifica", "certifica", "evidencia")),
    ("optimizar", ("optimiza", "mejora", "reduce", "maximiza", "minimiza")),
    ("predecir", ("predice", "estima", "anticipa", "pronostica")),
)

_DEICTIC_TERMS = {
    "esto",
    "eso",
    "aquello",
    "aqui",
    "ahi",
    "anterior",
    "lo anterior",
    "esa cosa",
    "esta cosa",
}

_SELF_REFERENCE_TERMS = {
    "pregunta",
    "esta pregunta",
    "lo que te estoy preguntando",
    "interpretacion",
    "comprension",
    "formalizacion",
    "metacognicion",
    "autorreferencia",
    "proceso de interpretar",
    "respuesta parece correcta",
}

_RULES_CONTRACT_VERSION = "bago.reflexive.rules.builtin"
_RULES_SOURCE = "builtin"
_RULES_PATH = ""
_RULES_VALIDATION = {"ok": True, "errors": [], "warnings": ["using_builtin_rules"]}


def validate_rules_contract(data: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not isinstance(data.get("contract_version"), str) or not str(data.get("contract_version")).strip():
        errors.append({"name": "missing_contract_version", "detail": "contract_version must be a non-empty string"})
    markers = data.get("interrogative_markers")
    if not isinstance(markers, list) or not markers:
        errors.append({"name": "invalid_interrogative_markers", "detail": "interrogative_markers must be a non-empty array"})
    else:
        for index, item in enumerate(markers):
            if not (isinstance(item, list) and len(item) == 3 and all(isinstance(part, str) and part.strip() for part in item)):
                errors.append({"name": "invalid_interrogative_marker", "index": index, "detail": "marker must be [marker, kind, description]"})
                break
    objectives = data.get("objective_hints")
    if not isinstance(objectives, dict) or not objectives:
        errors.append({"name": "invalid_objective_hints", "detail": "objective_hints must be a non-empty object"})
    else:
        for objective, hints in objectives.items():
            if not isinstance(objective, str) or not objective.strip():
                errors.append({"name": "invalid_objective_name", "detail": "objective names must be non-empty strings"})
                break
            if not isinstance(hints, list) or not any(str(hint).strip() for hint in hints):
                errors.append({"name": "invalid_objective_hints_entry", "objective": objective, "detail": "each objective needs at least one hint"})
                break
    for key in ("deictic_terms", "self_reference_terms"):
        value = data.get(key)
        if not isinstance(value, list) or not any(str(item).strip() for item in value):
            errors.append({"name": f"invalid_{key}", "detail": f"{key} must be a non-empty array"})
    if str(data.get("contract_version", "")).strip() != "bago.reflexive.rules.v1":
        warnings.append("unknown_contract_version")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _load_rules_contract() -> None:
    global _INTERROGATIVE_MARKERS
    global _OBJECTIVE_HINTS
    global _DEICTIC_TERMS
    global _SELF_REFERENCE_TERMS
    global _RULES_CONTRACT_VERSION
    global _RULES_SOURCE
    global _RULES_PATH
    global _RULES_VALIDATION

    path = Path(__file__).with_name("reflexive_rules.json")
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    validation = validate_rules_contract(data)
    _RULES_VALIDATION = validation
    if not validation["ok"]:
        _RULES_SOURCE = "invalid_file_fallback_builtin"
        _RULES_PATH = str(path)
        return

    markers = data.get("interrogative_markers")
    if isinstance(markers, list):
        parsed_markers = []
        for item in markers:
            if isinstance(item, list) and len(item) == 3 and all(isinstance(part, str) for part in item):
                parsed_markers.append((item[0], item[1], item[2]))
        if parsed_markers:
            _INTERROGATIVE_MARKERS = tuple(parsed_markers)

    objectives = data.get("objective_hints")
    if isinstance(objectives, dict):
        parsed_objectives = []
        for objective, hints in objectives.items():
            if isinstance(objective, str) and isinstance(hints, list):
                clean_hints = tuple(str(hint) for hint in hints if str(hint).strip())
                if clean_hints:
                    parsed_objectives.append((objective, clean_hints))
        if parsed_objectives:
            _OBJECTIVE_HINTS = tuple(parsed_objectives)

    deictics = data.get("deictic_terms")
    if isinstance(deictics, list):
        clean_deictics = {str(item) for item in deictics if str(item).strip()}
        if clean_deictics:
            _DEICTIC_TERMS = clean_deictics

    self_terms = data.get("self_reference_terms")
    if isinstance(self_terms, list):
        clean_self_terms = {str(item) for item in self_terms if str(item).strip()}
        if clean_self_terms:
            _SELF_REFERENCE_TERMS = clean_self_terms

    _RULES_CONTRACT_VERSION = str(data.get("contract_version") or _RULES_CONTRACT_VERSION)
    _RULES_SOURCE = "file"
    _RULES_PATH = str(path)


def rules_contract_info() -> dict[str, Any]:
    return {
        "contract_version": _RULES_CONTRACT_VERSION,
        "source": _RULES_SOURCE,
        "path": _RULES_PATH,
        "objective_count": len(_OBJECTIVE_HINTS),
        "interrogative_marker_count": len(_INTERROGATIVE_MARKERS),
        "deictic_term_count": len(_DEICTIC_TERMS),
        "self_reference_term_count": len(_SELF_REFERENCE_TERMS),
        "validation": _RULES_VALIDATION,
    }


_load_rules_contract()

_PATH_RE = re.compile(r"(?:[A-Za-z]:\\[^\s]+|(?:\.{1,2}/)?[\w.-]+(?:/[\w.-]+)+)")
_QUOTED_RE = re.compile(r"['\"]([^'\"]{2,200})['\"]")
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_CONSTRAINT_RE = re.compile(
    r"\b(sin|solo|solamente|con|debe|deben|tiene que|tienen que|maximo|max|minimo|min|formato)\b"
    r"([^.;?]*)",
    flags=re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", (text or "").lower().strip())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^\w\s:/\\.-]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def _stable_question_id(text: str, context: ReflexiveQuestionContext) -> str:
    payload = "|".join(
        [
            text.strip(),
            context.domain,
            "\n".join(context.conversation_history[-3:]),
            "\n".join(context.constraints),
        ]
    )
    return "Q-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10].upper()


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    return phrase in normalized_text


def _extract_unknowns(text: str) -> tuple[dict[str, Any], ...]:
    norm = _normalize_text(text)
    found: list[dict[str, Any]] = []
    used: set[str] = set()
    for marker, kind, description in _INTERROGATIVE_MARKERS:
        if _contains_phrase(norm, marker) and marker not in used:
            used.add(marker)
            found.append(
                {
                    "name": f"X{len(found) + 1}",
                    "marker": marker,
                    "kind": kind,
                    "description": description,
                    "source": "question_marker",
                }
            )
    if not found and "?" in text:
        found.append(
            {
                "name": "X1",
                "marker": "?",
                "kind": "answer",
                "description": "respuesta esperada por la pregunta",
                "source": "question_mark",
            }
        )
    return tuple(found)


def _extract_data(text: str) -> tuple[dict[str, Any], ...]:
    items: list[dict[str, Any]] = [
        {"kind": "raw_question", "value": text.strip(), "source": "user_text"},
    ]
    for path in _PATH_RE.findall(text):
        items.append({"kind": "path", "value": path, "source": "regex_path"})
    for quoted in _QUOTED_RE.findall(text):
        items.append({"kind": "quoted_text", "value": quoted.strip(), "source": "regex_quote"})
    for number in _NUMBER_RE.findall(text):
        items.append({"kind": "number", "value": number, "source": "regex_number"})
    return tuple(items)


def _extract_restrictions(text: str, context: ReflexiveQuestionContext) -> tuple[dict[str, Any], ...]:
    restrictions: list[dict[str, Any]] = []
    for match in _CONSTRAINT_RE.finditer(text):
        marker = match.group(1).strip()
        tail = match.group(2).strip(" ,:-")
        restrictions.append(
            {
                "kind": "text_constraint",
                "marker": marker,
                "value": tail or marker,
                "source": "user_text",
            }
        )
    for item in context.constraints:
        restrictions.append({"kind": "context_constraint", "value": item, "source": "context"})
    return tuple(restrictions)


def _context_factors(context: ReflexiveQuestionContext) -> tuple[dict[str, Any], ...]:
    factors: list[dict[str, Any]] = []
    if context.domain:
        factors.append({"kind": "domain", "value": context.domain})
    if context.conversation_history:
        factors.append(
            {
                "kind": "recent_history",
                "value": context.conversation_history[-1],
                "items": len(context.conversation_history),
            }
        )
    if context.user_profile:
        factors.append({"kind": "user_profile", "keys": sorted(context.user_profile)})
    if context.metadata:
        factors.append({"kind": "metadata", "keys": sorted(context.metadata)})
    return tuple(factors)


def _infer_objective(text: str) -> tuple[str, tuple[str, ...]]:
    norm = _normalize_text(text)
    matches: list[str] = []
    for objective, hints in _OBJECTIVE_HINTS:
        if any(hint in norm for hint in hints):
            matches.append(objective)
    if not matches and "?" in text:
        matches.append("responder")
    if not matches:
        matches.append("interpretar")
    return matches[0], tuple(dict.fromkeys(matches))


def _operational_intent(text: str) -> str:
    if classify_intent is None:
        return "work" if len(text.strip()) > 40 else "chat"
    try:
        return str(classify_intent(text))
    except Exception:
        return "work" if len(text.strip()) > 40 else "chat"


def _detect_ambiguity(
    text: str,
    context: ReflexiveQuestionContext,
    objectives: tuple[str, ...],
    unknowns: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    norm = _normalize_text(text)
    flags: list[dict[str, Any]] = []
    deictics = sorted(term for term in _DEICTIC_TERMS if term in norm)
    if deictics and not context.conversation_history:
        flags.append(
            {
                "kind": "missing_referent",
                "detail": "hay deicticos sin historial contextual suficiente",
                "markers": deictics,
            }
        )
    if len(objectives) > 1:
        flags.append(
            {
                "kind": "multiple_objectives",
                "detail": "la pregunta activa mas de un objetivo posible",
                "markers": list(objectives),
            }
        )
    if not unknowns and "?" not in text:
        flags.append(
            {
                "kind": "implicit_question",
                "detail": "no hay marcador interrogativo explicito",
                "markers": [],
            }
        )
    return tuple(flags)


def _build_alternatives(
    objective: str,
    ambiguity: tuple[dict[str, Any], ...],
    context: ReflexiveQuestionContext,
) -> tuple[dict[str, Any], ...]:
    alternatives: list[dict[str, Any]] = []
    for index, flag in enumerate(ambiguity, start=1):
        if flag["kind"] == "missing_referent":
            alternatives.append(
                {
                    "id": f"ALT-{index}",
                    "summary": "Resolver el referente desde el contexto conversacional",
                    "reason": "la pregunta usa deicticos y necesita el objeto exacto",
                    "score": 0.44 if not context.conversation_history else 0.72,
                    "status": "needs_context",
                }
            )
        elif flag["kind"] == "multiple_objectives":
            alternatives.append(
                {
                    "id": f"ALT-{index}",
                    "summary": "Tratar la pregunta como una tarea multiobjetivo",
                    "reason": "aparecen objetivos semanticos simultaneos",
                    "score": 0.58,
                    "status": "candidate",
                }
            )
        elif flag["kind"] == "implicit_question":
            alternatives.append(
                {
                    "id": f"ALT-{index}",
                    "summary": "Interpretar el texto como orden y no como pregunta",
                    "reason": "falta interrogacion explicita",
                    "score": 0.51,
                    "status": "candidate",
                }
            )
    if not alternatives:
        alternatives.append(
            {
                "id": "ALT-0",
                "summary": f"Interpretacion principal orientada a {objective}",
                "reason": "no se detecto ambiguedad estructural relevante",
                "score": 0.82,
                "status": "selected_baseline",
            }
        )
    return tuple(alternatives)


def _self_reference(text: str) -> dict[str, Any]:
    norm = _normalize_text(text)
    markers = sorted(term for term in _SELF_REFERENCE_TERMS if term in norm)
    detected = bool(markers)
    mirror_markers = ("esta pregunta", "lo que te estoy preguntando", "proceso de interpretar")
    depth = 2 if any(marker in norm for marker in mirror_markers) else (1 if detected else 0)
    return {
        "detected": detected,
        "depth": depth,
        "markers": markers,
        "stop_reason": "criterio_de_suficiencia: profundidad limitada a 2" if detected else "no_aplica",
    }


def _confidence(
    ambiguity: tuple[dict[str, Any], ...],
    context: ReflexiveQuestionContext,
    unknowns: tuple[dict[str, Any], ...],
    self_reference: dict[str, Any],
) -> float:
    score = 0.78
    if unknowns:
        score += 0.06
    if context.domain or context.conversation_history or context.constraints:
        score += 0.06
    score -= min(0.30, len(ambiguity) * 0.10)
    if self_reference.get("detected"):
        score -= 0.04
    return round(max(0.0, min(1.0, score)), 2)


def _build_formalization(
    text: str,
    objective: str,
    data: tuple[dict[str, Any], ...],
    unknowns: tuple[dict[str, Any], ...],
    context_factors: tuple[dict[str, Any], ...],
    restrictions: tuple[dict[str, Any], ...],
    self_reference: dict[str, Any],
) -> dict[str, Any]:
    variables = [
        {"name": "P", "meaning": "pregunta original", "value": text.strip()},
        {"name": "D", "meaning": "datos explicitos", "count": len(data)},
        {"name": "X", "meaning": "incognitas", "count": len(unknowns)},
        {"name": "C", "meaning": "contexto activo", "count": len(context_factors)},
        {"name": "R", "meaning": "restricciones", "count": len(restrictions)},
        {"name": "O", "meaning": "objetivo", "value": objective},
    ]
    relations = [
        "Q = (D, X, C, R, O)",
        "I = f(P, C, O)",
        "R* = argmax fidelity(representation, I) - ambiguity - contradiction",
    ]
    if self_reference.get("detected"):
        relations.append("F(R*) ~= R*")
    return {
        "type": "hybrid",
        "schema": "Q = D + X + C + R + O",
        "variables": variables,
        "relations": relations,
        "constraints": list(restrictions),
        "objective": objective,
        "trace": [
            {"target": "D", "source": "data"},
            {"target": "X", "source": "unknowns"},
            {"target": "C", "source": "context_factors"},
            {"target": "R", "source": "restrictions"},
            {"target": "O", "source": "intent"},
        ],
    }


def _evidence(
    text: str,
    objective: str,
    ambiguity: tuple[dict[str, Any], ...],
    self_reference: dict[str, Any],
    context: ReflexiveQuestionContext,
) -> tuple[dict[str, Any], ...]:
    items = [
        {
            "id": "E1",
            "type": "observation",
            "source": "user_text",
            "claim": "texto de entrada recibido",
            "value": text.strip(),
        },
        {
            "id": "E2",
            "type": "inference",
            "source": "heuristics",
            "claim": f"objetivo inferido: {objective}",
            "value": objective,
        },
        {
            "id": "E3",
            "type": "inference",
            "source": "ambiguity_engine",
            "claim": "ambiguedad estructural detectada",
            "value": [item["kind"] for item in ambiguity],
        },
        {
            "id": "E4",
            "type": "inference",
            "source": "self_reference_detector",
            "claim": "autorreferencia evaluada",
            "value": self_reference,
        },
    ]
    if context.domain or context.conversation_history or context.constraints:
        items.append(
            {
                "id": "E5",
                "type": "observation",
                "source": "context",
                "claim": "contexto opcional recibido",
                "value": {
                    "domain": context.domain,
                    "history_items": len(context.conversation_history),
                    "constraints": list(context.constraints),
                },
            }
        )
    return tuple(items)


def _audit_trail(
    question_id: str,
    objective: str,
    ambiguity: tuple[dict[str, Any], ...],
    confidence: float,
) -> tuple[dict[str, Any], ...]:
    return (
        {"step": "parse", "status": "ok", "evidence": ["E1"], "detail": question_id},
        {"step": "infer_intent", "status": "ok", "evidence": ["E2"], "detail": objective},
        {
            "step": "detect_ambiguity",
            "status": "ok",
            "evidence": ["E3"],
            "detail": [item["kind"] for item in ambiguity],
        },
        {"step": "formalize", "status": "ok", "evidence": ["E1", "E2"], "detail": "Q=(D,X,C,R,O)"},
        {"step": "calibrate_confidence", "status": "ok", "evidence": ["E1", "E2", "E3"], "detail": confidence},
    )


def _fixed_point(objective: str, self_reference: dict[str, Any], confidence: float) -> dict[str, Any]:
    stable = confidence >= 0.65
    return {
        "representation": "R* = argmax fidelity(R, I) subject to ambiguity->0 and contradiction->0",
        "condition": "F(R*) ~= R*",
        "applies": bool(self_reference.get("detected")) or objective == "formalizar",
        "stable": stable,
        "reason": (
            "la reinterpretacion conserva objetivo y estructura"
            if stable
            else "la reinterpretacion depende de contexto adicional"
        ),
    }


def _metrics(
    *,
    confidence: float,
    ambiguity: tuple[dict[str, Any], ...],
    evidence: tuple[dict[str, Any], ...],
    formalization: dict[str, Any],
    self_reference: dict[str, Any],
) -> dict[str, float]:
    ambiguity_penalty = min(0.35, len(ambiguity) * 0.12)
    evidence_count = len(evidence)
    trace_count = len(formalization.get("trace") or [])
    return {
        "fidelity": round(max(0.0, min(1.0, confidence + 0.05 - ambiguity_penalty)), 2),
        "coherence": round(0.92 if not ambiguity else max(0.55, 0.88 - ambiguity_penalty), 2),
        "traceability": round(min(1.0, 0.45 + evidence_count * 0.08 + trace_count * 0.04), 2),
        "ambiguity": round(min(1.0, len(ambiguity) * 0.25), 2),
        "self_reference_depth": float(self_reference.get("depth", 0) or 0),
        "invention_risk": round(max(0.05, 0.30 - evidence_count * 0.04 + ambiguity_penalty), 2),
    }


def _limits(
    ambiguity: tuple[dict[str, Any], ...],
    context: ReflexiveQuestionContext,
    self_reference: dict[str, Any],
) -> tuple[str, ...]:
    limits: list[str] = []
    if ambiguity:
        limits.append("hay ambiguedad o informacion contextual pendiente")
    if not context.conversation_history:
        limits.append("no se uso historial conversacional salvo el texto actual")
    if self_reference.get("detected"):
        limits.append("la autorreferencia se corta por criterio de suficiencia")
    if not limits:
        limits.append("analisis determinista; no sustituye validacion externa")
    return tuple(limits)


def analyze_question(
    text: str,
    context: Mapping[str, Any] | ReflexiveQuestionContext | None = None,
    *,
    question_id: str | None = None,
) -> ReflexiveInterpretationResult:
    """Analyze a natural-language question into the Reflexive Interpreter contract."""
    clean_text = (text or "").strip()
    ctx = ReflexiveQuestionContext.from_any(context)
    qid = question_id or _stable_question_id(clean_text, ctx)
    data = _extract_data(clean_text)
    unknowns = _extract_unknowns(clean_text)
    context_items = _context_factors(ctx)
    restrictions = _extract_restrictions(clean_text, ctx)
    objective, objectives = _infer_objective(clean_text)
    operational = _operational_intent(clean_text)
    ambiguity = _detect_ambiguity(clean_text, ctx, objectives, unknowns)
    alternatives = _build_alternatives(objective, ambiguity, ctx)
    self_ref = _self_reference(clean_text)
    confidence = _confidence(ambiguity, ctx, unknowns, self_ref)
    selected = {
        "summary": f"El usuario busca {objective} la pregunta o tarea planteada.",
        "reason": "maximiza fidelidad con el texto y requiere menos supuestos que las alternativas",
        "confidence": confidence,
        "evidence": ["E1", "E2", "E3"],
    }
    formalization = _build_formalization(
        clean_text,
        objective,
        data,
        unknowns,
        context_items,
        restrictions,
        self_ref,
    )
    evidence = _evidence(clean_text, objective, ambiguity, self_ref, ctx)
    audit = _audit_trail(qid, objective, ambiguity, confidence)
    fixed = _fixed_point(objective, self_ref, confidence)
    metrics = _metrics(
        confidence=confidence,
        ambiguity=ambiguity,
        evidence=evidence,
        formalization=formalization,
        self_reference=self_ref,
    )
    limits = _limits(ambiguity, ctx, self_ref)
    final_answer = (
        f"Se interpreta como objetivo '{objective}'. "
        "La forma operable es Q=(D,X,C,R,O): datos, incognitas, contexto, "
        "restricciones y objetivo. "
        f"Confianza {confidence:.2f}."
    )
    return ReflexiveInterpretationResult(
        question_id=qid,
        literal_reading=clean_text,
        intent=objective,
        operational_intent=operational,
        data=data,
        unknowns=unknowns,
        context_factors=context_items,
        restrictions=restrictions,
        assumptions=(
            {
                "id": "A1",
                "description": "la pregunta debe conservar intencion, no solo palabras",
                "risk": "bajo",
            },
        ),
        alternatives=alternatives,
        selected_interpretation=selected,
        formalization=formalization,
        evidence=evidence,
        audit_trail=audit,
        self_reference=self_ref,
        fixed_point=fixed,
        metrics=metrics,
        rules=rules_contract_info(),
        final_answer=final_answer,
        limits=limits,
        confidence=confidence,
    )


def format_reflexive_report(result: ReflexiveInterpretationResult | Mapping[str, Any]) -> str:
    """Render a compact terminal report for /interpret."""
    data = result.to_dict() if isinstance(result, ReflexiveInterpretationResult) else dict(result)
    formal = data.get("formalization") or {}
    selected = data.get("selected_interpretation") or {}
    self_ref = data.get("self_reference") or {}
    fixed = data.get("fixed_point") or {}

    def _values(items: Any, key: str = "value") -> str:
        if not items:
            return "-"
        values: list[str] = []
        for item in list(items)[:4]:
            if isinstance(item, Mapping):
                values.append(str(item.get(key) or item.get("description") or item.get("kind") or item))
            else:
                values.append(str(item))
        return "; ".join(values) if values else "-"

    lines = [
        "INTERPRETE REFLEXIVO",
        f"ID: {data.get('question_id', '-')}",
        f"Lectura literal: {data.get('literal_reading', '-')}",
        f"Intencion: {data.get('intent', '-')}  | operativa: {data.get('operational_intent', '-')}",
        "",
        "Estructura Q=(D,X,C,R,O)",
        f"  D datos: {_values(data.get('data'))}",
        f"  X incognitas: {_values(data.get('unknowns'), 'description')}",
        f"  C contexto: {_values(data.get('context_factors'), 'kind')}",
        f"  R restricciones: {_values(data.get('restrictions'))}",
        f"  O objetivo: {formal.get('objective', data.get('intent', '-'))}",
        "",
        f"Seleccion: {selected.get('summary', '-')}",
        f"Razon: {selected.get('reason', '-')}",
        f"Formalizacion: {formal.get('schema', '-')}",
        f"Autorreferencia: {self_ref.get('detected', False)} depth={self_ref.get('depth', 0)}",
        f"Punto fijo: {fixed.get('condition', '-')} stable={fixed.get('stable', False)}",
        f"Reglas: {data.get('rules', {}).get('contract_version', '-')} source={data.get('rules', {}).get('source', '-')}",
        "Metricas: "
        f"fidelidad={data.get('metrics', {}).get('fidelity', 0):.2f} "
        f"trazabilidad={data.get('metrics', {}).get('traceability', 0):.2f} "
        f"ambiguedad={data.get('metrics', {}).get('ambiguity', 0):.2f}",
        f"Confianza: {data.get('confidence', 0):.2f}",
    ]
    limits = data.get("limits") or []
    if limits:
        lines.append("Limites: " + "; ".join(str(item) for item in limits))
    return "\n".join(lines)
