#!/usr/bin/env python3
"""neural_router.py — BAGO Neural Router

El cerebro del ecosistema. Conecta nodos y ejecuta el arco reflejo completo:

  user.message
      ↓
  [personality enrichment] → user.context
      ↓
  [intent_router]  → intent.detected
      ↓ (si no_match → fallback LLM)
  [llm node]       → llm.request → llm.response (tool suggestions)
      ↓
  [tool_runner]    → tool.request → tool.result
      ↓
  [user.response]  → entregado al nodo de origen (Telegram, WhatsApp, Hub, CLI)

El router NO contiene lógica de negocio. Orquesta los nodos existentes
del ecosistema BAGO via el Neural Bus.

Nodos gestionados:
  intent_router   → identifica intención del mensaje (intent_router.py)
  tool_runner     → ejecuta tools BAGO de forma segura (bago CLI subprocess)
  personality     → enriquece contexto con perfil del usuario
  llm             → consulta al LLM local si la intención lo requiere

Uso:
  bago neural router          → inicia el router (blocking)
  bago neural router --once   → procesa un evento y sale (debug)
  bago neural router --dry-run → muestra routing sin ejecutar tools
  python3 neural_router.py --test
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR    = Path(__file__).resolve().parent
BAGO_ROOT    = TOOLS_DIR.parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_SCRIPT  = PROJECT_ROOT / "bago"
PYTHON       = sys.executable


def _find_tool(stem: str) -> Path:
    """Locate tool by stem with rglob fallback (resilient to reorganisation)."""
    direct = TOOLS_DIR / f"{stem}.py"
    if direct.exists():
        return direct
    hits = list(BAGO_ROOT.rglob(f"{stem}.py"))
    return hits[0] if hits else direct

# ── Colors ──
_USE_COLOR = sys.stdout.isatty() and sys.platform != "win32"
def _c(code, t): return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t
OK   = lambda t: _c("1;32", t)   # noqa
WARN = lambda t: _c("1;33", t)   # noqa
ERR  = lambda t: _c("1;31", t)   # noqa
DIM  = lambda t: _c("2", t)      # noqa
BOLD = lambda t: _c("1", t)      # noqa
CYAN = lambda t: _c("1;36", t)   # noqa


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"  {DIM(ts)}  {msg}")


# ── Tool runner (safe subprocess) ──────────────────────────────────────────────

def run_tool(cmd: str, timeout: int = 60) -> dict:
    """Execute a BAGO tool via CLI and return structured result."""
    start = time.time()
    try:
        result = subprocess.run(
            [str(BAGO_SCRIPT), cmd],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        elapsed = time.time() - start
        return {
            "cmd": cmd,
            "rc": result.returncode,
            "output": (result.stdout + result.stderr).strip(),
            "elapsed": round(elapsed, 2),
            "ok": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "rc": 1, "output": f"TIMEOUT ({timeout}s)", "elapsed": timeout, "ok": False}
    except Exception as e:
        return {"cmd": cmd, "rc": 1, "output": str(e), "elapsed": 0.0, "ok": False}


# ── Intent execution (calls intent_router.py inline) ──────────────────────────

def resolve_intent(text: str, dry_run: bool = False) -> dict:
    """Call intent_router to map text to tools, then execute them.

    Returns:
      {
        "intent_id": "security_check",
        "intent_name": "Auditoría de seguridad",
        "tools": ["secret-scan", "dep-audit"],
        "results": [{"cmd": "secret-scan", "rc": 0, "output": "...", ...}],
        "summary": "...",
        "ok": True/False,
      }
    """
    # Import intent_router inline (avoids subprocess overhead)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_intent_router", str(_find_tool("intent_router"))
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        intents = mod.identify_intents(text, top_n=1)
    except Exception as e:
        return {
            "intent_id": "unknown",
            "intent_name": "Error cargando intent_router",
            "tools": [],
            "results": [],
            "summary": f"Error: {e}",
            "ok": False,
        }

    if not intents:
        return {
            "intent_id": "no_match",
            "intent_name": "Sin intención reconocida",
            "tools": [],
            "results": [],
            "summary": "No identifiqué qué quieres hacer. Describe el problema con más detalle.",
            "ok": True,
        }

    _score, intent = intents[0]
    tools = intent["tools"]
    results = []

    if not dry_run:
        for tool_cmd in tools:
            _log(f"▶ bago {tool_cmd}")
            r = run_tool(tool_cmd)
            results.append(r)
            icon = OK("✓") if r["ok"] else WARN("⚠")
            _log(f"{icon} {tool_cmd}  ({r['elapsed']}s)")

    # Build summary
    ok_count  = sum(1 for r in results if r["ok"])
    fail_count = len(results) - ok_count

    if dry_run:
        summary = f"[dry-run] Haría: {' → '.join(tools)}"
    elif not results:
        summary = f"Intención: {intent['name']} (sin tools ejecutados)"
    elif fail_count == 0:
        summary = f"✅ {intent['name']} completado ({ok_count}/{len(results)} tools OK)"
    else:
        summary = f"⚠️ {intent['name']}: {fail_count} tool(s) con problemas"

    return {
        "intent_id":   intent["id"],
        "intent_name": intent["name"],
        "tools":       tools,
        "results":     results,
        "summary":     summary,
        "ok":          fail_count == 0,
    }


def _request_llm_tool_suggest(
    node,
    text: str,
    corr: str,
    origin: str,
    dry_run: bool,
    timeout: float = 30.0,
) -> list[str]:
    """Ask the LLM node to suggest tools for `text`.

    Emits `llm.request` (mode=tool_suggest) and waits up to `timeout` seconds
    for `llm.tool_suggestion` or `llm.response`. Returns list of tool names.
    Falls back to [] if the LLM node is not connected or times out.
    """
    import threading
    result_holder: list[list[str]] = [[]]
    event = threading.Event()

    def on_llm_tool_suggestion(ev: dict) -> None:
        if ev.get("correlation_id") == corr:
            result_holder[0] = ev.get("payload", {}).get("tools", [])
            event.set()

    def on_llm_response(ev: dict) -> None:
        # Fallback: parse tools from the response text if no tool_suggestion event
        if ev.get("correlation_id") == corr and not event.is_set():
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "_llm_node", str(TOOLS_DIR / "llm_node.py")
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                tools = mod.parse_tool_suggestions(ev.get("payload", {}).get("text", ""))
                result_holder[0] = tools
            except Exception:
                pass
            event.set()

    # Register temporary listeners
    node._handlers.setdefault("llm.tool_suggestion", []).append(on_llm_tool_suggestion)
    node._handlers.setdefault("llm.response", []).append(on_llm_response)

    try:
        if dry_run:
            return ["review", "health"]

        node.emit("llm.request", {
            "prompt": text,
            "mode":   "tool_suggest",
            "stream": False,
        }, to="llm", correlation_id=corr)

        event.wait(timeout=timeout)
    finally:
        try:
            node._handlers.get("llm.tool_suggestion", []).remove(on_llm_tool_suggestion)
        except ValueError:
            pass
        try:
            node._handlers.get("llm.response", []).remove(on_llm_response)
        except ValueError:
            pass

    return result_holder[0]




def load_personality() -> dict:
    """Load user personality profile from state/."""
    profile_path = BAGO_ROOT / "state" / "user_personality_profile.json"
    try:
        if profile_path.exists():
            return json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def enrich_context(event: dict, personality: dict) -> dict:
    """Augment a user.message event with personality context."""
    enriched = dict(event)
    enriched.setdefault("payload", {})
    if personality:
        enriched["payload"]["_user_style"]    = personality.get("personality", {}).get("style", "")
        enriched["payload"]["_user_language"]  = personality.get("language", {}).get("primary", "es")
        enriched["payload"]["_user_register"]  = personality.get("language", {}).get("register", "neutral")
        vocab = personality.get("vocabulary", [])
        if vocab:
            enriched["payload"]["_vocabulary"] = vocab[:10]  # top 10 terms
    return enriched


# ── Main router logic ──────────────────────────────────────────────────────────

def make_router(dry_run: bool = False, verbose: bool = False):
    """Return a configured BusNode that routes user.message events."""
    try:
        from bago_node import BusNode
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bago_node", str(_find_tool("bago_node")))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        BusNode = mod.BusNode  # type: ignore[misc]

    personality = load_personality()
    if personality and verbose:
        _log(f"Perfil cargado: {personality.get('personality', {}).get('style', '—')}")

    node = BusNode(
        "neural_router",
        role="supervisor",
        capabilities=["intent-routing", "tool-dispatch", "personality-enrichment", "llm-fallback"],
    )

    # Track which LLM nodes are registered on the bus
    _llm_node_present: list[bool] = [False]

    @node.on("user.message")
    def handle_user_message(event: dict) -> None:
        text   = event.get("payload", {}).get("text", "").strip()
        origin = event.get("from", "*")
        corr   = event.get("id")  # use event ID as correlation
        platform = event.get("payload", {}).get("platform", "unknown")

        if not text:
            return

        _log(f"{CYAN(origin)} → [{platform}] {BOLD(repr(text[:60]))}")

        # 1. Emit enriched context event
        enriched = enrich_context(event, personality)
        node.emit("user.context", enriched["payload"], correlation_id=corr)

        # 2. Resolve intent and run tools
        intent_result = resolve_intent(text, dry_run=dry_run)

        # 2b. LLM fallback when intent is not recognized and LLM node is online
        if intent_result["intent_id"] in ("no_match", "unknown") and _llm_node_present[0]:
            _log(f"{DIM('→')} Intent no reconocida — consultando LLM node…")
            suggested = _request_llm_tool_suggest(node, text, corr, origin, dry_run)
            if suggested:
                _log(f"{OK('→')} LLM sugiere tools: {', '.join(suggested)}")
                # Execute suggested tools
                results = []
                if not dry_run:
                    for tool_cmd in suggested:
                        _log(f"▶ bago {tool_cmd}")
                        r = run_tool(tool_cmd)
                        results.append(r)
                        icon = OK("✓") if r["ok"] else WARN("⚠")
                        _log(f"{icon} {tool_cmd}  ({r['elapsed']}s)")
                ok_count   = sum(1 for r in results if r["ok"])
                fail_count = len(results) - ok_count
                intent_result = {
                    "intent_id":   "llm_suggested",
                    "intent_name": "LLM Tool Suggestion",
                    "tools":       suggested,
                    "results":     results,
                    "summary":     (
                        f"[dry-run] LLM sugeriría: {' → '.join(suggested)}"
                        if dry_run
                        else f"✅ LLM → {ok_count}/{len(results)} tools OK"
                        if fail_count == 0
                        else f"⚠️ LLM → {fail_count} tool(s) con problemas"
                    ),
                    "ok": fail_count == 0,
                }

        # 3. Emit intent.detected so other nodes can react
        node.emit("intent.detected", {
            "intent_id":   intent_result["intent_id"],
            "intent_name": intent_result["intent_name"],
            "tools":       intent_result["tools"],
            "origin":      origin,
            "platform":    platform,
        }, correlation_id=corr)

        # 4. Emit tool results
        for r in intent_result.get("results", []):
            node.emit("tool.result", {
                "cmd":     r["cmd"],
                "rc":      r["rc"],
                "output":  r["output"][:2000],  # truncate for bus
                "elapsed": r["elapsed"],
                "ok":      r["ok"],
            }, correlation_id=corr)

        # 5. Emit user response (directed back to origin)
        node.emit(
            "user.response",
            {
                "text":     intent_result["summary"],
                "platform": platform,
                "ok":       intent_result["ok"],
                "details":  [
                    {"tool": r["cmd"], "ok": r["ok"], "output": r["output"][:500]}
                    for r in intent_result.get("results", [])
                ],
            },
            to=origin,
            correlation_id=corr,
        )

        _log(f"→ {OK('done') if intent_result['ok'] else WARN('warn')}  {intent_result['summary'][:80]}")

    @node.on("system.node_up")
    def handle_node_up(event: dict) -> None:
        nid  = event.get("payload", {}).get("node_id", "?")
        role = event.get("payload", {}).get("role", "?")
        _log(f"⚡ Nodo conectado: {BOLD(nid)} [{role}]")
        if nid == "llm":
            _llm_node_present[0] = True
            _log(f"{OK('→')} LLM fallback activado")

    @node.on("system.node_down")
    def handle_node_down(event: dict) -> None:
        nid = event.get("payload", {}).get("node_id", "?")
        if nid == "llm":
            _llm_node_present[0] = False
            _log(f"{WARN('⚠')} LLM node desconectado — fallback desactivado")

    @node.on("system.node_stale")
    def handle_node_stale(event: dict) -> None:
        nid = event.get("payload", {}).get("node_id", "?")
        _log(f"{WARN('⚠')} Nodo sin heartbeat: {nid}")

    return node


# ── CLI ────────────────────────────────────────────────────────────────────────

def _self_test() -> int:
    results = []

    # Test 1: run_tool dry-run (bago not needed — uses intentional bad cmd)
    r = run_tool("__no_such_cmd__", timeout=3)
    ok1 = isinstance(r, dict) and "rc" in r and "output" in r and "ok" in r
    results.append(("run_tool_structure", ok1, f"rc={r['rc']}"))

    # Test 2: resolve_intent dry-run
    result = resolve_intent("mi código tiene secretos hardcodeados", dry_run=True)
    ok2 = result["intent_id"] != "" and "[dry-run]" in result["summary"]
    results.append(("resolve_intent_dry_run", ok2, f"intent={result['intent_id']}"))

    # Test 3: resolve_intent no match
    result = resolve_intent("xyz123 nonsense aeiou", dry_run=True)
    ok3 = result["intent_id"] == "no_match"
    results.append(("resolve_intent_no_match", ok3, f"id={result['intent_id']}"))

    # Test 4: load_personality doesn't crash
    profile = load_personality()
    ok4 = isinstance(profile, dict)
    results.append(("load_personality", ok4, f"keys={list(profile.keys())}"))

    # Test 5: enrich_context
    ev = {"payload": {"text": "hola"}, "from": "test"}
    enriched = enrich_context(ev, {"personality": {"style": "directo"}, "language": {"primary": "es"}})
    ok5 = enriched["payload"].get("_user_style") == "directo"
    results.append(("enrich_context", ok5, f"style={enriched['payload'].get('_user_style')}"))

    # Test 6: make_router instantiates without crashing
    try:
        router = make_router(dry_run=True)
        ok6 = router.node_id == "neural_router" and router.role == "supervisor"
    except Exception:
        ok6 = False
    results.append(("make_router", ok6, ""))

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  BAGO Neural Router — Self-tests ({passed}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}  {detail}")
    return 0 if passed == len(results) else 1


def main(argv=None):
    import argparse
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(description="BAGO Neural Router — arco reflejo del ecosistema")
    ap.add_argument("--dry-run",  action="store_true", help="Muestra routing sin ejecutar tools")
    ap.add_argument("--verbose",  action="store_true", help="Output detallado")
    ap.add_argument("--once",     action="store_true", help="Procesa un evento y sale (debug)")
    ap.add_argument("--test",     action="store_true", help="Ejecuta self-tests")
    args = ap.parse_args(argv)

    if args.test:
        return _self_test()

    print("  🧠 BAGO Neural Router")
    print(f"  Modo: {'dry-run' if args.dry_run else 'live'}")
    print("  Conectando al Neural Bus…\n")

    router = make_router(dry_run=args.dry_run, verbose=args.verbose)

    if not router.connect():
        print(f"  {ERR('✗')} No se pudo conectar al Neural Bus.")
        print("  Inicia el bus primero: bago neural serve")
        return 1

    print(f"  {OK('●')} Neural Router activo — escuchando [user.message, system.*]\n")

    if args.once:
        # Wait for one event then exit
        ev = router.wait_for("user.message", timeout=60)
        if ev:
            print(f"  Procesado: {ev.get('payload', {}).get('text', '?')[:60]}")
        else:
            print(f"  {WARN('⚠')} Timeout — no llegaron eventos.")
        router.disconnect()
        return 0

    # Blocking loop
    router.run(block=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
