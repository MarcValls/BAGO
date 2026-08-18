from __future__ import annotations

from typing import Any


def _normalize_tool_approval_mode(mode: str | None) -> str:
    raw = " ".join(str(mode or "").strip().split()).lower().replace("-", "_")
    if raw in {"always", "auto", "permitir", "permitir_siempre", "siempre", "yes", "true", "1"}:
        return "always"
    if raw in {"ask", "prompt", "preguntar", "preguntar_siempre", "question", "maybe", "no", "false", "0"}:
        return "ask"
    return ""


def current_tool_approval_policy(mgr: Any) -> str:
    getter = getattr(mgr, "tool_approval_policy", None)
    if callable(getter):
        try:
            policy = str(getter() or "").strip().lower()
            if policy in {"ask", "always"}:
                return policy
        except Exception:
            pass
    return _normalize_tool_approval_mode(mgr.config.get("features.tool_approval_policy", "")) or (
        "always" if bool(mgr.config.get("features.auto_allow_tools", False)) else "ask"
    )


def set_tool_approval_policy(mgr: Any, mode: str) -> str:
    setter = getattr(mgr, "set_tool_approval_policy", None)
    if callable(setter):
        return str(setter(mode))
    policy = _normalize_tool_approval_mode(mode) or "ask"
    mgr.config.set("features.tool_approval_policy", policy)
    mgr.config.set("features.auto_allow_tools", policy == "always")
    return policy


def _tool_registry_lines(mgr: Any) -> list[str]:
    tools = list(mgr.tool_registry)
    if not tools:
        return []
    lines = []
    for name, t in tools:
        lines.append(f"  🔧 {name}: {t.description}")
    return lines


def handle_tools_command(mgr: Any, args: list[str]) -> dict[str, Any]:
    if not args or args[0] == "list":
        tools = list(mgr.tool_registry)
        if not tools:
            return {"ok": True, "message": "No hay herramientas registradas."}
        lines = [f"  política aprobación: {current_tool_approval_policy(mgr)} (auto_allow_tools={mgr.config.get('features.auto_allow_tools')})"]
        lines.extend(_tool_registry_lines(mgr))
        return {"ok": True, "message": f"Herramientas disponibles ({len(tools)}):\n" + "\n".join(lines)}
    if args[0] == "enable":
        mgr.config.set("features.tool_calling", True)
        return {"ok": True, "message": "Herramientas activadas. El modelo puede invocar tools."}
    if args[0] == "disable":
        mgr.config.set("features.tool_calling", False)
        return {"ok": True, "message": "Herramientas desactivadas. El modelo no invocará tools."}
    if args[0] in ("approval", "policy"):
        if len(args) == 1:
            policy = current_tool_approval_policy(mgr)
            return {
                "ok": True,
                "message": (
                    f"Política actual de aprobación: {policy}\n"
                    "Usa /tools approval ask | /tools approval always"
                ),
            }
        mode = " ".join(args[1:]).strip()
        if not mode:
            policy = current_tool_approval_policy(mgr)
            return {"ok": True, "message": f"Política actual de aprobación: {policy}"}
        policy = set_tool_approval_policy(mgr, mode)
        return {
            "ok": True,
            "message": (
                f"✓ Política de aprobación actualizada a: {policy}\n"
                f"  auto_allow_tools = {mgr.config.get('features.auto_allow_tools')}"
            ),
        }
    return {"ok": False, "message": "Uso: /tools [list|enable|disable|approval [ask|always]]"}


def handle_allow_command(mgr: Any, args: list[str]) -> dict[str, Any]:
    mode = " ".join(args).strip() or "once"
    if hasattr(mgr, "approve_tools"):
        result = mgr.approve_tools(mode)
    else:
        result = "No se puede aprobar herramientas en este manager."
    return {"ok": True, "message": result}


def handle_deny_command(mgr: Any, args: list[str]) -> dict[str, Any]:
    mode = " ".join(args).strip() or "once"
    if hasattr(mgr, "deny_tools"):
        result = mgr.deny_tools(mode)
    else:
        result = "No se puede rechazar herramientas en este manager."
    return {"ok": True, "message": result}
