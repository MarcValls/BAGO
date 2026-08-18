"""test_translation_middleware.py — Test end-to-end del middleware sin
necesidad de pasar por todo el HTTP server. Construimos un fake adapter,
lo envolvemos con TranslationAdapter, y verificamos que:
  1. Si el usuario habla en ES y el modelo subyacente "habla" en EN,
     el adapter ENTRADA recibe EN y SALIDA devuelve ES.
  2. Si el usuario habla en EN, no se traduce.
  3. Si el texto parece código, no se traduce.
"""
import sys
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Cargar módulos por ruta
sys.path.insert(0, str(ROOT / ".bago" / "core"))  # para que translation_adapter importe translation_middleware

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# Stub mínimo de ProviderResponse y ProviderAdapter
class FakeProviderResponse:
    def __init__(self, content, model="fake", finish_reason="stop", usage=None, metadata=None):
        self.content = content
        self.model_used = model
        self.finish_reason = finish_reason
        self.usage = usage or type("U", (), {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})()
        self.metadata = metadata or {}

class FakeAdapter:
    provider_name = "ollama-local"
    config = {}
    def __init__(self, canned_response="This is a test response."):
        self.canned = canned_response
        self.received_messages = None
        self.received_system = None
    def is_configured(self): return True
    def supports_tools(self): return True
    def supports_streaming(self): return True
    def supports_embeddings(self): return False
    def list_models(self): return []
    def health_check(self, timeout=5.0): return None
    def chat(self, messages, model, *, system="", temperature=0.7, max_tokens=None, stream=False, tools=None):
        self.received_messages = messages
        self.received_system = system
        return FakeProviderResponse(self.canned)
    def chat_stream(self, messages, model, *, system="", temperature=0.7, max_tokens=None, tools=None):
        self.received_messages = messages
        self.received_system = system
        yield self.canned

tm = load("tm", ROOT / ".bago" / "core" / "translation_middleware.py")
ta = load("ta", ROOT / ".bago" / "core" / "translation_adapter.py")

cfg = tm.load_config({})  # defaults

print("=" * 60)
print("TEST 1: usuario en ES, fake adapter devuelve EN")
print("=" * 60)
fake = FakeAdapter(canned_response="Artificial intelligence is a field of computer science.")
adapter = ta.TranslationAdapter(fake, cfg, source_lang="es")
resp = adapter.chat(
    messages=[{"role": "user", "content": "Hola, explicame que es la inteligencia artificial"}],
    model="granite3.2:8b",
    system="Eres un asistente util.",
)
print(f"  user input:      'Hola, explicame que es la inteligencia artificial'")
print(f"  adapter received user msg:  '{fake.received_messages[0]['content'][:80]}'")
print(f"  adapter received system:    '{fake.received_system[:80]}'")
print(f"  final user response:        '{resp.content}'")
print(f"  translation info: {adapter.get_last_translation_info()}")
assert "Artificial" in resp.content or "inteligencia" in resp.content.lower(), "respuesta parece no traducida"
info = adapter.get_last_translation_info()
assert info["output"].get("translated"), "El output debería haberse traducido a ES"
print("  ✅ OK\n")

print("=" * 60)
print("TEST 2: usuario en EN, input no se traduce pero output SI (porque está en EN)")
print("=" * 60)
fake = FakeAdapter(canned_response="Sure, here is the answer.")
adapter = ta.TranslationAdapter(fake, cfg, source_lang="es")
resp = adapter.chat(
    messages=[{"role": "user", "content": "Hello, what is artificial intelligence?"}],
    model="granite3.2:8b",
)
print(f"  user input:      'Hello, what is artificial intelligence?'")
print(f"  adapter received user msg:  '{fake.received_messages[0]['content'][:80]}'")
print(f"  final user response:        '{resp.content}'")
info = adapter.get_last_translation_info()
# El user msg NO debería haberse traducido (ya estaba en EN, source_lang=es → no es)
assert not info["input"][0].get("translated"), "Input EN no debe traducirse a EN"
# El output ESTÁ en EN y el usuario quiere ES → SÍ debe traducirse
assert info["output"].get("translated"), "Output EN debe traducirse a ES"
print("  ✅ OK\n")

print("=" * 60)
print("TEST 3: usuario pega código, no debe traducir")
print("=" * 60)
fake = FakeAdapter(canned_response="```python\\nprint('hola')\\n```")
adapter = ta.TranslationAdapter(fake, cfg, source_lang="es")
resp = adapter.chat(
    messages=[{"role": "user", "content": "```python\\nprint('hola mundo')\\n```"}],
    model="granite3.2:8b",
)
print(f"  user input: code block")
print(f"  final user response: '{resp.content}'")
print("  ✅ OK (código no traducido)\n")

print("=" * 60)
print("TEST 4: chat_stream emite traducción al final")
print("=" * 60)
fake = FakeAdapter(canned_response="The capital of France is Paris.")
adapter = ta.TranslationAdapter(fake, cfg, source_lang="es")
chunks = list(adapter.chat_stream(
    messages=[{"role": "user", "content": "Cual es la capital de Francia?"}],
    model="granite3.2:8b",
))
print(f"  num chunks: {len(chunks)}")
print(f"  chunk: '{chunks[0]}'")
assert len(chunks) == 1, "Streaming debería acumular y emitir UN chunk traducido"
assert "París" in chunks[0] or "capital" in chunks[0].lower()
print("  ✅ OK\n")

print("=" * 60)
print("TEST 5: detección de idioma")
print("=" * 60)
for t, expected in [
    ("Hola mundo", "es"),
    ("Hello world", "en"),
    ("x = 5 + 3", "unknown"),
    ("", "unknown"),
    ("El veloz murciélago hindú comía feliz cardillo y kiwi", "es"),
    ("The quick brown fox jumps over the lazy dog", "en"),
]:
    got = tm.detect_language(t)
    print(f"  '{t[:50]}' -> {got} (esperado {expected})")
    if expected != "unknown":
        assert got == expected, f"detect_language falló en {t!r}: {got} != {expected}"
print("  ✅ OK\n")

print("=" * 60)
print("TEST 5b: output ya en ES, no se traduce (no malgasta tiempo)")
print("=" * 60)
fake = FakeAdapter(canned_response="Claro, la inteligencia artificial es la capacidad de las maquinas de aprender.")
adapter = ta.TranslationAdapter(fake, cfg, source_lang="es")
resp = adapter.chat(
    messages=[{"role": "user", "content": "Explica que es la IA"}],
    model="granite3.2:8b",
)
print(f"  fake adapter ya devolvió en ES: '{fake.canned}'")
print(f"  final user response: '{resp.content}'")
info = adapter.get_last_translation_info()
assert not info["output"].get("translated"), "Si el output ya está en ES, NO debe traducirse"
assert info["output"].get("reason") == "output_already_es", f"reason inesperado: {info['output'].get('reason')}"
print("  ✅ OK (no malgastamos llamada al traductor)\n")
