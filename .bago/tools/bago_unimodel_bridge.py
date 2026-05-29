#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
bago_unimodel_bridge.py — Puente persistente de chat unimodel para BAGO Dev Twin.

Lee líneas de stdin, envía a chat_bridge(), imprime respuesta a stdout.
Mantiene historial en JSON para sobrevivir cambios de modelo y reinicios.

Uso:
    python bago_unimodel_bridge.py --provider copilot --model gpt-5.4 \
        --history-file %LOCALAPPDATA%\BAGO\unimodel_history.json

Comandos especiales (stdin):
    SWITCH:<provider>:<model>  → cambia de modelo conservando historial
    CLEAR                      → borra historial de la sesión
    EXIT                       → termina el puente
    HELP                       → lista todos los comandos
    STATUS                     → estado de la sesión (provider, modelo, tokens...)
    TIMELINE  (alias: TL)      → muestra línea de tiempo de eventos
    SAVE                       → guarda sesión completa a disco
    COMPACT                    → compacta historial conservando contexto
    MODELS                     → lista modelos disponibles
    NEW[:<tipo>]               → inicia wizard de creación (devuelve instrucciones)
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import datetime
import json
import os
import sys
import threading


# Ensure bago package is importable when running from .bago/tools/
_BAGO_TOOLS = os.path.dirname(os.path.abspath(__file__))
if _BAGO_TOOLS not in sys.path:
    sys.path.insert(0, _BAGO_TOOLS)

from bago import CredentialManager
from bago.api.bridge import chat_bridge
from bago.menus.config import _load_config
from bago.providers import get_default_model, load_providers, _normalize_provider_name
from bago.session import BagoSession
from timeline_db import TimelineDB


def _load_session_data(path: str) -> dict:
    """Carga datos persistidos del puente (history, timeline, metadata)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"messages": data}
    except Exception:
        pass
    return {}


def _save_session_data(path: str, data: dict):
    """Guarda datos completos del puente (history, timeline, metadata)."""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _create_session(provider: str, model: str | None = None) -> BagoSession:
    creds = CredentialManager()
    providers = load_providers()
    prov = _normalize_provider_name(provider)

    if model:
        name = model
        wire = model
        prov_data = providers.get(prov, {})
        model_data = prov_data.get("models", {}).get(model, {})
        if model_data:
            wire = model_data.get("wire_name", model)
    else:
        name, wire, prov = get_default_model(prov, providers)
        if not name:
            name = "sin-modelo"
            wire = "sin-modelo"

    cfg = _load_config()
    session = BagoSession(prov, name, wire, creds, single_model=cfg.get("single_model", False))
    session.autoroute = cfg.get("autoroute", True)
    session.autonomous = cfg.get("autonomous", False)
    session.orch_mode = cfg.get("orch_mode", "standard")
    return session


def _session_to_dict(session: BagoSession) -> dict:
    """Serializa la sesión completa para persistencia."""
    return {
        "provider": session.provider,
        "model_name": session.model_name,
        "wire_name": session.wire_name,
        "started_at": session.started_at.isoformat(),
        "switches": session.switches,
        "messages": session.history,
        "timeline": session.timeline,
        "token_log": session.token_log,
        "last_route": session.last_route,
    }


def _restore_session_dict(session: BagoSession, data: dict):
    """Restaura partes de la sesión desde dict persistido."""
    # Restore history (keep current system message)
    persisted_msgs = data.get("messages", [])
    if persisted_msgs:
        system_msg = session.history[0] if session.history else {"role": "system", "content": ""}
        session.history = [system_msg]
        for msg in persisted_msgs:
            if msg.get("role") != "system":
                session.history.append(msg)
    # Restore timeline
    persisted_tl = data.get("timeline", [])
    if persisted_tl:
        session.timeline = persisted_tl
        # Keep timeline capped
        if len(session.timeline) > 120:
            session.timeline = session.timeline[-120:]
    # Restore token log
    persisted_tokens = data.get("token_log", {})
    if persisted_tokens:
        session.token_log = persisted_tokens
    # Restore switches count
    session.switches = data.get("switches", 0)
    # Restore last route if present
    persisted_route = data.get("last_route", {})
    if persisted_route:
        session.last_route = persisted_route


def _compact_history(session: BagoSession, keep_last: int = 10) -> int:
    """Compacta el historial conservando system + últimos N mensajes.
    Devuelve número de mensajes eliminados."""
    system_msg = session.history[0] if session.history else {"role": "system", "content": ""}
    before = len(session.history)
    kept = session.history[-keep_last:] if len(session.history) > keep_last else session.history[1:]
    session.history = [system_msg] + kept
    removed = before - len(session.history)
    return removed


def _format_status(session: BagoSession) -> str:
    """Devuelve estado formateado de la sesión."""
    lines = [
        "═ Estado de sesión unimodel ═",
        f"  Provider : {session.provider}",
        f"  Modelo   : {session.model_name}",
        f"  Wire     : {session.wire_name}",
        f"  Mensajes : {len(session.history) - 1}",
        f"  Timeline : {len(session.timeline)} eventos",
        f"  Switches : {session.switches}",
        f"  Inicio   : {session.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if session.token_log:
        lines.append("  Tokens   :")
        for prov, models in session.token_log.items():
            for mdl, t in models.items():
                lines.append(f"    {prov}/{mdl}  ↑{t['in']} in  ↓{t['out']} out  ×{t['calls']} calls")
    else:
        lines.append("  Tokens   : (sin llamadas)")
    route = session.last_route or {}
    if route.get("reason"):
        lines.append(f"  Ruta     : {route.get('mode','?')} → {route.get('provider','?')}/{route.get('model','?')} | {route.get('reason','')}")
    return "\n".join(lines)


def _format_models(session: BagoSession) -> str:
    """Lista modelos disponibles formateados."""
    active = session.creds.active_bago_providers()
    from bago.providers import _available_model_items
    lines = ["═ Modelos disponibles ═"]
    for pn, pd in session.providers.items():
        avail = "✓" if pn in active else "○"
        lines.append(f"\n[{avail}] [{pn}]")
        for mn, md in _available_model_items(pn, pd):
            act = " ← ACTIVO" if mn == session.model_name else ""
            lines.append(f"    {mn:<30} {md.get('best_for',''):<25} {md.get('cost','')}{act}")
    if not session.providers:
        lines.append("  (ningún provider cargado)")
    return "\n".join(lines)


def _format_timeline(session: BagoSession, limit: int = 20) -> str:
    """Devuelve timeline formateado."""
    rows = session.timeline_view(limit=limit, width=80)
    header = f"═ Timeline (últimos {len(rows)} eventos) ═"
    return header + "\n" + "\n".join(rows)


def _print_help() -> str:
    return (
        "═ Comandos del puente unimodel ═\n"
        "  SWITCH:<p>:<m>  Cambia de modelo conservando historial\n"
        "  CLEAR           Borra historial de mensajes\n"
        "  SAVE            Guarda sesión completa a disco\n"
        "  COMPACT         Reduce historial a los últimos 10 mensajes\n"
        "  STATUS          Muestra estado de provider, modelo, tokens...\n"
        "  TIMELINE / TL   Muestra línea de tiempo de eventos\n"
        "  MODELS          Lista modelos disponibles\n"
        "  NEW[:tipo]      Inicia wizard de creación (devuelve cómo)\n"
        "  DB-STATUS       Estado de la base de datos de timelines\n"
        "  DB-LIST         Lista sesiones almacenadas en la DB\n"
        "  DB-COMPACT      Reduce eventos de la sesión a los últimos 50\n"
        "  DB-CLEAR        Borra eventos de la sesión de la DB\n"
        "  DB-EXPORT:path  Exporta sesión a JSON\n"
        "  HELP            Muestra esta ayuda\n"
        "  EXIT            Cierra el puente"
    )


def main():
    parser = argparse.ArgumentParser(description="BAGO Unimodel Bridge")
    parser.add_argument("--provider", default="copilot", help="Provider alias (copilot, codex, claude, ollama, local)")
    parser.add_argument("--model", default="", help="Model name (optional)")
    parser.add_argument("--history-file", default="", help="JSON file path to persist conversation history")
    parser.add_argument("--timeline-db", default="", help="SQLite DB path for timeline (default: %LOCALAPPDATA%\\BAGO\\timeline.db)")
    args = parser.parse_args()

    session = _create_session(args.provider, args.model or None)
    history_file = args.history_file or ""

    # ── TimelineDB init ─────────────────────────────────────────────────────
    tdb = TimelineDB(db_path=args.timeline_db or None)
    db_sid = tdb.create_session(
        name="unimodel-bridge",
        provider=session.provider,
        model=session.model_name,
    )

    def _db_log(kind: str, title: str, detail: str = "", level: str = "info"):
        try:
            tdb.log_event(db_sid, kind, title, detail, level)
        except Exception:
            pass

    # Load persisted session data
    data = _load_session_data(history_file)
    if data:
        _restore_session_dict(session, data)
        msg_count = len(session.history) - 1
        tl_count = len(session.timeline)
        print(f"[bridge] Sesión restaurada: {msg_count} mensajes, {tl_count} eventos", flush=True)
        _db_log("bridge", "restore", f"{msg_count} msgs, {tl_count} events", level="info")
    else:
        print("[bridge] Sesión nueva iniciada", flush=True)
        _db_log("bridge", "start", f"{session.provider}/{session.model_name}", level="info")

    print(f"[bridge] Provider: {session.provider} | Modelo: {session.model_name}", flush=True)
    print("[bridge] Escribe HELP para ver comandos disponibles.", flush=True)

    _lock = threading.Lock()

    def _persist():
        """Guarda estado completo tras cada interacción."""
        if history_file:
            _save_session_data(history_file, _session_to_dict(session))

    for line in sys.stdin:
        line = line.rstrip("\n\r")
        if not line:
            continue

        cmd = line.upper()

        if cmd == "EXIT":
            with _lock:
                session.add_timeline("bridge", "exit", "Puente cerrado por usuario", level="info")
            _db_log("bridge", "exit", "Puente cerrado por usuario", level="info")
            tdb.close_session(db_sid)
            tdb.close()
            _persist()
            print("[bridge] Cerrando puente...", flush=True)
            break

        if cmd == "HELP":
            print(_print_help(), flush=True)
            continue

        if cmd == "STATUS":
            print(_format_status(session), flush=True)
            continue

        if cmd in ("TIMELINE", "TL"):
            print(_format_timeline(session), flush=True)
            continue

        if cmd == "SAVE":
            with _lock:
                path = session.save()
                session.add_timeline("bridge", "save", f"Guardado en {path}", level="info")
            _db_log("bridge", "save", f"Guardado en {path}", level="info")
            print(f"[bridge] Guardado: {path}", flush=True)
            _persist()
            continue

        if cmd == "CLEAR":
            with _lock:
                system_msg = session.history[0] if session.history else {"role": "system", "content": ""}
                session.history = [system_msg]
                session.add_timeline("bridge", "clear", "Historial limpiado", level="info")
            _db_log("bridge", "clear", "Historial limpiado", level="info")
            print("[bridge] Historial borrado.", flush=True)
            _persist()
            continue

        if cmd == "COMPACT":
            with _lock:
                removed = _compact_history(session, keep_last=10)
                session.add_timeline("bridge", "compact", f"Eliminados {removed} mensajes", level="info")
            _db_log("bridge", "compact", f"Eliminados {removed} mensajes", level="info")
            print(f"[bridge] Compactado: {removed} mensajes eliminados. Quedan {len(session.history)-1}.", flush=True)
            _persist()
            continue

        if cmd == "MODELS":
            print(_format_models(session), flush=True)
            continue

        if cmd.startswith("NEW"):
            sub = line.split(":", 1)[1].strip() if ":" in line else ""
            if sub:
                print(f"[bridge] Para crear un artefacto tipo '{sub}', ejecuta en el panel derecho:", flush=True)
                print(f"[bridge]   bago new --type {sub}", flush=True)
                print(f"[bridge] O usa el menú: bago menu → Crear artefacto", flush=True)
            else:
                print("[bridge] Para crear un artefacto, ejecuta en el panel derecho:", flush=True)
                print("[bridge]   bago new   o   bago menu → Crear artefacto", flush=True)
            with _lock:
                session.add_timeline("bridge", "new", f"Solicitud wizard tipo={sub or 'default'}", level="info")
            _db_log("bridge", "new", f"tipo={sub or 'default'}", level="info")
            continue

        # ── Timeline DB commands ──────────────────────────────────────────────
        if cmd == "DB-STATUS":
            stats = tdb.stats()
            db_sess = tdb.get_session(db_sid)
            evt_count = tdb.event_count(db_sid)
            lines = [
                "═ TimelineDB ═",
                f"  DB path   : {stats['db_path']}",
                f"  DB size   : {stats['db_size']} bytes",
                f"  Sesiones  : {stats['sessions']}",
                f"  Eventos   : {stats['events']}",
                f"  Session ID: {db_sid}",
                f"  Provider  : {db_sess.get('provider','') if db_sess else ''}",
                f"  Modelo    : {db_sess.get('model','') if db_sess else ''}",
                f"  Eventos local: {evt_count}",
            ]
            print("\n".join(lines), flush=True)
            continue

        if cmd == "DB-LIST":
            sessions = tdb.list_sessions(limit=20)
            lines = ["═ Sesiones en TimelineDB ═"]
            for s in sessions:
                ended = s.get("ended_at") or "(activa)"
                lines.append(f"  {s['id']} | {s['name']} | {s['provider']}/{s['model']} | {s['created_at']} | {ended}")
            if not sessions:
                lines.append("  (ninguna sesión)")
            print("\n".join(lines), flush=True)
            continue

        if cmd == "DB-COMPACT":
            removed = tdb.compact_session(db_sid, keep_last=50)
            print(f"[bridge] DB compactada: {removed} eventos antiguos eliminados.", flush=True)
            continue

        if cmd == "DB-CLEAR":
            tdb.clear_session_events(db_sid)
            print("[bridge] Eventos de sesión borrados de TimelineDB.", flush=True)
            continue

        if cmd.startswith("DB-EXPORT:"):
            path = line.split(":", 1)[1].strip()
            try:
                out = tdb.export_session(db_sid, path)
                print(f"[bridge] Exportado a: {out}", flush=True)
            except Exception as exc:
                print(f"[bridge] Error exportando: {exc}", flush=True)
            continue

        if line.startswith("SWITCH:"):
            parts = line.split(":")
            if len(parts) >= 3:
                new_prov = parts[1]
                new_model = parts[2]
                old_name = session.model_name
                old_hist = list(session.history)
                try:
                    with _lock:
                        session = _create_session(new_prov, new_model or None)
                        session.history = old_hist
                        session.timeline = []
                        session.token_log = {}
                        session.switches = 0
                        session.add_timeline("bridge", "switch", f"{old_name} → {session.model_name}", level="info")
                    _db_log("bridge", "switch", f"{old_name} → {session.model_name}", level="info")
                    print(f"[bridge] Cambiado a {session.provider}/{session.model_name}", flush=True)
                except Exception as exc:
                    _db_log("bridge", "error", f"switch failed: {exc}", level="error")
                    print(f"[bridge] Error al cambiar modelo: {exc}", flush=True)
            else:
                print("[bridge] Uso: SWITCH:<provider>:<modelo>", flush=True)
            _persist()
            continue

        # Normal chat message
        try:
            with _lock:
                response = chat_bridge(session, line, history_input=line)
        except Exception as exc:
            with _lock:
                session.add_timeline("bridge", "error", f"{type(exc).__name__}: {exc}"[:160], level="error")
            _db_log("bridge", "error", f"{type(exc).__name__}: {exc}"[:160], level="error")
            print(f"[bridge] ERROR: {exc}", flush=True)
            _persist()
            continue

        if response:
            print(response, flush=True)
        else:
            print("[bridge] (sin respuesta)", flush=True)

        with _lock:
            session.add_timeline("bridge", "chat", f"user: {line[:80]}...", level="user")
            if response:
                session.add_timeline("bridge", "reply", f"assistant: {response[:80]}...", level="assistant")
        _db_log("chat", "user", line[:120], level="user")
        if response:
            _db_log("chat", "assistant", response[:120], level="assistant")

        _persist()

    print("[bridge] Terminado.", flush=True)


if __name__ == "__main__":
    main()
