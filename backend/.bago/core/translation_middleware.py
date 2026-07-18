"""translation_middleware.py — Wrap de un provider adapter que traduce
ES↔EN automáticamente para modelos que solo trabajan bien en inglés.

Caso de uso: granite3.2:8b responde bien en inglés pero degrada en español
(timeout 180s con prompts largos en ES). Este middleware hace:
  1. Si el usuario habla en español → traduce el último mensaje user a inglés
     con un modelo traductor (default: llama3.2:3b).
  2. Tras recibir la respuesta del modelo objetivo → la traduce de inglés
     a español con el mismo modelo traductor.
  3. El usuario no nota nada: ve su chat en español, el modelo recibe EN.

Config en .bago/config.json (sección "translation_middleware"):
    {
      "enabled": true,
      "translator_model": "llama3.2:3b",
      "translator_provider": "ollama-local",
      "target_models": ["granite3.2:8b", "granite3.2:*"],
      "skip_if_same_language": true,
      "max_input_chars": 4000
    }

Si no hay sección, se aplican defaults sensatos.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Iterator


# ─── Detección de idioma (heurística barata) ────────────────────────────

_ES_CHARS = set("áéíóúüñ¿¡")
_ES_COMMON = {
    "el", "la", "los", "las", "de", "del", "que", "en", "un", "una",
    "es", "está", "están", "por", "para", "con", "sin", "como",
    "pero", "porque", "si", "no", "sí", "yo", "tú", "él", "ella",
    "nosotros", "vosotros", "ellos", "esto", "esa", "este", "ese",
    "hola", "gracias", "por favor", "bueno", "buenos", "buenas",
    "qué", "cómo", "cuándo", "dónde", "cuál", "cuáles", "quién",
    "muy", "más", "menos", "también", "tambien", "ahora", "aquí",
    "allí", "hay", "ser", "estar", "tener", "hacer", "ir", "poder",
    "sobre", "hasta", "desde", "entre", "cuando", "donde",
}
_EN_COMMON = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "should", "could", "may", "might", "can", "of", "in", "on",
    "at", "to", "for", "with", "by", "from", "as", "and", "or",
    "but", "if", "this", "that", "these", "those", "i", "you",
    "he", "she", "it", "we", "they", "hello", "thanks", "please",
    "what", "when", "where", "which", "who", "how", "my", "your",
    "his", "her", "its", "our", "their",
}


def detect_language(text: str) -> str:
    """Devuelve 'es' | 'en' | 'unknown'. Heurística rápida, sin libs."""
    if not text or not text.strip():
        return "unknown"
    sample = text[:4000]
    lowered = sample.lower()
    words = re.findall(r"[a-záéíóúüñ]+", lowered)
    if not words:
        return "unknown"
    es_hits = sum(1 for w in words if w in _ES_COMMON)
    en_hits = sum(1 for w in words if w in _EN_COMMON)
    # Bonus por caracteres diagnósticos
    es_bonus = sum(2 for c in sample if c in _ES_CHARS)
    en_bonus = 0
    es_score = es_hits * 1.0 + es_bonus
    en_score = en_hits * 1.0 + en_bonus
    if es_score == 0 and en_score == 0:
        return "unknown"
    if es_score > en_score * 1.2:
        return "es"
    if en_score > es_score * 1.2:
        return "en"
    return "unknown"


# ─── Llamada directa a Ollama para el traductor ─────────────────────────

_DEFAULT_TIMEOUT = 60


def _ollama_generate(
    model: str,
    prompt: str,
    base_url: str = "http://127.0.0.1:11434",
    timeout_s: float = _DEFAULT_TIMEOUT,
    temperature: float = 0.1,
) -> tuple[str, float, str | None]:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max(64, min(len(prompt) * 2, 1024)),
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            return (d.get("response") or "").strip(), time.time() - t0, None
    except urllib.error.URLError as exc:
        return "", time.time() - t0, f"URLError: {exc.reason}"
    except Exception as exc:
        return "", time.time() - t0, f"{type(exc).__name__}: {exc}"


# ─── Prompts de traducción ──────────────────────────────────────────────

_PROMPT_ES_TO_EN = (
    "You are a professional EN→ES translator. Translate the following text "
    "from Spanish to English. Preserve technical terms, code blocks, URLs, "
    "and proper nouns. Output ONLY the translation, no preamble, no quotes, "
    "no explanations.\n\n"
    "TEXT:\n{text}\n\n"
    "ENGLISH TRANSLATION:"
)

_PROMPT_EN_TO_ES = (
    "Eres un traductor profesional EN→ES. Traduce el siguiente texto del "
    "inglés al español. Conserva términos técnicos, bloques de código, URLs "
    "y nombres propios. Responde SOLO con la traducción, sin preámbulo, "
    "sin comillas, sin explicaciones.\n\n"
    "TEXTO:\n{text}\n\n"
    "TRADUCCIÓN AL ESPAÑOL:"
)

# Patrones que NO deben traducirse
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`]+`")
_URL = re.compile(r"https?://\S+")
_PATH = re.compile(r"(?:[A-Za-z]:)?[/\\][\w./\\-]+")


def _looks_like_code_or_paths(text: str) -> bool:
    """Si el texto es predominantemente código, no traducimos nada."""
    if _CODE_FENCE.search(text):
        return True
    if _PATH.search(text) and len(text) < 200:
        return True
    return False


def _strip_translation_chatter(text: str) -> str:
    """Quita prefijos típicos que los modelos añaden aunque se lo pidas."""
    t = text.strip()
    # Quitar prefijos tipo "Here is the translation:", "La traducción es:",
    # bloques de markdown ``` que envuelvan la respuesta entera.
    prefixes = [
        r"^(here\s+is\s+the\s+translation\s*:?\s*)",
        r"^(this\s+is\s+the\s+translation\s*:?\s*)",
        r"^(la\s+traducci[oó]n\s+es\s*:?\s*)",
        r"^(traducci[oó]n\s*:?\s*)",
        r"^(english\s+translation\s*:?\s*)",
        r"^(spanish\s+translation\s*:?\s*)",
        r"^(output\s*:?\s*)",
        r"^(respuesta\s*:?\s*)",
    ]
    for p in prefixes:
        t = re.sub(p, "", t, flags=re.IGNORECASE | re.DOTALL)
    # Quitar comillas externas si las pone
    if (t.startswith('"') and t.endswith('"')) or \
       (t.startswith("'") and t.endswith("'")) or \
       (t.startswith("“") and t.endswith("”")):
        t = t[1:-1].strip()
    return t


# ─── Config ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "translator_model": "llama3.2:3b",
    "translator_provider": "ollama-local",
    # Lista de modelos (soporta wildcards con *) cuyo input/salida debe
    # pasar por traducción. Por defecto solo granite3.2:*, pero se puede
    # extender.
    "target_models": ["granite3.2:*"],
    "skip_if_same_language": True,
    "max_input_chars": 4000,
    "timeout_s": 60.0,
    "translator_base_url": "http://127.0.0.1:11434",
    # Liberar RAM tras usar el modelo objetivo (e.g. granite3.2 ~5GB).
    # Por defecto DESACTIVADO: modelos lentos de cargar (granite3.2:8b
    # tarda 3-5min en arrancar desde cero) hacen que unload_after_use sea
    # contraproducente. Ollama gestiona su propio keep_alive (5min por
    # defecto). Actívalo solo si tienes mucha presión de RAM.
    "unload_target_after_use": False,
    "target_keep_alive_minutes": 30,
    # Timeout del adapter subyacente cuando se activa el middleware.
    # Modelos como granite3.2:8b tardan ~90s por respuesta; subimos a 180s.
    "adapter_timeout_s": 180.0,
}


def load_config(user_config: dict | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(user_config, dict):
        # Translation middleware puede vivir en .bago/config.json bajo
        # clave "translation_middleware" o pasarse ya extraído.
        inner = user_config.get("translation_middleware", user_config)
        if isinstance(inner, dict):
            cfg.update(inner)
    return cfg


def should_translate_for(model: str, target_patterns: list[str]) -> bool:
    """True si el modelo activo está en la lista de modelos a traducir."""
    if not model or not target_patterns:
        return False
    for pat in target_patterns:
        if pat == model:
            return True
        if "*" in pat:
            # Convertir wildcard a regex sencilla
            regex = "^" + re.escape(pat).replace(r"\*", ".*") + "$"
            if re.match(regex, model):
                return True
    return False


# ─── Función de traducción de alto nivel ────────────────────────────────

def translate(
    text: str,
    target_lang: str,
    cfg: dict,
) -> tuple[str, dict]:
    """Traduce `text` al idioma destino usando el modelo traductor.

    Devuelve (translated_text, info) donde info es dict con:
        - translated: bool
        - skipped: bool (True si no hizo falta)
        - reason: str
        - elapsed_s: float
        - error: str | None
    """
    info = {
        "translated": False,
        "skipped": False,
        "reason": "",
        "elapsed_s": 0.0,
        "error": None,
        "src_lang": None,
        "dst_lang": target_lang,
    }
    if not text or not text.strip():
        info["skipped"] = True
        info["reason"] = "empty"
        return text, info

    if not cfg.get("enabled", True):
        info["skipped"] = True
        info["reason"] = "disabled"
        return text, info

    if _looks_like_code_or_paths(text):
        info["skipped"] = True
        info["reason"] = "looks_like_code"
        return text, info

    src = detect_language(text)
    info["src_lang"] = src
    if src == "unknown":
        info["skipped"] = True
        info["reason"] = "unknown_language"
        return text, info
    if src == target_lang and cfg.get("skip_if_same_language", True):
        info["skipped"] = True
        info["reason"] = f"already_{target_lang}"
        return text, info

    max_chars = int(cfg.get("max_input_chars", 4000))
    if len(text) > max_chars:
        info["skipped"] = True
        info["reason"] = f"too_long ({len(text)}>{max_chars})"
        return text, info

    if target_lang == "en":
        prompt = _PROMPT_ES_TO_EN.format(text=text)
    elif target_lang == "es":
        prompt = _PROMPT_EN_TO_ES.format(text=text)
    else:
        info["error"] = f"target_lang no soportado: {target_lang}"
        return text, info

    model = str(cfg.get("translator_model", "llama3.2:3b"))
    base = str(cfg.get("translator_base_url", "http://127.0.0.1:11434"))
    timeout = float(cfg.get("timeout_s", 60.0))

    raw, dt, err = _ollama_generate(model, prompt, base_url=base, timeout_s=timeout)
    info["elapsed_s"] = dt
    if err:
        info["error"] = err
        return text, info
    if not raw:
        info["error"] = "translator devolvió vacío"
        return text, info

    cleaned = _strip_translation_chatter(raw)
    info["translated"] = True
    info["reason"] = f"{src}->{target_lang} via {model}"
    return cleaned, info


def translate_messages_input(
    messages: list[dict],
    cfg: dict,
) -> tuple[list[dict], list[dict]]:
    """Traduce los mensajes user al inglés (si están en español).

    Devuelve (messages_new, infos) donde infos es la lista de info[] de
    cada traducción aplicada (útil para diagnóstico).
    """
    infos: list[dict] = []
    new_messages: list[dict] = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role in ("user",) and isinstance(content, str) and content.strip():
            translated, info = translate(content, target_lang="en", cfg=cfg)
            infos.append(info)
            if info.get("translated"):
                new_m = dict(m)
                new_m["content"] = translated
                new_messages.append(new_m)
            else:
                new_messages.append(m)
        else:
            new_messages.append(m)
    return new_messages, infos


def translate_output(text: str, cfg: dict) -> tuple[str, dict]:
    """Traduce la salida del modelo objetivo del inglés al español."""
    return translate(text, target_lang="es", cfg=cfg)
