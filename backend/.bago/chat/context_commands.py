from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# LEGACY[CHAT-L005]: allow direct file imports to resolve sibling chat modules.
CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

# CANON[CTX-004]: /context is the authoritative inspection and control surface.
# CANON[CTX-005]: each subcommand reports or mutates the live session state only.
# LEGACY[CTX-L001]: parse_args stays as a local helper because this file is loaded directly.
from command_utils import parse_args


def cmd_context(mgr: Any, engine: Any, args: list[str]) -> dict:
    """Inspecciona y gestiona el contexto operativo real."""
    positional, flags = parse_args(args)
    subcmd = (positional[0] if positional else "inspect").lower()

    if subcmd == "inspect":
        data = mgr.inspect_context()
        last_receipt = data.get("last_receipt", {})
        lines = [
            f"Session ID : {data['session_id']}",
            f"Workspace  : {data['workspace_state_root']}",
            f"Repo       : {data['repo_branch'] or data['repo_root'] or '—'}",
            f"Provider   : {data['provider']}",
            f"Model      : {data['model']}",
            f"Binding    : {'OK' if data['binding_confirmed'] else 'FAIL'} — {data['binding_reason']}",
            f"Revision   : {data['context_revision'] or 'sin revisar'}",
            f"Receipt    : {last_receipt.get('envelope_id', '—') or '—'}",
        ]
        return {"ok": True, "message": "\n".join(lines), "data": data}

    if subcmd == "attach":
        paths = positional[1:] if len(positional) > 1 else []
        if hasattr(mgr, "attach_context"):
            data = mgr.attach_context(paths)
            return {"ok": bool(data.get("ok")), "message": data.get("message", "Contexto adjuntado"), "data": data}
        return {"ok": False, "message": "La sesión no expone attach_context()."}

    if subcmd == "measure":
        data = mgr.measure_context()
        budget = data.get("budget", {})
        lines = [
            f"Workspace  : {data['workspace_state_root']}",
            f"Provider   : {data['provider']}",
            f"Model      : {data['model']}",
            f"Tokens ctx : {data['model_context_tokens']}",
            f"Disponibles: {budget.get('available_tokens', 0)}",
            f"Uso        : {round(float(budget.get('usage_fraction', 0.0) or 0.0) * 100)}%",
        ]
        return {"ok": True, "message": "\n".join(lines), "data": data}

    if subcmd == "benchmark":
        iterations = 3
        if len(positional) > 1:
            try:
                iterations = max(1, int(positional[1]))
            except ValueError:
                pass
        data = mgr.benchmark_context(iterations=iterations)
        if bool(flags.get("cognitive")):
            data["cognitive"] = mgr.benchmark_cognitive(iterations=iterations)
        return {
            "ok": True,
            "message": f"Benchmark ejecutado: {data['iterations']} iteraciones, avg={data['elapsed_ms']['avg']} ms",
            "data": data,
        }

    if subcmd == "certify":
        data = mgr.certify_context()
        status = data.get("status", "NO_CERTIFIED")
        return {
            "ok": bool(data.get("ok")),
            "message": f"Estado: {status}\nFallos: {len(data.get('failures', []))}",
            "data": data,
        }

    if subcmd == "history":
        limit = 10
        if len(positional) > 1:
            try:
                limit = max(1, int(positional[1]))
            except ValueError:
                pass
        data = mgr.context_history(limit=limit)
        return {
            "ok": True,
            "message": f"Historial de contexto: {len(data.get('history', []))} mensajes, {len(data.get('timeline', []))} eventos",
            "data": data,
        }

    if subcmd == "invalidate":
        if not bool(flags.get("confirm")):
            return {"ok": False, "message": "Uso: /context invalidate --confirm"}
        reason = str(flags.get("reason") or "")
        data = mgr.invalidate_context(reason=reason)
        return {
            "ok": True,
            "message": f"Contexto invalidado: {data.get('previous_context_revision') or '—'}",
            "data": data,
        }

    if subcmd == "calibrate":
        iterations = 3
        if len(positional) > 1:
            try:
                iterations = max(1, int(positional[1]))
            except ValueError:
                pass
        data = mgr.calibrate_context(iterations=iterations)
        return {
            "ok": True,
            "message": f"Contexto recalibrado: {data['benchmark']['iterations']} iteraciones",
            "data": data,
        }

    if subcmd == "tune":
        if not bool(flags.get("confirm")):
            return {"ok": False, "message": "Uso: /context tune --confirm"}
        data = mgr.tune_context(authorized=True, patch={"requested": True, "flags": flags, "args": positional[1:]})
        return {"ok": bool(data.get("ok")), "message": data.get("message", "tune procesado"), "data": data}

    return {
        "ok": False,
        "message": "Uso: /context [inspect|attach|measure|benchmark|certify|history|invalidate|calibrate|tune]",
    }
