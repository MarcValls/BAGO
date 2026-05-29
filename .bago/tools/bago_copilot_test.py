#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_copilot_test.py — Herramienta de prueba BAGO desde terminal.

Ejecuta el orquestador directamente desde línea de comandos, sin necesidad
de abrir otra ventana. Usa el puente chat_bridge (API o directo) que ya
existe en BAGO.

Uso:
    python .bago/tools/bago_copilot_test.py "mensaje"                    # un solo mensaje
    python .bago/tools/bago_copilot_test.py -i                           # modo interactivo
    python .bago/tools/bago_copilot_test.py -p ollama-local -m llama3.2:3b "hola"
    python .bago/tools/bago_copilot_test.py --test                       # self-test
    python .bago/tools/bago_copilot_test.py --status                     # estado de sesión
    python .bago/tools/bago_copilot_test.py --quality "pregunta" "respuesta"  # test calidad
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

# ── Ensure bago package importable ──────────────────────────────────────────
_BAGO_TOOLS = os.path.dirname(os.path.abspath(__file__))
if _BAGO_TOOLS not in sys.path:
    sys.path.insert(0, _BAGO_TOOLS)

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from bago import CredentialManager, load_providers, load_routing, BagoSession
from bago.providers import get_default_model, auto_detect_provider
from bago.api.bridge import chat_bridge, detect_mode, set_mode
from bago.menus.config import _load_config


# ── Colores ANSI ────────────────────────────────────────────────────────────
class _C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"
    BG_DARK = "\033[48;5;236m"


def _create_session(provider: str = "", model: str = "") -> BagoSession:
    """Crea una sesión BAGO lista para chatear."""
    creds = CredentialManager()
    providers = load_providers()

    cfg = _load_config()

    if model:
        name, wire, prov = model, model, provider or "ollama-local"
        prov_data = providers.get(prov, {})
        model_data = prov_data.get("models", {}).get(model, {})
        if model_data:
            wire = model_data.get("wire_name", model)
    elif provider:
        name, wire, prov = get_default_model(provider, providers)
    else:
        pm = {
            "copilot": "copilot", "codex": "codex",
            "ollama": "ollama-local", "ollama-local": "ollama-local",
            "ollama-cloud": "ollama-cloud", "anthropic": "anthropic",
            "local": "ollama-local", "github-models": "github-models",
        }
        chosen = auto_detect_provider(creds, providers)
        name, wire, prov = get_default_model(chosen, providers)

    if not name:
        name, wire, prov = "sin-modelo", "sin-modelo", "none"

    session = BagoSession(prov, name, wire, creds,
                          single_model=cfg.get("single_model", False))
    session.autoroute = cfg.get("autoroute", True)
    session.autonomous = cfg.get("autonomous", False)
    session.orch_mode = cfg.get("orch_mode", "standard")
    return session


def _print_banner(session: BagoSession):
    """Muestra el banner de sesión."""
    mode = detect_mode()
    print(f"\n{_C.BG_DARK}{_C.BOLD}{_C.CYAN}  ◆ BAGO Test Bridge {_C.RESET}")
    print(f"  {_C.DIM}Proveedor: {session.provider}/{session.model_name}")
    print(f"  Modo bridge: {mode}")
    print(f"  Autoroute: {'ON' if session.autoroute else 'OFF'}")
    print(f"  Modo orquestación: {session.orch_mode}{_C.RESET}")
    print(f"  {_C.DIM}Escribe un mensaje o 'help' para comandos.{_C.RESET}\n")


def _print_status(session: BagoSession):
    """Muestra estado detallado de la sesión."""
    route = session.last_route or {}
    print(f"\n{_C.BOLD}══ Estado de sesión ══{_C.RESET}")
    print(f"  Provider  : {session.provider}")
    print(f"  Modelo    : {session.model_name}")
    print(f"  Wire      : {session.wire_name}")
    print(f"  Bridge    : {detect_mode()}")
    print(f"  Autoroute : {'ON' if session.autoroute else 'OFF'}")
    print(f"  Orch mode : {session.orch_mode}")
    print(f"  Mensajes  : {len(session.history)}")
    print(f"  Switches  : {session.switches}")
    print(f"  Última ruta: {route.get('reason', '(ninguna)')}")
    if session.token_log:
        print(f"  {_C.DIM}Tokens:{_C.RESET}")
        for prov, models in session.token_log.items():
            for mdl, t in models.items():
                print(f"    {prov}/{mdl}  ↑{t['in']}  ↓{t['out']}  ×{t['calls']}")
    else:
        print(f"  Tokens: (sin llamadas)")
    active = session.creds.active_bago_providers()
    print(f"  Providers activos: {', '.join(active) if active else 'ninguno'}")
    print()


def _print_help():
    """Muestra comandos disponibles."""
    print(f"""
{_C.BOLD}══ Comandos del Test Bridge ══{_C.RESET}
  {_C.CYAN}help{_C.RESET}              Muestra esta ayuda
  {_C.CYAN}status{_C.RESET}            Estado de sesión
  {_C.CYAN}models{_C.RESET}            Lista modelos disponibles
  {_C.CYAN}switch <p> <m>{_C.RESET}    Cambia de provider/modelo
  {_C.CYAN}route <msg>{_C.RESET}       Preview del routing sin llamar
  {_C.CYAN}quality <q> <r>{_C.RESET}   Test de calidad (garbage detection)
  {_C.CYAN}clear{_C.RESET}             Borra historial
  {_C.CYAN}compact{_C.RESET}           Compacta historial (últimos 10)
  {_C.CYAN}save{_C.RESET}              Guarda sesión a disco
  {_C.CYAN}mode <modo>{_C.RESET}       Cambia modo bridge (api/direct/hybrid)
  {_C.CYAN}exit / quit{_C.RESET}       Cierra el bridge
  {_C.DIM}Cualquier otro texto se envía como mensaje al modelo.{_C.RESET}
""")


def _cmd_models(session: BagoSession):
    """Lista modelos disponibles."""
    from bago.providers import _available_model_items
    active = session.creds.active_bago_providers()
    print(f"\n{_C.BOLD}══ Modelos disponibles ══{_C.RESET}")
    for pn, pd in session.providers.items():
        avail = "✓" if pn in active else "○"
        marker = f" {_C.GREEN}← ACTIVO{_C.RESET}" if pn == session.provider else ""
        print(f"  [{avail}] {pn}{marker}")
        for mn, md in _available_model_items(pn, pd):
            print(f"      {mn:<30} {md.get('best_for', ''):<25} {md.get('cost', '')}")
    print()


def _cmd_route(session: BagoSession, msg: str):
    """Preview del routing."""
    from bago.api.bridge import api_route
    mode = detect_mode()
    if mode == "api":
        try:
            result = api_route(msg)
            print(f"\n  {_C.BOLD}Routing preview (API):{_C.RESET}")
            for k, v in result.items():
                print(f"    {k}: {v}")
            print()
        except Exception as exc:
            print(f"\n  {_C.RED}Error: {exc}{_C.RESET}\n")
    else:
        from bago.providers import route_by_task
        routing = load_routing()
        name, wire, prov, reason = route_by_task(msg, routing, session.providers)
        print(f"\n  {_C.BOLD}Routing preview (local):{_C.RESET}")
        print(f"    Modelo: {name}")
        print(f"    Provider: {prov}")
        print(f"    Razón: {reason}")
        print()


def _cmd_quality_check(question: str, response: str):
    """Test de quality guard."""
    from bago.llm.quality import _response_is_garbage, _EVASION_PATTERNS, _CLARIFICATION_PATTERNS
    from bago.llm.orchestrator import _looks_like_helpful_clarification

    is_g, reason = _response_is_garbage(question, response)
    is_clarif = _looks_like_helpful_clarification(response)

    print(f"\n{_C.BOLD}══ Quality Guard Test ══{_C.RESET}")
    print(f"  Pregunta:   {question!r}")
    print(f"  Respuesta:  {response!r}")
    print(f"  Basura:     {_C.RED if is_g else _C.GREEN}{is_g}{_C.RESET}")
    print(f"  Razón:      {reason or '(ninguna)'}")
    print(f"  Aclaración: {_C.GREEN if is_clarif else _C.DIM}{is_clarif}{_C.RESET}")
    print(f"  Patrones evasion: {len(_EVASION_PATTERNS)}")
    print(f"  Patrones clarif:  {len(_CLARIFICATION_PATTERNS)}")
    print()


def _cmd_switch(session: BagoSession, args: list[str]):
    """Cambia de provider/modelo."""
    if len(args) < 1:
        print(f"  {_C.YELLOW}Uso: switch <provider> [modelo]{_C.RESET}")
        return session
    prov = args[0]
    model = args[1] if len(args) > 1 else ""
    old_prov, old_model = session.provider, session.model_name
    name, wire, prov = get_default_model(prov, session.providers) if not model else (model, model, prov)
    session.provider = prov or prov
    session.model_name = name or model
    session.wire_name = wire or model
    source = session._update_model_origin(session.provider, session.model_name, session.wire_name)
    print(f"  {_C.GREEN}Cambiado: {old_prov}/{old_model} → {session.provider}/{session.model_name}{_C.RESET}")
    return session


def _interactive(session: BagoSession):
    """Modo interactivo."""
    _print_banner(session)

    while True:
        try:
            line = input(f"{_C.CYAN}bago>{_C.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {_C.DIM}Bridge cerrado.{_C.RESET}")
            break

        if not line:
            continue

        cmd = line.lower().strip()

        if cmd in ("exit", "quit"):
            print(f"  {_C.DIM}Bridge cerrado.{_C.RESET}")
            break

        if cmd == "help":
            _print_help()
            continue

        if cmd == "status":
            _print_status(session)
            continue

        if cmd == "models":
            _cmd_models(session)
            continue

        if cmd == "clear":
            system_msg = session.history[0] if session.history else {"role": "system", "content": ""}
            session.history = [system_msg]
            print(f"  {_C.GREEN}Historial borrado.{_C.RESET}")
            continue

        if cmd == "compact":
            system_msg = session.history[0] if session.history else {"role": "system", "content": ""}
            kept = session.history[-10:] if len(session.history) > 10 else session.history[1:]
            removed = len(session.history) - 1 - len(kept)
            session.history = [system_msg] + kept
            print(f"  {_C.GREEN}Compactado: {removed} mensajes eliminados.{_C.RESET}")
            continue

        if cmd == "save":
            path = session.save()
            print(f"  {_C.GREEN}Guardado: {path}{_C.RESET}")
            continue

        if cmd.startswith("switch "):
            parts = line.split()[1:]
            _cmd_switch(session, parts)
            continue

        if cmd.startswith("route "):
            _cmd_route(session, line[6:])
            continue

        if cmd.startswith("quality "):
            # quality "pregunta" "respuesta"
            parts = line[8:].strip()
            if parts.startswith('"'):
                import re as _re
                m = _re.findall(r'"([^"]*)"', parts)
                if len(m) >= 2:
                    _cmd_quality_check(m[0], m[1])
                else:
                    print(f"  {_C.YELLOW}Uso: quality \"pregunta\" \"respuesta\"{_C.RESET}")
            else:
                print(f"  {_C.YELLOW}Uso: quality \"pregunta\" \"respuesta\"{_C.RESET}")
            continue

        if cmd.startswith("mode "):
            mode = line[5:].strip().lower()
            if mode in ("api", "direct", "hybrid"):
                set_mode(mode)
                print(f"  {_C.GREEN}Bridge modo: {mode}{_C.RESET}")
            else:
                print(f"  {_C.YELLOW}Modos: api, direct, hybrid{_C.RESET}")
            continue

        # ── Enviar mensaje al orquestador ──────────────────────────────────
        t0 = time.perf_counter()
        try:
            response = chat_bridge(session, line, history_input=line)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"  {_C.RED}ERROR ({elapsed:.1f}s): {exc}{_C.RESET}")
            traceback.print_exc()
            continue

        elapsed = time.perf_counter() - t0
        route = session.last_route or {}

        if response:
            print(f"\n{response}")
            print(f"  {_C.DIM}─── {session.provider}/{session.model_name} │ "
                  f"{elapsed:.1f}s │ {route.get('reason', '')} ───{_C.RESET}\n")
        else:
            print(f"  {_C.DIM}(sin respuesta, {elapsed:.1f}s){_C.RESET}\n")


def _single_message(session: BagoSession, message: str, verbose: bool = False):
    """Envía un solo mensaje y muestra la respuesta."""
    t0 = time.perf_counter()
    try:
        response = chat_bridge(session, message, history_input=message)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"ERROR ({elapsed:.1f}s): {exc}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return None

    elapsed = time.perf_counter() - t0
    route = session.last_route or {}

    if verbose:
        print(f"Provider: {session.provider}")
        print(f"Model:    {session.model_name}")
        print(f"Mode:     {detect_mode()}")
        print(f"Route:    {route.get('reason', '(none)')}")
        print(f"Switches: {session.switches}")
        print(f"Time:     {elapsed:.1f}s")
        print("---")

    if response:
        print(response)
    else:
        print("(sin respuesta)")

    return response


def _run_tests() -> int:
    """Self-test: verifica imports y quality guard."""
    results = []

    # Import test
    try:
        from bago.llm.orchestrator import chat, _looks_like_helpful_clarification
        from bago.llm.quality import _response_is_garbage
        from bago.api.bridge import chat_bridge
        results.append(("imports", True, "all modules import OK"))
    except Exception as e:
        results.append(("imports", False, str(e)))

    # Quality guard tests
    try:
        from bago.llm.quality import _response_is_garbage
        from bago.llm.orchestrator import _looks_like_helpful_clarification

        tests_ok = True
        tests = [
            ("busca config", "Te refieres a los archivos de configuracion?", False),
            ("como configuro el entorno de desarrollo", "Como puedo ayudarte hoy?", True),
            ("cambia el color", "Si quieres cambiar el color, edita config.json", False),
        ]
        for q, r, expected in tests:
            is_g, reason = _response_is_garbage(q, r)
            if is_g != expected:
                tests_ok = False
                results.append(("quality", False, f"FAIL: {q!r} → garbage={is_g}, expected={expected}"))
                break

        if tests_ok:
            results.append(("quality", True, "quality guard patterns correct"))
    except Exception as e:
        results.append(("quality", False, str(e)))

    # Spiral structure test
    try:
        import inspect
        from bago.llm.orchestrator import chat
        src = inspect.getsource(chat)
        returns = [l for l in src.split('\n') if 'return ' in l and not l.strip().startswith('#') and not l.strip().startswith('"""')]
        # chat() should have 1 return (the final one)
        actual_returns = [l for l in returns if 'result' in l]
        if len(actual_returns) <= 1:
            results.append(("spiral", True, f"chat() has {len(actual_returns)} exit point(s)"))
        else:
            results.append(("spiral", False, f"chat() has {len(actual_returns)} exit points, expected 1"))
    except Exception as e:
        results.append(("spiral", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = f"{_C.GREEN}OK{_C.RESET}" if ok else f"{_C.RED}FAIL{_C.RESET}"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1


def main():
    parser = argparse.ArgumentParser(
        description="BAGO Test Bridge — prueba el orquestador desde terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("message", nargs="*", help="Mensaje a enviar (modo no interactivo)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Modo interactivo")
    parser.add_argument("-p", "--provider", default="", help="Provider (ollama-local, copilot, codex, etc.)")
    parser.add_argument("-m", "--model", default="", help="Modelo específico")
    parser.add_argument("--mode", default="", choices=["api", "direct", "hybrid"], help="Modo del bridge")
    parser.add_argument("-v", "--verbose", action="store_true", help="Salida detallada")
    parser.add_argument("--test", action="store_true", help="Ejecutar self-tests")
    parser.add_argument("--status", action="store_true", help="Mostrar estado de sesión")
    parser.add_argument("--quality", nargs=2, metavar=("QUESTION", "RESPONSE"), help="Test de quality guard")

    args = parser.parse_args()

    if args.test:
        raise SystemExit(_run_tests())

    # Configurar modo bridge
    if args.mode:
        set_mode(args.mode)

    # Crear sesión
    session = _create_session(provider=args.provider, model=args.model)

    if args.status:
        _print_status(session)
        return

    if args.quality:
        _cmd_quality_check(args.quality[0], args.quality[1])
        return

    if args.interactive:
        _interactive(session)
        return

    if args.message:
        message = " ".join(args.message)
        _single_message(session, message, verbose=args.verbose)
        return

    # Sin argumentos → interactivo
    _interactive(session)


if __name__ == "__main__":
    main()