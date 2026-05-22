#!/usr/bin/env python3
"""bago_neural.py — BAGO Neural Bus v1.0

Bus de mensajes en tiempo real que conecta todos los nodos del ecosistema BAGO.
Transporte puro: no contiene lógica de negocio. Los nodos conectados son
responsables del enrutamiento semántico (ver neural_router.py).

Arquitectura:
  HTTP 127.0.0.1:6789     — API REST local (segura, no expuesta a red)
  SSE  GET /stream        — eventos en tiempo real (Server-Sent Events)
  JSONL state/neural_bus.jsonl — log persistente de eventos durables

Endpoints:
  GET  /              → estado del bus
  GET  /nodes         → nodos registrados
  GET  /events        → eventos recientes (polling)
  GET  /stream        → stream SSE en tiempo real
  GET  /map           → mapa Mermaid del ecosistema
  POST /emit          → publicar evento (requiere X-Bago-Token)
  POST /register      → registrar nodo (requiere X-Bago-Token)
  POST /heartbeat     → keepalive de nodo (requiere X-Bago-Token)

Esquema de evento:
  {
    "id":             "abc12345",           # 8-char UUID prefix
    "ts":             "2026-05-11T01:34Z",  # ISO 8601 UTC
    "from":           "telegram_bot",        # node_id origen
    "to":             "*",                   # node_id destino o "*" (broadcast)
    "topic":          "user.message",        # jerarquía de tópicos
    "payload":        {...},                 # datos del evento
    "correlation_id": "job_xyz",            # opcional: para req/resp
    "reply_to":       "telegram_bot",       # opcional: quién espera la respuesta
    "durable":        true,                 # opcional: persiste en JSONL
    "priority":       1                     # opcional: 0=low 1=normal 2=high
  }

Jerarquía de tópicos:
  user.message       ← entrada de usuario (Telegram, WhatsApp, CLI, Hub)
  user.response      → respuesta al usuario
  user.context       → perfil/vocab enriquecido
  tool.request       → solicitar ejecución de tool
  tool.result        → resultado de tool
  llm.request        → solicitud al LLM local
  llm.response       → respuesta del LLM
  system.node_up     → nodo conectado
  system.node_down   → nodo desconectado
  system.node_stale  → nodo sin heartbeat
  system.bus_up      → bus iniciado
  system.health      → broadcast de salud periódico
  workflow.started   → workflow iniciado
  workflow.step      → paso de workflow
  workflow.completed → workflow completado
  workflow.failed    → workflow fallido

Uso:
  bago neural serve              → inicia el bus (puerto 6789)
  bago neural serve --port 7000  → puerto custom
  bago neural status             → comprueba si el bus está activo
  bago neural nodes              → lista nodos conectados
  bago neural tail               → escucha eventos en tiempo real
  bago neural tail --topic user  → filtra por prefijo de tópico
  bago neural emit user.message '{"text":"hola"}'
  bago neural map                → mapa Mermaid del ecosistema
  bago neural --test             → self-tests
"""
from __future__ import annotations

import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _neural_bus import (
    DEFAULT_BUS_URL,
    DEFAULT_PORT,
    _events_buffer,
    _get_or_create_token,
    _make_event,
    _store_event,
    _topic_matches,
    get_nodes,
    get_recent_events,
    heartbeat_node,
    register_node,
    start_server,
)
from _neural_nodes import (
    DIM,
    ERR,
    OK,
    _load_token,
    cmd_emit,
    cmd_map,
    cmd_nodes,
    cmd_status,
    cmd_tail,
)

# ── Self-tests ─────────────────────────────────────────────────────────────────

def _self_test() -> int:
    """Self-test para Neural Bus.

    Usa un directorio temporal para STATE_DIR — no deja rastro en .bago/state/.
    Compatible con el Contrato §2 (ningún test debe dejar ruido persistente en state).
    """
    import importlib
    import tempfile

    with tempfile.TemporaryDirectory(prefix="bago_neural_test_") as tmpdir:
        # Redirect neural bus state to tmpdir for the duration of the test
        os.environ["BAGO_NEURAL_STATE_DIR"] = tmpdir

        # Force reload of _neural_bus so it picks up the new STATE_DIR
        import sys as _sys
        mods_to_reload = [m for m in _sys.modules if "_neural_bus" in m]
        for m in mods_to_reload:
            del _sys.modules[m]
        # Also reload our own imports from _neural_bus
        try:
            from _neural_bus import (
                _make_event, _topic_matches, _store_event, _events_buffer,
                get_recent_events, register_node, get_nodes, heartbeat_node,
                _get_or_create_token,
            )
        except ImportError:
            print("  ❌ No se pudo importar _neural_bus en modo test")
            return 1

        results = []

        # Test 1: make_event structure
        ev = _make_event("test_node", "test.event", {"key": "val"})
        ok1 = all(k in ev for k in ["id", "ts", "from", "to", "topic", "payload", "durable"])
        results.append(("make_event_structure", ok1, f"keys={list(ev.keys())}"))

        # Test 2: topic_matches
        cases = [
            ("*", "anything", True),
            ("user.*", "user.message", True),
            ("user.*", "tool.result", False),
            ("user.*", "user", True),
            ("system.health", "system.health", True),
            ("system.health", "system.node_up", False),
        ]
        ok2 = all(_topic_matches(p, t) == exp for p, t, exp in cases)
        results.append(("topic_matches", ok2, f"{len(cases)} cases"))

        # Test 3: store_event
        before = len(_events_buffer)
        _store_event(_make_event("test", "test.store", {}, durable=False))
        ok3 = len(_events_buffer) == before + 1
        results.append(("store_event", ok3, f"buffer={len(_events_buffer)}"))

        # Test 4: durable flag auto-set
        ev_durable = _make_event("x", "user.message", {})
        ev_ephemeral = _make_event("x", "system.health", {})
        ok4 = ev_durable["durable"] and not ev_ephemeral["durable"]
        results.append(("durable_auto_flag", ok4, f"user.msg={ev_durable['durable']} sys.health={ev_ephemeral['durable']}"))

        # Test 5: get_recent_events limit
        for i in range(20):
            _store_event(_make_event("test", "test.bulk", {"i": i}, durable=False))
        events = get_recent_events(limit=5)
        ok5 = len(events) <= 5
        results.append(("get_recent_limit", ok5, f"got={len(events)}"))

        # Test 6: register node
        register_node("test_node_abc", {"role": "test", "capabilities": ["testing"]})
        nodes = get_nodes()
        ok6 = "test_node_abc" in nodes and nodes["test_node_abc"]["role"] == "test"
        results.append(("register_node", ok6, f"nodes={len(nodes)}"))

        # Test 7: heartbeat_node
        heartbeat_node("test_node_abc")
        ok7 = get_nodes().get("test_node_abc", {}).get("status") == "active"
        results.append(("heartbeat_node", ok7, ""))

        # Test 8: token file
        token = _get_or_create_token()
        ok8 = isinstance(token, str) and len(token) >= 16
        results.append(("token_generation", ok8, f"len={len(token)}"))

    # tmpdir is cleaned up here — no side effects on .bago/state/
    del os.environ["BAGO_NEURAL_STATE_DIR"]

    passed = sum(1 for _, ok, _ in results if ok)
    failed_list = [n for n, ok, _ in results if not ok]
    print(f"\n  BAGO Neural Bus — Self-tests ({passed}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        icon = OK("✅") if ok else ERR("❌")
        print(f"  {icon}  {name}  {DIM(detail)}")
    if failed_list:
        print(f"\n  Fallidos: {', '.join(failed_list)}")
    return 0 if not failed_list else 1


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(
        description="BAGO Neural Bus — bus de mensajes del ecosistema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--bus", default=DEFAULT_BUS_URL, metavar="URL",
                    help=f"URL del bus (default: {DEFAULT_BUS_URL})")
    ap.add_argument("--token-file", metavar="PATH",
                    help="Archivo con el token de auth (default: state/neural_token.txt)")
    ap.add_argument("--test", action="store_true", help="Ejecuta self-tests")

    sub = ap.add_subparsers(dest="cmd")

    # serve
    p_serve = sub.add_parser("serve", help="Inicia el bus server")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)

    # status
    sub.add_parser("status", help="Estado del bus")

    # nodes
    sub.add_parser("nodes", help="Lista nodos registrados")

    # emit
    p_emit = sub.add_parser("emit", help="Emite un evento al bus")
    p_emit.add_argument("topic", help="Tópico (ej: user.message)")
    p_emit.add_argument("payload", nargs="?", default="{}", help="JSON o texto libre")
    p_emit.add_argument("--from", dest="from_node", default="cli", help="Nodo origen")
    p_emit.add_argument("--to", default="*", help="Nodo destino (* = broadcast)")

    # tail
    p_tail = sub.add_parser("tail", help="Escucha eventos en tiempo real")
    p_tail.add_argument("--topic", default="*", help="Filtro de tópico (ej: user.*)")

    # map
    sub.add_parser("map", help="Mapa Mermaid del ecosistema")

    args = ap.parse_args(argv)

    if args.test:
        return _self_test()

    if not args.cmd:
        # No subcommand — show status if bus is up, else show help
        token = _load_token(getattr(args, "token_file", None))
        rc = cmd_status(args.bus, token)
        if rc != 0:
            ap.print_help()
        return rc

    token = _load_token(getattr(args, "token_file", None))

    if args.cmd == "serve":
        start_server(port=args.port)
        return 0
    elif args.cmd == "status":
        return cmd_status(args.bus, token)
    elif args.cmd == "nodes":
        return cmd_nodes(args.bus, token)
    elif args.cmd == "emit":
        return cmd_emit(args.bus, token, args.topic, args.payload,
                        from_node=args.from_node, to=args.to)
    elif args.cmd == "tail":
        return cmd_tail(args.bus, token, topic_filter=args.topic)
    elif args.cmd == "map":
        return cmd_map(args.bus, token)

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
