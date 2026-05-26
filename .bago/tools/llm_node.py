#!/usr/bin/env python3
"""llm_node.py — BAGO LLM Node: puente brutal entre Ollama y el Neural Bus.

Nodo persistente que escucha `llm.request` en el Neural Bus, ejecuta
el LLM local (Ollama) con streaming real y publica `llm.chunk` +
`llm.response` de vuelta al bus. Gestiona historial por conversación.

Modos de operación:
  chat           → conversación libre con historial por correlation_id
  tool_suggest   → LLM elige qué tools BAGO usar (parsea [TOOLS: ...])
  classify_intent → LLM devuelve JSON con intent_id + confidence + tools

Eventos consumidos:
  llm.request  payload: {prompt, system?, model?, stream?, mode?, context?}

Eventos emitidos:
  llm.chunk     payload: {chunk, done, correlation_id}   ← por token (streaming)
  llm.response  payload: {text, model, elapsed, tokens, mode, suggested_tools?}
  llm.error     payload: {error, prompt_preview}

Uso:
  bago llm node               → arranca el nodo LLM (daemon)
  bago llm node --once        → procesa una petición y sale
  bago llm node --test        → self-tests
  bago llm node --dry-run     → simula sin llamar a Ollama
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import sys
import threading
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Iterator, Optional

from bago.ollama_runtime import DEFAULT_OLLAMA_PORT, default_ollama_base_url

# ── Paths ──────────────────────────────────────────────────────────────────────
TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
STATE_DIR  = BAGO_ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

CONV_LOG   = STATE_DIR / "llm_conversations.jsonl"
CFG_FILE   = STATE_DIR / "llm_config.json"

OLLAMA_PORT     = DEFAULT_OLLAMA_PORT
OLLAMA_BASE_URL = default_ollama_base_url()
DEFAULT_MODEL   = "qwen2.5-coder:7b"
MAX_HISTORY     = 20   # messages per conversation before trim
MAX_CONV_AGE    = 3600 # seconds before discarding idle conversation

# ── Colors ─────────────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty() and sys.platform != "win32"

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t

OK   = lambda t: _c("1;32", t)   # noqa: E731
WARN = lambda t: _c("1;33", t)   # noqa: E731
ERR  = lambda t: _c("1;31", t)   # noqa: E731
BOLD = lambda t: _c("1", t)      # noqa: E731
DIM  = lambda t: _c("2", t)      # noqa: E731
CYAN = lambda t: _c("1;36", t)   # noqa: E731

def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"  {DIM(ts)} {msg}")


# ── System prompt BAGO ────────────────────────────────────────────────────────

BAGO_SYSTEM_PROMPT = """Eres el asistente IA del framework BAGO (Bootstrap for AI-Guided Operations).
Ayudas a desarrolladores a navegar y mejorar su codebase usando las herramientas BAGO.

Herramientas disponibles (usa: bago <herramienta>):
  review       → revisión de código (calidad, bugs, mejoras)
  audit        → auditoría completa del proyecto
  health       → puntuación de salud del codebase
  sprint       → gestión de sprints y tareas
  npath        → grafo de conocimiento del proyecto
  secrets      → detección de secretos hardcodeados
  hardcodes    → detección de datos hardcodeados que deberían ser dinámicos
  spanish      → auditoría ortográfica español (tildes, plural/singular)
  toolsmith    → asignación dinámica de herramientas por tarea
  neural       → Neural Bus (mensajería entre agentes)
  llm          → motor LLM local (Ollama)
  roles        → contratos de roles de agentes
  dep-audit    → auditoría de dependencias
  secret-scan  → escaneo de secretos
  find-tool    → buscar herramienta adecuada para una tarea

Cuando sugieras herramientas, usa el formato exacto: [TOOLS: herramienta1, herramienta2]
Si no sabes qué herramienta usar, responde: [TOOLS: find-tool]
Responde en el idioma del usuario. Sé conciso y accionable."""

TOOL_SUGGEST_SUFFIX = """
Analiza el mensaje del usuario y decide qué herramientas BAGO usar.
Responde con una breve explicación y termina SIEMPRE con:
[TOOLS: herramienta1, herramienta2]"""

CLASSIFY_INTENT_SUFFIX = """
Clasifica la intención del usuario. Responde SOLO con JSON válido:
{
  "intent_id": "code_review|security_check|performance|cleanup|unknown",
  "confidence": 0.0-1.0,
  "tools": ["herramienta1", "herramienta2"],
  "rationale": "breve explicación"
}"""


# ── Ollama API ─────────────────────────────────────────────────────────────────

def _active_model() -> str:
    """Read active model from llm_config.json or fall back to default."""
    try:
        if CFG_FILE.exists():
            cfg = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            mid = cfg.get("active_model")
            if mid:
                # Map BAGO model ID to Ollama tag
                catalog_map = {
                    "qwen25-coder":   "qwen2.5-coder:7b",
                    "phi3-mini":      "phi3:mini",
                    "llama32-3b":     "llama3.2:3b",
                    "deepseek-coder": "deepseek-coder:6.7b",
                }
                return catalog_map.get(mid, mid)
    except Exception:
        pass
    return DEFAULT_MODEL


def _ollama_running() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", DEFAULT_OLLAMA_PORT), timeout=1):
            return True
    except OSError:
        return False


def stream_ollama(
    messages: list[dict],
    model: str,
    on_chunk: Callable[[str], None],
) -> tuple[str, int]:
    """Call Ollama /api/chat with streaming. Calls on_chunk for each token.

    Returns (full_text, approx_token_count).
    Raises urllib.error.URLError if Ollama is unreachable.
    """
    body = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   True,
        "options":  {"temperature": 0.7, "num_predict": 2048},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    full_text   = ""
    token_count = 0

    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = obj.get("message", {}).get("content", "")
            if chunk:
                full_text += chunk
                token_count += 1
                on_chunk(chunk)
            if obj.get("done"):
                # Ollama reports eval_count (tokens) in the final message
                token_count = obj.get("eval_count", token_count)
                break

    return full_text, token_count


def query_ollama(
    prompt: str,
    model: str,
    system: str = "",
    history: Optional[list[dict]] = None,
) -> tuple[str, int]:
    """Non-streaming call — returns (full_text, token_count)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   False,
        "options":  {"temperature": 0.7, "num_predict": 2048},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    text   = obj.get("message", {}).get("content", "")
    tokens = obj.get("eval_count", 0)
    return text, tokens


# ── Tool suggestion parser ─────────────────────────────────────────────────────

def parse_tool_suggestions(text: str) -> list[str]:
    """Extract tools from [TOOLS: a, b, c] markers in LLM response."""
    import re
    matches = re.findall(r'\[TOOLS?:\s*([^\]]+)\]', text, re.IGNORECASE)
    tools = []
    for m in matches:
        for t in m.split(","):
            t = t.strip().lower().replace(" ", "-")
            if t:
                tools.append(t)
    return list(dict.fromkeys(tools))  # deduplicated, ordered


def parse_intent_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM classify_intent response."""
    import re
    m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


# ── Conversation history ───────────────────────────────────────────────────────

class ConversationStore:
    """Thread-safe in-memory conversation store with JSONL persistence."""

    def __init__(self, log_path: Path) -> None:
        self._log = log_path
        self._lock = threading.Lock()
        # {corr_id: {"messages": [...], "last_ts": float}}
        self._store: dict[str, dict] = {}

    def get_history(self, corr_id: str) -> list[dict]:
        with self._lock:
            entry = self._store.get(corr_id)
            if entry:
                entry["last_ts"] = time.time()
                return list(entry["messages"])
            return []

    def append(self, corr_id: str, role: str, content: str) -> None:
        with self._lock:
            if corr_id not in self._store:
                self._store[corr_id] = {"messages": [], "last_ts": time.time()}
            entry = self._store[corr_id]
            entry["messages"].append({"role": role, "content": content})
            entry["last_ts"] = time.time()
            # Trim old messages
            if len(entry["messages"]) > MAX_HISTORY:
                entry["messages"] = entry["messages"][-MAX_HISTORY:]
            # Persist
            self._persist(corr_id, role, content)

    def _persist(self, corr_id: str, role: str, content: str) -> None:
        try:
            record = {
                "ts":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "corr_id": corr_id,
                "role":    role,
                "content": content[:500],  # truncate for log
            }
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def prune_stale(self) -> None:
        cutoff = time.time() - MAX_CONV_AGE
        with self._lock:
            stale = [cid for cid, e in self._store.items() if e["last_ts"] < cutoff]
            for cid in stale:
                del self._store[cid]


_conversations = ConversationStore(CONV_LOG)


# ── LLM Node ──────────────────────────────────────────────────────────────────

def make_llm_node(dry_run: bool = False, verbose: bool = False):
    """Build and return a configured BusNode that handles llm.request events."""
    try:
        from bago_node import BusNode
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bago_node", str(TOOLS_DIR / "bago_node.py"))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        BusNode = mod.BusNode  # type: ignore[misc]

    node = BusNode(
        "llm",
        role="processing",
        capabilities=["llm-inference", "tool-suggestion", "intent-classification", "streaming"],
    )

    @node.on("llm.request")
    def handle_llm_request(event: dict) -> None:
        payload    = event.get("payload", {})
        prompt     = payload.get("prompt", "").strip()
        system     = payload.get("system", "")
        model_id   = payload.get("model")
        mode       = payload.get("mode", "chat")
        do_stream  = payload.get("stream", True)
        context    = payload.get("context")     # optional external history
        corr       = event.get("correlation_id") or event.get("id") or uuid.uuid4().hex[:8]
        origin     = event.get("from", "*")

        if not prompt:
            return

        _log(f"{CYAN(origin)} → llm.request [{mode}] {BOLD(repr(prompt[:50]))}")

        # Resolve model
        model = _active_model()
        if model_id:
            # Accept either BAGO ID or Ollama tag directly
            _catalog = {
                "qwen25-coder":   "qwen2.5-coder:7b",
                "phi3-mini":      "phi3:mini",
                "llama32-3b":     "llama3.2:3b",
                "deepseek-coder": "deepseek-coder:6.7b",
            }
            model = _catalog.get(model_id, model_id)

        # Build system prompt
        if not system:
            system = BAGO_SYSTEM_PROMPT
        if mode == "tool_suggest":
            system = BAGO_SYSTEM_PROMPT + TOOL_SUGGEST_SUFFIX
        elif mode == "classify_intent":
            system = BAGO_SYSTEM_PROMPT + CLASSIFY_INTENT_SUFFIX

        # Build messages with history
        history = context or _conversations.get_history(corr)
        messages: list[dict] = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        if verbose:
            _log(f"  model={model}  history={len(history)} msgs  mode={mode}")

        if dry_run:
            _emit_dry_run(node, prompt, model, mode, corr, origin)
            return

        if not _ollama_running():
            _log(f"{WARN('⚠')} Ollama no disponible — emitiendo llm.error")
            node.emit("llm.error", {
                "error":          "Ollama no está en ejecución. Usa: bago llm start",
                "prompt_preview": prompt[:100],
            }, to=origin, correlation_id=corr)
            return

        # Execute
        start = time.time()
        full_text = ""
        token_count = 0
        ok = False

        try:
            if do_stream:
                def on_chunk(chunk: str) -> None:
                    node.emit("llm.chunk", {
                        "chunk":          chunk,
                        "done":           False,
                        "correlation_id": corr,
                    }, to=origin, correlation_id=corr)

                full_text, token_count = stream_ollama(messages, model, on_chunk)
                # Final chunk marker
                node.emit("llm.chunk", {
                    "chunk":          "",
                    "done":           True,
                    "correlation_id": corr,
                }, to=origin, correlation_id=corr)
            else:
                full_text, token_count = query_ollama(prompt, model, system, history)

            ok = True

        except urllib.error.URLError as exc:
            full_text = f"[LLM ERROR] No se pudo contactar Ollama: {exc}"
            node.emit("llm.error", {
                "error":          str(exc),
                "prompt_preview": prompt[:100],
            }, to=origin, correlation_id=corr)

        except Exception as exc:
            full_text = f"[LLM ERROR] {exc}"
            node.emit("llm.error", {
                "error":          str(exc),
                "prompt_preview": prompt[:100],
            }, to=origin, correlation_id=corr)

        elapsed = round(time.time() - start, 2)

        # Update conversation history
        if ok:
            _conversations.append(corr, "user",      prompt)
            _conversations.append(corr, "assistant",  full_text)

        # Parse mode-specific extras
        suggested_tools: list[str] = []
        intent_data: Optional[dict] = None

        if mode == "tool_suggest":
            suggested_tools = parse_tool_suggestions(full_text)
            if suggested_tools:
                node.emit("llm.tool_suggestion", {
                    "tools":          suggested_tools,
                    "rationale":      full_text[:400],
                    "correlation_id": corr,
                }, to=origin, correlation_id=corr)

        elif mode == "classify_intent":
            intent_data = parse_intent_json(full_text)
            if intent_data:
                suggested_tools = intent_data.get("tools", [])

        # Emit final llm.response
        response_payload: dict = {
            "text":    full_text,
            "model":   model,
            "elapsed": elapsed,
            "tokens":  token_count,
            "mode":    mode,
            "ok":      ok,
        }
        if suggested_tools:
            response_payload["suggested_tools"] = suggested_tools
        if intent_data:
            response_payload["intent"] = intent_data

        node.emit("llm.response", response_payload, to=origin, correlation_id=corr)

        icon = OK("✓") if ok else WARN("⚠")
        _log(f"{icon} llm.response [{model}] {token_count} tokens  {elapsed}s")

    @node.on("system.node_up")
    def handle_node_up(event: dict) -> None:
        nid = event.get("payload", {}).get("node_id", "?")
        if nid != "llm" and verbose:
            _log(f"⚡ {BOLD(nid)} conectado")

    return node


def _emit_dry_run(node, prompt: str, model: str, mode: str, corr: str, origin: str) -> None:
    fake_text = f"[dry-run] Respondería a: {repr(prompt[:40])} con modelo {model} en modo {mode}"
    if mode == "tool_suggest":
        fake_text += "\n[TOOLS: review, health]"
        node.emit("llm.tool_suggestion", {
            "tools": ["review", "health"], "rationale": fake_text, "correlation_id": corr,
        }, to=origin, correlation_id=corr)
    elif mode == "classify_intent":
        fake_text = '{"intent_id":"code_review","confidence":0.9,"tools":["review"],"rationale":"dry-run"}'
    node.emit("llm.response", {
        "text": fake_text, "model": model, "elapsed": 0.0, "tokens": 0, "mode": mode, "ok": True,
    }, to=origin, correlation_id=corr)


# ── Stale conversation pruner ──────────────────────────────────────────────────

def _start_pruner() -> None:
    def _loop():
        while True:
            time.sleep(300)  # every 5 min
            _conversations.prune_stale()
    t = threading.Thread(target=_loop, daemon=True)
    t.start()


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _self_test() -> int:
    results = []

    # Test 1: parse_tool_suggestions
    text = "Deberías usar estas tools:\n[TOOLS: review, health, audit]"
    tools = parse_tool_suggestions(text)
    ok1 = tools == ["review", "health", "audit"]
    results.append(("parse_tool_suggestions", ok1, str(tools)))

    # Test 2: parse_tool_suggestions — case insensitive
    text2 = "[tools: Secret-Scan, DEP-AUDIT]"
    tools2 = parse_tool_suggestions(text2)
    ok2 = "secret-scan" in tools2 and "dep-audit" in tools2
    results.append(("parse_tools_case_insensitive", ok2, str(tools2)))

    # Test 3: parse_intent_json
    text3 = 'Respuesta:\n{"intent_id":"security_check","confidence":0.9,"tools":["secrets"],"rationale":"x"}'
    intent = parse_intent_json(text3)
    ok3 = intent is not None and intent.get("intent_id") == "security_check"
    results.append(("parse_intent_json", ok3, str(intent)))

    # Test 4: parse_intent_json — invalid JSON
    ok4 = parse_intent_json("no json here") is None
    results.append(("parse_intent_json_invalid", ok4, "None as expected"))

    # Test 5: ConversationStore
    store = ConversationStore(Path("/dev/null") if sys.platform != "win32" else STATE_DIR / "test_conv.jsonl")
    store.append("corr1", "user", "hola")
    store.append("corr1", "assistant", "hola mundo")
    hist = store.get_history("corr1")
    ok5 = len(hist) == 2 and hist[0]["role"] == "user"
    results.append(("ConversationStore", ok5, f"{len(hist)} msgs"))

    # Test 6: make_llm_node doesn't crash
    try:
        n = make_llm_node(dry_run=True)
        ok6 = n.node_id == "llm" and n.role == "processing"
    except Exception as e:
        ok6 = False
        results.append(("make_llm_node", ok6, str(e)))
    else:
        results.append(("make_llm_node", ok6, f"node_id={n.node_id}"))

    # Test 7: _active_model doesn't crash
    try:
        m = _active_model()
        ok7 = isinstance(m, str) and len(m) > 0
    except Exception as e:
        ok7 = False
    results.append(("active_model", ok7, _active_model()))

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  BAGO LLM Node — Self-tests ({passed}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}  {DIM(detail)}")
    return 0 if passed == len(results) else 1


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(
        description="BAGO LLM Node — puente Ollama ↔ Neural Bus"
    )
    ap.add_argument("--dry-run",  action="store_true", help="Simula sin llamar a Ollama")
    ap.add_argument("--verbose",  action="store_true", help="Output detallado")
    ap.add_argument("--status",   action="store_true", help="Muestra estado y sale")
    ap.add_argument("--once",     action="store_true", help="Procesa una petición y sale")
    ap.add_argument("--test",     action="store_true", help="Ejecuta self-tests")
    args = ap.parse_args(argv)

    if args.test:
        return _self_test()

    if args.status:
        print()
        print(f"  {BOLD('🤖 BAGO LLM Node')}")
        print(f"  Modelo activo : {CYAN(_active_model())}")
        print(f"  Ollama        : {OK('activo') if _ollama_running() else WARN('inactivo — inicia con: bago llm start')}")
        print(f"  Bus           : {'disponible' if (STATE_DIR / 'neural_bus.json').exists() else 'no materializado'}")
        print(f"  Modo          : estado")
        return 0

    print()
    print(f"  {BOLD('🤖 BAGO LLM Node')}")
    print(f"  Modelo activo : {CYAN(_active_model())}")
    print(f"  Ollama        : {OK('activo') if _ollama_running() else WARN('inactivo — inicia con: bago llm start')}")
    print(f"  Modo          : {'dry-run' if args.dry_run else 'live'}")
    print(f"  Conectando al Neural Bus…\n")

    node = make_llm_node(dry_run=args.dry_run, verbose=args.verbose)

    if not node.connect():
        print(f"  {ERR('✗')} No se pudo conectar al Neural Bus.")
        print(f"  Inicia el bus primero: bago neural serve")
        return 1

    print(f"  {OK('●')} LLM Node activo — escuchando [llm.request]\n")

    _start_pruner()

    if args.once:
        ev = node.wait_for("llm.request", timeout=60)
        if ev:
            print(f"  Procesado: {ev.get('payload', {}).get('prompt', '?')[:60]}")
        else:
            print(f"  {WARN('⚠')} Timeout — no llegaron peticiones.")
        node.disconnect()
        return 0

    try:
        node.run()
    except KeyboardInterrupt:
        print(f"\n  {DIM('LLM Node detenido.')}")
        node.disconnect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
