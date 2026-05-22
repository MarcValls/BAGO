"""bago.llm.quality — Calidad de respuesta: anti-repetición, detección de basura,
escalado preventivo por URL o incapacidad de modelo."""

import re

# ── Anti-repetición interna ────────────────────────────────────────────────────

_REPEAT_THRESHOLD = 0.72   # Jaccard entre respuestas sucesivas


def _jaccard(a: str, b: str) -> float:
    """Similitud Jaccard por palabras (0–1). Rápido, sin dependencias."""
    if not a or not b:
        return 0.0
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _dedup_paragraphs(text: str) -> str:
    """Elimina párrafos/bloques duplicados dentro de una misma respuesta."""
    blocks = re.split(r'\n{2,}', text)
    seen, out = [], []
    for blk in blocks:
        key = blk.strip()
        if not key:
            continue
        if any(_jaccard(key, s) > 0.82 for s in seen[-8:]):
            continue
        seen.append(key)
        out.append(blk)
    return "\n\n".join(out)


def _last_assistant(history: list) -> str:
    """Último mensaje del asistente en el historial."""
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            return msg["content"]
    return ""


# ── Detección de respuesta incoherente / basura ───────────────────────────────

# Patrones que indican que el modelo redirigió en lugar de responder
_EVASION_PATTERNS = [
    r"(?i)(cómo|como) puedo ayudarte",
    r"(?i)no (necesito|necesitas) m[aá]s informaci[oó]n",
    r"(?i)¿(qué|que) deseas (saber|hacer|preguntar)",
    r"(?i)(¿hay|hay) algo m[aá]s (en que|que) pueda",
    r"(?i)how can i (help|assist) you( today)?",
    r"(?i)what would you like (me to|to) (do|know|help)",
    r"(?i)i('m|'d) (be )?happy to help",
    r"(?i)please (let me know|tell me) (what|how)",
    r"(?i)¿(en qué|en que) puedo ayudarte",
    r"(?i)¿(qué|que) (es lo que|necesitas|quieres)",
]

# Patrones que indican que el modelo admite no poder acceder a internet
_NO_INTERNET_SIGNALS = (
    "no puedo navegar",
    "no tengo acceso a internet",
    "no puedo acceder a",
    "no puedo abrir",
    "no puedo visitar",
    "can't browse",
    "cannot browse",
    "can't access the url",
    "cannot access the url",
    "i don't have internet",
    "sin acceso a internet",
    "no tengo capacidad para navegar",
    "no tengo herramientas de búsqueda",
    "as an ai i don't have access",
    "no puedo abrir enlaces",
)

# Saludos simples — no se penalizan con calidad
_SIMPLE_GREETING = re.compile(
    r"(?i)^(hola|hi|hello|hey|buenas|saludos|good\s+\w+)[.!?]?\s*$"
)

# Detectar URLs en el mensaje del usuario
_URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
_WEB_INTENT_PATTERN = re.compile(
    r"(?i)\b("
    r"abre|abrir|visita|visitar|consulta|consultar|navega|navegar|busca|buscar|"
    r"lee|leer|descarga|descargar|fetch|open|visit|browse|search|read|download"
    r")\b"
)
_PASTED_STATUS_PATTERN = re.compile(
    r"(?i)("
    r"ratelimiterror|quota|billing|/status|context window|weekly limit|5h limit|"
    r"visit https://chatgpt\.com|docs/guides/error-codes|openai codex|"
    r"directory:|permissions:|session:"
    r")"
)


def _contains_url(text: str) -> bool:
    return bool(_URL_PATTERN.search(text))


def _response_is_garbage(user_input: str, response: str) -> "tuple[bool, str]":
    """Detecta si la respuesta es incoherente/basura respecto a la pregunta.

    Retorna (True, reason) si es basura, (False, '') si es aceptable.
    Nunca penaliza respuestas a saludos simples.
    """
    is_simple_greeting = bool(_SIMPLE_GREETING.match(user_input.strip()))
    resp_words  = len(response.split())
    q_words     = len(user_input.split())
    resp_low    = response.lower()

    # 1. Respuesta vacía o extremadamente corta para pregunta sustantiva
    if resp_words < 8 and q_words > 6 and not is_simple_greeting:
        return True, f"respuesta demasiado corta ({resp_words} palabras)"

    # 2. El modelo admite no poder acceder a internet — solo relevante si el
    #    usuario mencionó una URL; evita falsos positivos en respuestas de POO, etc.
    if _contains_url(user_input):
        for sig in _NO_INTERNET_SIGNALS:
            if sig in resp_low:
                return True, "modelo admite no poder acceder a internet/URL"

    # 3. Patrones de evasión / redirección cuando la pregunta es sustantiva
    if not is_simple_greeting and q_words > 4:
        for pat in _EVASION_PATTERNS:
            if re.search(pat, response):
                return True, "respuesta evasiva — modelo redirigió sin responder"

    # 4. Overlap de palabras clave muy bajo cuando la pregunta es larga
    if q_words >= 8 and not is_simple_greeting:
        q_sig = {
            w.lower()
            for w in re.findall(r'\b[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{4,}\b', user_input)
        }
        if q_sig:
            overlap = sum(1 for w in q_sig if w in resp_low)
            ratio = overlap / len(q_sig)
            if ratio < 0.07:
                return True, (
                    f"sin relación con la pregunta "
                    f"({overlap}/{len(q_sig)} palabras clave coinciden)"
                )

    return False, ""


def _needs_cloud_for_url(user_input: str, session) -> bool:
    """True si hay URL + intención real de navegación y el modelo actual es local."""
    if not _contains_url(user_input):
        return False
    if session.provider not in ("ollama-local", "ollama-cloud"):
        return False
    # Texto pegado de status/error: la URL es evidencia, no una petición web.
    if _PASTED_STATUS_PATTERN.search(user_input):
        return False
    return bool(_WEB_INTENT_PATTERN.search(user_input))
