#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
intent_engine.py — Auto-training intent classification for BAGO local.

Learns from the user's own conversation history (intent_examples.json)
and classifies incoming messages into intents:
  chat      → casual conversation, do NOT use tools
  review    → examine/read/list files or directories
  execute   → run a command or script immediately
  work      → create, modify, refactor code or content
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Load few-shot dataset (auto-generated from session_store)
# ---------------------------------------------------------------------------

_DEFAULT_EXAMPLES: Dict[str, List[Dict[str, str]]] = {}
_BUNDLED_DATA_PATH = Path(__file__).with_name("intent_examples.json")


def _user_data_path() -> Path:
    override = os.environ.get("BAGO_INTENT_EXAMPLES_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".bago" / "state" / "intent_examples.json"


def _load_examples() -> Dict[str, List[Dict[str, str]]]:
    def _merge(dst: Dict[str, List[Dict[str, str]]], src: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
        for intent, rows in src.items():
            dst.setdefault(intent, [])
            seen = {item.get("user", "") for item in dst[intent] if item.get("user")}
            for row in rows:
                user = row.get("user", "")
                if not user or user in seen:
                    continue
                seen.add(user)
                dst[intent].append(row)
        return dst

    merged: Dict[str, List[Dict[str, str]]] = {}
    for path in (_BUNDLED_DATA_PATH, _user_data_path()):
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        merged = _merge(merged, data)
    return merged


_DEFAULT_EXAMPLES = _load_examples()


def reload_examples() -> Dict[str, int]:
    """Recarga el dataset few-shot desde disco (tras una autoevolución/retrain).
    Necesario porque el dataset se carga una sola vez al importar el módulo.
    Devuelve el conteo de ejemplos por intención."""
    global _DEFAULT_EXAMPLES
    _DEFAULT_EXAMPLES = _load_examples()
    return {k: len(v) for k, v in _DEFAULT_EXAMPLES.items()}


def example_counts() -> Dict[str, int]:
    """Conteo actual de ejemplos few-shot por intención."""
    return {k: len(v) for k, v in _DEFAULT_EXAMPLES.items()}


# Keyword heuristics for fast classification (mirrors the generation logic)
_KEYWORDS: Dict[str, List[str]] = {
    "chat": [
        "hola", "hey", "saludos", "continua", "gracias", "adios",
        "español", "hello", "hi",
    ],
    "review": [
        "revisa", "mira", "reune", "busca", "chequea", "examina",
        "verifica", "audita", "evalua", "evalúa", "diagnostica", "inspecciona",
        "analiza esto", "mira esto", "mira ahora",
        "list_directory", "read_file", "dame el contenido",
        "echa un vistazo", "ojea", "inspecciona", "comprueba",
        "lee", "leer", "abre el archivo", "abre el log", "abre la carpeta",
        "abre el directorio", "abre la ruta", "abre el contenido",
    ],
    "execute": [
        "ejecuta", "corre", "lanza", "dispara", "run", "execute",
        "corre el comando", "ejecuta el script", "corre el script",
        "instala", "arranca", "levanta", "inicia",
        "abre la app", "abre electron", "arranca electron", "levanta electron",
        "inicia electron", "abre el servidor", "levanta el servidor",
    ],
    "work": [
        "trabaja", "modulariza", "adapta", "crea", "modifica",
        "refactoriza", "estructurala", "ordena", "desarrolla",
        "implementa", "construye", "genera", "haz que", "hazme",
        "adaptalo", "modularizala", "estructuralo", "organiza",
        "escribe", "redacta", "construyeme", "constrúyeme",
    ],
}


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower().strip())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9+/.\s_-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _tokenize(text: str) -> list[str]:
    return [token for token in _normalize_text(text).split() if token]


def _has_root(tokens: list[str], root: str) -> bool:
    root = _normalize_text(root)
    return any(token.startswith(root) for token in tokens)


_COMMAND_HINTS: Dict[str, list[str]] = {
    "/save": [
        "guardar", "guard", "grabar", "graba", "snapshot", "checkpoint", "preserva",
        "preserva la sesion", "preserva la sesión", "copia", "backup", "salva", "freeze", "no pierdas",
    ],
    "/switch": [
        "cambiar", "cambia", "switch", "modelo", "provider", "llm", "ia",
        "inteligencia artificial", "otro modelo", "otro provider", "probar otro",
        "ponme otro", "usa otro", "mas potente", "mas fuerte",
    ],
    "/status": [
        "estado", "resumen", "sesion", "tokens", "donde estamos", "en que estamos",
        "como estamos", "como va todo", "que tal va", "dime en que punto", "punto exacto",
    ],
    "/quit": [
        "salir", "cierra", "cerrar", "termina", "terminar", "adios", "bye",
        "cierres", "termines", "me voy", "hasta luego", "apaga bago", "para bago", "cierra todo", "vete cerrando",
    ],
    "/help": [
        "ayuda", "help", "manual", "guia", "explicame", "como funciona",
        "que puedes hacer", "instrucciones",
    ],
    "/plan": [
        "plan", "estrategia", "pasos", "hoja de ruta", "roadmap", "arrancamos",
        "empezamos", "como lo hacemos", "por donde empezamos",
    ],
    "/autopilot": [
        "autopilot", "autopiloto", "autonom", "sin seguir preguntando",
        "toma el control", "toma las riendas", "desatate", "hazlo tu solo",
        "hazlo todo tu", "hazlo todo tú", "no supervises", "resuelvelo tu",
    ],
    "/evolve": [
        "evolve", "evolucion", "aprende", "reentrena", "actualiza tus intenciones",
        "actualiza", "mejora", "ajustate", "historial",
    ],
    "/memory": [
        "memoria", "memory", "recuerd", "recuerda", "base de conocimiento",
        "knowledge base", "almacenad", "guardado", "que queda almacenado",
    ],
    "/credentials set": [
        "api key", "apikey", "token", "clave", "credencial", "credenciales",
        "login", "autentic", "meter el token", "poner el token", "dame acceso",
    ],
    "/good": [
        "me gusto", "me gustó", "guarda esa respuesta", "marca como importante",
        "marcar como bueno", "excelente respuesta", "eso fue correcto", "thumbs up",
    ],
}

_COMMAND_THRESHOLDS: Dict[str, float] = {
    "/save": 4.6,
    "/switch": 5.5,
    "/status": 4.8,
    "/quit": 5.0,
    "/help": 4.0,
    "/plan": 4.0,
    "/autopilot": 4.4,
    "/evolve": 4.8,
    "/memory": 4.0,
    "/memory delete": 7.0,
    "/credentials set": 4.0,
    "/project": 8.5,
    "/good": 8.5,
}

_STOPWORDS = {
    "a", "al", "algo", "antes", "asi", "aun", "aunque", "bago", "como", "con",
    "contra", "de", "del", "desde", "donde", "e", "el", "ella", "ellas", "ellos",
    "en", "entre", "era", "eres", "es", "esa", "ese", "eso", "esta", "estamos",
    "estan", "estás", "este", "esto", "estos", "estas", "ha", "hay", "he", "la",
    "las", "le", "les", "lo", "los", "me", "mi", "mis", "muy", "nada", "ni", "no",
    "nos", "o", "otra", "otro", "para", "pero", "por", "que", "qué", "se", "si",
    "sí", "sin", "sobre", "su", "sus", "te", "tu", "tus", "un", "una", "uno",
    "unos", "unas", "ya", "yo",
    "bien", "va", "cosa",
}


def _stem_token(token: str) -> str:
    token = _normalize_text(token)
    if len(token) <= 3:
        return token
    suffixes = (
        "mente", "aciones", "acion", "iciones", "icion", "idades", "idad",
        "amiento", "imiento", "ando", "iendo", "ar", "er", "ir", "ado", "ada",
        "ados", "adas", "ido", "ida", "idos", "idas", "aba", "aban", "abas",
        "aran", "aron", "eran", "eran", "es", "s", "a", "e", "o", "os", "as",
        "en", "an", "is",
    )
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            token = token[: -len(suffix)]
            break
    return token


def _normalize_tokens(text: str) -> list[str]:
    return [token for token in _tokenize(text) if token and token not in _STOPWORDS]


def _root_match(token: str, candidate: str) -> bool:
    token = _normalize_text(token)
    candidate = _normalize_text(candidate)
    if token.startswith(candidate):
        return True
    if len(token) >= 5 and candidate.startswith(token):
        return True
    return _stem_token(token) == _stem_token(candidate)


_INTENT_HINTS: Dict[str, list[str]] = {
    "chat": [
        "hola", "hey", "saludos", "gracias", "adios", "hello", "hi",
        "que tal", "como estas", "como va", "vamos bien", "buen camino",
    ],
    "review": [
        "revisa", "mira", "busca", "chequea", "examina", "verifica", "analiza",
        "echa un vistazo", "ojea", "inspecciona", "comprueba", "contenido",
        "archivo", "directorio", "lista", "dame el contenido", "lee", "leer", "abre",
    ],
    "execute": [
        "ejecuta", "corre", "lanza", "dispara", "run", "execute", "instala",
        "arranca", "levanta", "inicia", "despliega", "abre el servidor",
    ],
    "work": [
        "trabaja", "modulariza", "adapta", "crea", "modifica", "refactoriza",
        "ordena", "desarrolla", "implementa", "construye", "genera", "haz que",
        "hazme", "escribe", "redacta", "crea una", "construyeme", "construyeme",
    ],
}

_INTENT_PROTOTYPES: Dict[str, frozenset[str]] = {
    "chat": frozenset({
        "hola", "hey", "saludo", "gracias", "adios", "tal", "como", "estas", "va", "bien",
    }),
    "review": frozenset({
        "revis", "audit", "analiz", "inspeccion", "verific", "comprueb", "examin", "le", "abr", "busc",
        "detect", "diagnostic", "valida", "riesg", "fall", "bug", "diff", "archivo", "ruta", "list",
    }),
    "execute": frozenset({
        "ejecut", "corre", "lanza", "dispar", "instal", "arranc", "levant", "inici", "aplic", "parche",
        "corrig", "arregl", "run", "command", "script", "shell", "comando",
    }),
    "work": frozenset({
        "trabaj", "cre", "modific", "refactor", "estructur", "orden", "desarroll", "implement",
        "constru", "gener", "escrib", "rediseñ", "migra", "adapta", "reorgan", "ajust", "parche",
    }),
}

_INTENT_MACRO_HINTS: Dict[str, list[str]] = {
    "chat": ["hola", "hey", "saludos", "gracias", "buenas", "que tal", "como estas", "como va"],
    "analysis": ["revisa", "revisa", "audita", "analiza", "inspecciona", "evalua", "diagnostica", "verifica"],
    "action": ["ejecuta", "corrige", "arregla", "implementa", "modifica", "refactoriza", "migra", "crea"],
}

_INTENT_ACTION_CUES: Dict[str, list[str]] = {
    "review": [
        "audita", "auditoria", "revisa", "revisar", "analiza", "analisis", "evalua", "evaluar",
        "inspecciona", "inspeccionar", "diagnostica", "diagnosticar", "verifica", "verificar",
        "comprueba", "comprueba", "detecta", "riesgo", "riesgos", "fallo", "fallos", "bug", "bugs",
    ],
    "execute": [
        "ejecuta", "ejecutar", "corre", "correr", "lanza", "lanzar", "levanta", "levantar",
        "inicia", "iniciar", "instala", "instalar", "aplica", "aplicar", "parchea", "parchear",
        "corrige", "corregir", "arregla", "arreglar", "run", "script", "comando", "terminal",
    ],
    "work": [
        "implementa", "implementar", "modifica", "modificar", "refactoriza", "refactorizar",
        "migra", "migrar", "crea", "crear", "genera", "generar", "construye", "construir",
        "rediseña", "redisenar", "ordena", "ordenar", "adapta", "adaptar", "reestructura", "reestructurar",
    ],
}

_REVIEW_OPEN_HINTS = [
    "abre el archivo", "abre el log", "abre la carpeta", "abre el directorio",
    "abre la ruta", "abre el contenido",
]

_EXECUTE_LAUNCH_HINTS = [
    "abre la app", "abre electron", "arranca electron", "levanta electron",
    "inicia electron", "abre el servidor", "levanta el servidor",
]


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(_normalize_text(phrase) in text for phrase in phrases)


def _prototype_score(stems: list[str], intent: str) -> float:
    prototype = _INTENT_PROTOTYPES.get(intent, frozenset())
    if not prototype or not stems:
        return 0.0
    stem_set = set(stems)
    overlap = len(stem_set.intersection(prototype))
    if not overlap:
        return 0.0
    return (overlap / max(len(prototype) ** 0.5, 1.0)) * 3.0


def _macro_intent_score(msg: str, tokens: list[str], intent: str) -> float:
    score = 0.0
    cues = _INTENT_MACRO_HINTS.get(intent, [])
    if cues and _contains_any(msg, cues):
        score += 3.5
    if intent != "chat" and _contains_any(msg, _INTENT_ACTION_CUES.get(intent, [])):
        score += 2.5
    if intent == "chat" and any(token in _STOPWORDS for token in tokens) and len(tokens) <= 3:
        score += 1.0
    return score

_COMMAND_PROFILES: dict[str, dict[str, object]] = {}


def _build_command_profiles() -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}
    if not _CMD_DATA_PATH.exists():
        return profiles
    try:
        data = json.loads(_CMD_DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return profiles

    raw: dict[str, dict[str, object]] = {}
    token_df: Counter[str] = Counter()
    stem_df: Counter[str] = Counter()
    for cmd, info in data.get("commands", {}).items():
        phrases = [_normalize_text(p) for p in info.get("phrases", []) if p]
        token_counter: Counter[str] = Counter()
        stem_counter: Counter[str] = Counter()
        for phrase in phrases:
            tokens = _normalize_tokens(phrase)
            for token in tokens:
                token_counter[token] += 1
                stem_counter[_stem_token(token)] += 1
        raw[cmd] = {
            "phrases": phrases,
            "tokens": token_counter,
            "stems": stem_counter,
        }
        token_df.update(token_counter.keys())
        stem_df.update(stem_counter.keys())

    n_cmds = max(len(raw), 1)
    for cmd, profile in raw.items():
        token_weights: dict[str, float] = {}
        stem_weights: dict[str, float] = {}
        for token in profile["tokens"]:  # type: ignore[union-attr]
            df = token_df[token]
            token_weights[token] = 1.0 + ((n_cmds + 1) / (df + 1))
        for stem in profile["stems"]:  # type: ignore[union-attr]
            df = stem_df[stem]
            stem_weights[stem] = 0.6 + ((n_cmds + 1) / (df + 1)) * 0.7
        profiles[cmd] = {
            "phrases": profile["phrases"],
            "tokens": profile["tokens"],
            "stems": profile["stems"],
            "token_weights": token_weights,
            "stem_weights": stem_weights,
        }
    return profiles


def _score_command(msg: str, tokens: list[str], command: str) -> int:
    score = 0
    for hint in _COMMAND_HINTS.get(command, []):
        norm_hint = _normalize_text(hint)
        if " " in norm_hint:
            if norm_hint in msg:
                score += 4 + len(norm_hint.split())
        else:
            if any(_root_match(token, norm_hint) for token in tokens):
                score += 2 + min(len(norm_hint), 6)
    return score


def _score_intent(msg: str, tokens: list[str], stems: list[str], intent: str) -> float:
    score = 0.0
    for hint in _INTENT_HINTS.get(intent, []):
        norm_hint = _normalize_text(hint)
        if not norm_hint:
            continue
        if " " in norm_hint:
            if norm_hint in msg:
                score += 4.0 + min(len(norm_hint.split()), 6) * 0.8
        else:
            hint_stem = _stem_token(norm_hint)
            for token, stem in zip(tokens, stems):
                if token == norm_hint or stem == hint_stem or token.startswith(norm_hint[:4]):
                    score += 1.8
                    break
    return score


def classify_intent(user_message: str) -> str:
    """
    Classify a user message into an intent.
    Returns one of: 'chat', 'review', 'execute', 'work'.
    """
    msg = _normalize_text(user_message)
    tokens = _normalize_tokens(msg)
    stems = [_stem_token(token) for token in tokens]

    if not msg:
        return "chat"

    if _contains_any(msg, _EXECUTE_LAUNCH_HINTS):
        return "execute"
    if _contains_any(msg, _REVIEW_OPEN_HINTS):
        return "review"

    # Explicit file-creation detection: always wins over generic keyword match
    _FILE_WORK_ACTIONS = frozenset({"crea", "crear", "genera", "generar", "escrib", "redacta", "make", "creat", "generat", "writ"})
    _FILE_INDICATORS = frozenset({".md", ".py", ".js", ".ts", ".json", ".txt", ".html", ".css", ".yaml", ".yml", ".tsx", ".jsx"})
    _has_action = any(any(t.startswith(a) for a in _FILE_WORK_ACTIONS) for t in tokens)
    _has_file = any(ind in msg for ind in _FILE_INDICATORS) or ("archivo" in msg) or ("fichero" in msg)
    if _has_action and _has_file:
        return "work"

    # 1. Strong keyword match stays first for obvious cases.
    for intent, words in _KEYWORDS.items():
        if any(_normalize_text(w) in msg for w in words):
            return intent

    scores = {}
    for intent in ("chat", "review", "execute", "work"):
        score = _score_intent(msg, tokens, stems, intent)
        score += _prototype_score(stems, intent)
        score += _macro_intent_score(msg, tokens, intent)
        score += len(set(tokens).intersection(_INTENT_PROTOTYPES.get(intent, frozenset()))) * 0.5
        scores[intent] = score

    best_intent, best_score = max(scores.items(), key=lambda item: item[1])
    runner_up = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
    action_score = max(scores["review"], scores["execute"], scores["work"])
    chat_score = scores["chat"]

    if best_intent == "chat" and action_score >= chat_score + 0.75:
        best_intent = max(("review", "execute", "work"), key=lambda intent: scores[intent])
        best_score = scores[best_intent]
        runner_up = max(chat_score, sorted((scores["review"], scores["execute"], scores["work"]), reverse=True)[1])

    if best_score < 1.5:
        if len(tokens) <= 8:
            return "chat"
        return "work"

    if best_intent != "chat" and (best_score - runner_up) < 0.8 and len(tokens) <= 8:
        return "chat"

    if best_intent == "chat" and best_score < 2.2:
        return "chat"

    # 2. Short messages without strong action cues → chat
    if len(msg) < 40 and not any(t in msg for t in [":\\", "/", "\\", ".py", ".js", ".md"]):
        if best_intent == "work" and best_score < 3.8:
            return "chat"
        if best_intent == "review" and best_score < 3.2:
            return "chat"

    if best_intent != "chat" and action_score >= chat_score + 0.5:
        return best_intent

    return best_intent


def get_few_shot_examples(intent: str, max_examples: int = 3) -> str:
    """
    Return formatted few-shot examples for the given intent,
    to be injected into the system prompt.
    """
    examples = _DEFAULT_EXAMPLES.get(intent, [])
    if not examples:
        return ""

    lines: List[str] = []
    lines.append(f"\n--- FEW-SHOT EXAMPLES FOR INTENT: {intent.upper()} ---")
    for ex in examples[:max_examples]:
        u = ex.get("user", "").strip()
        a = ex.get("assistant", "").strip()
        if not u:
            continue
        lines.append(f"User: {u}")
        lines.append(f"Assistant: {a[:300] if a else '(respond naturally)'}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command-intent classification (maps natural language → slash command)
# ---------------------------------------------------------------------------

_CMD_DATA_PATH = Path(__file__).with_name("command_intents.json")
_CMD_INDEX: dict[str, str] = {}   # phrase → command


def _build_cmd_index() -> dict[str, str]:
    """Carga command_intents.json y construye un índice phrase→command."""
    index: dict[str, str] = {}
    if not _CMD_DATA_PATH.exists():
        return index
    try:
        data = json.loads(_CMD_DATA_PATH.read_text(encoding="utf-8"))
        for cmd, info in data.get("commands", {}).items():
            for phrase in info.get("phrases", []):
                index[phrase.lower().strip()] = cmd
    except Exception:
        pass
    return index


_CMD_INDEX = _build_cmd_index()
_COMMAND_PROFILES = _build_command_profiles()


def reload_command_index() -> int:
    """Recarga el índice de comandos desde disco. Retorna número de frases cargadas."""
    global _CMD_INDEX, _COMMAND_PROFILES
    _CMD_INDEX = _build_cmd_index()
    _COMMAND_PROFILES = _build_command_profiles()
    return len(_CMD_INDEX)


def _score_command(msg: str, tokens: list[str], command: str) -> int:
    score = 0
    for hint in _COMMAND_HINTS.get(command, []):
        norm_hint = _normalize_text(hint)
        if " " in norm_hint:
            if norm_hint in msg:
                score += 4 + len(norm_hint.split())
        else:
            if any(_root_match(token, norm_hint) for token in tokens):
                score += 2 + min(len(norm_hint), 6)
    return score


def classify_command_intent(user_message: str) -> str | None:
    """Clasifica si el mensaje es un comando natural y devuelve el comando slash.

    Retorna el comando slash (ej. '/credentials set') si hay coincidencia,
    o None si el mensaje debe tratarse como chat normal.

    Estrategia:
    1. Coincidencia exacta en el índice (más rápida y precisa).
    2. Coincidencia parcial: la frase del índice está contenida en el mensaje
       y el mensaje es corto (≤ 6 palabras), para evitar falsos positivos.
    """
    msg = _normalize_text(user_message)
    tokens = msg.split()
    if not msg:
        return None

    # Coincidencia exacta
    if msg in _CMD_INDEX:
        return _CMD_INDEX[msg]
    compact = msg.replace(" ", "")
    for phrase, cmd in _CMD_INDEX.items():
        if _normalize_text(phrase) == msg or _normalize_text(phrase).replace(" ", "") == compact:
            return cmd

    # Reglas por comando: frases nuevas, sin depender de coincidencia literal.
    best_cmd: str | None = None
    best_score = 0
    runner_up = 0
    for cmd in _CMD_INDEX.values():
        score = _score_command(msg, tokens, cmd)
        if score > best_score:
            runner_up = best_score
            best_cmd = cmd
            best_score = score
        elif score > runner_up:
            runner_up = score

    # Evita falsos positivos en chat corto o señales débiles.
    if best_cmd == "/good" and best_score < 8:
        return None
    if best_score >= 6:
        return best_cmd

    # Coincidencia parcial solo en mensajes cortos, pero con frase completa
    if len(tokens) <= 6:
        for phrase, cmd in _CMD_INDEX.items():
            norm_phrase = _normalize_text(phrase)
            if norm_phrase in msg and len(norm_phrase) >= 6:
                if cmd == "/good" and norm_phrase == "bien":
                    continue
                return cmd

    return None


def command_intent_description(command: str) -> str:
    """Devuelve la descripción del comando desde command_intents.json."""
    try:
        data = json.loads(_CMD_DATA_PATH.read_text(encoding="utf-8"))
        return data.get("commands", {}).get(command, {}).get("description", "")
    except Exception:
        return ""


def command_intent_is_wizard(command: str) -> bool:
    """True si el comando tiene asistente guiado interactivo."""
    try:
        data = json.loads(_CMD_DATA_PATH.read_text(encoding="utf-8"))
        return bool(data.get("commands", {}).get(command, {}).get("wizard", False))
    except Exception:
        return False


def should_enable_tools(intent: str) -> bool:
    """
    Decide whether tool-calling should be offered to the model
    based on the detected intent.
    """
    return intent in ("review", "execute", "work")


def intent_guidance(intent: str) -> str:
    """
    Extra system-guidance text tailored to the detected intent.
    """
    guidance = {
        "chat": (
            "The user is just chatting. Do NOT call any tools. "
            "Respond naturally and concisely."
        ),
        "review": (
            "The user wants to REVIEW or EXAMINE something. "
            "Use file-read or dir-list tools ONLY if a path is mentioned. "
            "Summarize findings, do NOT modify anything unless explicitly asked."
        ),
        "execute": (
            "The user wants to EXECUTE or RUN something. "
            "Use execute_command tool if a command is provided, "
            "otherwise ask for clarification."
        ),
        "work": (
            "The user wants you to WORK on code or content. "
            "Use dir-list and file-read to inspect current state first, then file-write or file-edit as needed. "
            "If the task is large, confirm the plan before changing files."
        ),
    }
    return guidance.get(intent, "")


