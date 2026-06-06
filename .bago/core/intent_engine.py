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
from pathlib import Path
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Load few-shot dataset (auto-generated from session_store)
# ---------------------------------------------------------------------------

_DEFAULT_EXAMPLES: Dict[str, List[Dict[str, str]]] = {}
_DATA_PATH = Path(__file__).with_name("intent_examples.json")


def _load_examples() -> Dict[str, List[Dict[str, str]]]:
    if _DATA_PATH.exists():
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


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
        "bago", "bago next", "bago start", "español", "hello", "hi",
    ],
    "review": [
        "revisa", "mira", "reune", "busca", "chequea", "examina",
        "verifica", "analiza esto", "mira esto", "mira ahora",
        "list_directory", "read_file", "dame el contenido",
    ],
    "execute": [
        "ejecuta", "corre", "lanza", "dispara", "run", "execute",
        "corre el comando", "ejecuta el script", "corre el script",
    ],
    "work": [
        "trabaja", "modulariza", "adapta", "crea", "modifica",
        "refactoriza", "estructurala", "ordena", "desarrolla",
        "implementa", "construye", "genera", "haz que", "hazme",
        "adaptalo", "modularizala", "estructuralo", "organiza",
    ],
}


def classify_intent(user_message: str) -> str:
    """
    Classify a user message into an intent.
    Returns one of: 'chat', 'review', 'execute', 'work'.
    """
    msg = user_message.lower().strip()

    # 1. Strong keyword match
    for intent, words in _KEYWORDS.items():
        if any(w in msg for w in words):
            return intent

    # 2. Short messages without path/command-like tokens → chat
    if len(msg) < 40 and not any(t in msg for t in [":\\", "/", "\\", ".py", ".js", ".md"]):
        return "chat"

    # 3. Default to work (user often asks for changes implicitly)
    return "work"


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


def reload_command_index() -> int:
    """Recarga el índice de comandos desde disco. Retorna número de frases cargadas."""
    global _CMD_INDEX
    _CMD_INDEX = _build_cmd_index()
    return len(_CMD_INDEX)


def classify_command_intent(user_message: str) -> str | None:
    """Clasifica si el mensaje es un comando natural y devuelve el comando slash.

    Retorna el comando slash (ej. '/credentials set') si hay coincidencia,
    o None si el mensaje debe tratarse como chat normal.

    Estrategia:
    1. Coincidencia exacta en el índice (más rápida y precisa).
    2. Coincidencia parcial: la frase del índice está contenida en el mensaje
       y el mensaje es corto (≤ 6 palabras), para evitar falsos positivos.
    """
    msg = user_message.lower().strip()
    if not msg:
        return None

    # Coincidencia exacta
    if msg in _CMD_INDEX:
        return _CMD_INDEX[msg]

    # Coincidencia parcial solo en mensajes cortos
    if len(msg.split()) <= 6:
        for phrase, cmd in _CMD_INDEX.items():
            if phrase in msg and len(phrase) >= 4:
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
            "Use read_file or list_directory tools ONLY if a path is mentioned. "
            "Summarize findings, do NOT modify anything unless explicitly asked."
        ),
        "execute": (
            "The user wants to EXECUTE or RUN something. "
            "Use execute_command tool if a command is provided, "
            "otherwise ask for clarification."
        ),
        "work": (
            "The user wants you to WORK on code or content. "
            "Use file tools to read current state, then write/modify as needed. "
            "If the task is large, confirm the plan before changing files."
        ),
    }
    return guidance.get(intent, "")
