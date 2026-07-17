"""test_intent_routing.py — Reproduce y documenta el bug de clasificación
de intent del mensaje 'genera un resumen sobre IA LA PREGUNTA EN UN TXT'.

Hipótesis: classify_intent devuelve 'work' porque la palabra 'TXT' contiene
'.txt' como substring, lo que dispara el modo agente con tool_registry, y
el modelo sobre-actúa emitiendo tool_calls espurios (search-symbol, etc).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "intent_engine",
    ROOT / ".bago" / "core" / "intent_engine.py",
)
ie = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ie)

PROMPTS = [
    # El que reportaste
    "genera un resumen sobre IA LA PREGUNTA EN UN TXT",
    # Variantes
    "genera un resumen sobre IA en un txt",
    "escribe un resumen de IA en un .txt",
    "crea un archivo TXT con resumen de IA",
    "hazme un resumen de IA en formato texto",
    "resumen sobre IA",
    "explica qué es la IA",
    "genera un archivo .py con un hola mundo",
    "genera un poema corto sobre el mar",  # el que sí funcionó
    "escribe un txt con un resumen de IA",
    "crea txt resumen IA",
]

print(f"{'prompt':65} -> {'intent':10} (esperado)")
print("-" * 90)
for p in PROMPTS:
    intent = ie.classify_intent(p)
    # Detectar por qué clasificó así
    msg = ie._normalize_text(p)
    file_actions = frozenset({"crea", "crear", "genera", "generar", "escrib", "redacta", "make", "creat", "generat", "writ"})
    file_indicators = frozenset({".md", ".py", ".js", ".ts", ".json", ".txt", ".html", ".css", ".yaml", ".yml", ".tsx", ".jsx"})
    has_action = any(any(t.startswith(a) for a in file_actions) for t in ie._normalize_tokens(msg))
    has_file = any(ind in msg for ind in file_indicators) or ("archivo" in msg) or ("fichero" in msg)
    flags = []
    if has_action:
        flags.append("action")
    if has_file:
        flags.append(f"file-ind[{[i for i in file_indicators if i in msg]}]")
    flag_str = ",".join(flags) if flags else "-"
    print(f"{p!r:65} -> {intent:10} [{flag_str}]")

print()
print("Bug si 'genera ... EN UN TXT' (mayúsculas, sin punto) clasifica como 'work'")
print("debería ser 'chat' porque 'TXT' sin punto no es una extensión real.")
