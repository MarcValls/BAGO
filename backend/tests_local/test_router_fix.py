"""test_router_fix.py — Validación del fix del router.

El bug original era:
    AttributeError: 'int' object has no attribute 'get'
en session_turn_mixin.py:180, cuando json.loads() devolvía un escalar
(int/float/str) en lugar de un dict.

El fix añade:
    if not isinstance(data, dict):
        return self._route_fallback(text)

Probamos que ese guard funciona con todos los casos edge.
"""
import sys
from pathlib import Path
import importlib.util
from unittest.mock import MagicMock

# Cargar el módulo
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "session_turn_mixin",
    ROOT / ".bago" / "core" / "session_turn_mixin.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_mgr(route_response: str):
    """Build a minimal SessionTurnMixin stand-in for _route_from_model."""
    # We invoke the unbound method with a stub self.
    mgr = MagicMock()
    mgr._route_fallback = lambda text: {"kind": "chat", "source": "fallback"}
    # Patch _ensure_adapter to return a mock adapter.chat that returns our content
    adapter = MagicMock()
    adapter.chat.return_value.content = route_response
    mgr._ensure_adapter.return_value = adapter
    mgr._route_system_prompt = lambda: "system"
    mgr.model = "test-model"
    mgr._route_from_model = mod.SessionTurnMixin._route_from_model.__get__(mgr)
    return mgr


CASES = [
    # (descripcion, json crudo que devuelve el modelo, esperado: "fallback" | "parsed")
    ("dict válido", '{"kind": "chat", "command": "", "args": []}', "parsed"),
    ("int escalar", "42", "fallback"),
    ("float escalar", "3.14", "fallback"),
    ("string escalar", '"hello"', "fallback"),
    ("bool escalar", "true", "fallback"),
    ("null escalar", "null", "fallback"),
    ("lista", '[1, 2, 3]', "fallback"),
    ("dict vacío", '{}', "parsed"),
    ("dict con kind inválido", '{"kind": "hack", "command": ""}', "fallback"),
    ("dict con kind=command pero sin /", '{"kind": "command", "command": "ls"}', "fallback"),
    ("dict con kind=command válido", '{"kind": "command", "command": "/help"}', "parsed"),
    ("no-json, prose", 'I cannot route this.', "fallback"),
    ("json en bloque ```", '```json\n{"kind":"chat"}\n```', "parsed"),
    ("json en bloque ``` con prose", 'Sure!\n```json\n{"kind":"chat"}\n```\nDone.', "parsed"),
    ("json corrupto", '{"kind": ', "fallback"),
    ("string vacío", '', "fallback"),
    ("whitespace", '   \n  ', "fallback"),
    ("dict con args no-list", '{"kind":"chat","args":"oops"}', "parsed"),  # args se coerce
    ("dict con confidence no-num", '{"kind":"chat","confidence":"high"}', "parsed"),
    ("int con llaves alrededor", '{42}', "fallback"),  # regex extrae {} y falla el loads
]

passed = 0
failed = 0
for desc, raw, expected in CASES:
    mgr = make_mgr(raw)
    try:
        result = mgr._route_from_model("test message")
    except Exception as exc:
        print(f"  ❌ EXCEPCIÓN en '{desc}': {type(exc).__name__}: {exc}")
        failed += 1
        continue

    is_fallback = result.get("source") == "fallback"
    got = "fallback" if is_fallback else "parsed"
    status = "✅" if got == expected else "❌"
    print(f"  {status} '{desc}' -> kind={result.get('kind')!r} source={result.get('source')!r} (esperado: {expected})")
    if got == expected:
        passed += 1
    else:
        failed += 1

print()
print(f"Pasados: {passed}/{len(CASES)}  Fallados: {failed}")
sys.exit(0 if failed == 0 else 1)
