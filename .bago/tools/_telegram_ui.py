from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

_INTENT_PATTERNS: list = [
    (re.compile(r"\b(ping|test)\b"),                          "ping"),
    (re.compile(r"\b(menu|menú|start|inicio)\b"),             "menu"),
    (re.compile(r"\b(estado|status)\b"),                      "status"),
    (re.compile(r"\b(sprint|workflow|wf)\b"),                 "sprint"),
    (re.compile(r"\b(git|commit|branch|rama)\b"),             "git"),
    (re.compile(r"\b(tareas|tasks|pendiente|todo)\b"),        "tareas"),
    (re.compile(r"\b(ideas?|idea)\b"),                        "ideas"),
    (re.compile(r"\b(next|siguiente|próxima|proxima)\b"),     "next"),
    (re.compile(r"\b(health|salud|score)\b"),                 "health"),
    (re.compile(r"\b(tarea|task|hacer|create|crea)\b"),       "crear_tarea"),
    (re.compile(r"\b(nota|note|apunta|apuntar|recordar)\b"),  "nota"),
    (re.compile(r"\b(ayuda|help|comandos|qué puedes)\b"),     "ayuda"),
]

def detect_intent(text: str) -> str:
    """Return the intent label for a free-text message (lowercase)."""
    tl = text.lower()
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.search(tl):
            return intent
    return "unknown"


def format_estado(state: dict) -> str:
    """Format a BAGO state dict into a human-readable Telegram message."""
    v      = state.get("bago_version", "?")
    health = state.get("system_health", state.get("health_score", {}).get("score", "?"))
    wf     = state.get("sprint_status", {}).get("active_workflow") or {}
    wf_str = f"{wf.get('code','?')} — {wf.get('title','?')}" if wf else "ninguno"
    guardian = state.get("guardian_findings", {}).get("status", "?")
    return (
        f"🤖 BAGO v{v}\n"
        f"⚕️ Health: {health}\n"
        f"⚡ Workflow: {wf_str}\n"
        f"🛡 Guardian: {guardian}"
    )


def make_main_keyboard():
    """Return the main inline keyboard markup (alias for kb_menu_principal)."""
    return kb_menu_principal()

def kb_menu_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Estado",      callback_data="accion:estado"),
         InlineKeyboardButton("⚡ Sprint",       callback_data="accion:sprint")],
        [InlineKeyboardButton("📋 Tareas",       callback_data="accion:tareas"),
         InlineKeyboardButton("📝 Notas",        callback_data="accion:notas")],
        [InlineKeyboardButton("📁 Git Log",      callback_data="accion:git"),
         InlineKeyboardButton("📜 Logs",         callback_data="accion:logs")],
        [InlineKeyboardButton("💰 Cartera",      callback_data="accion:cartera"),
         InlineKeyboardButton("🪂 Airdrops",     callback_data="accion:airdrop"),
         InlineKeyboardButton("🌐 Mini App",     callback_data="accion:app")],
        [InlineKeyboardButton("📈 Telemetría",   callback_data="accion:telemetria"),
         InlineKeyboardButton("❓ Ayuda",         callback_data="accion:ayuda")],
    ])

def kb_estado() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Sprint",   callback_data="accion:sprint"),
         InlineKeyboardButton("📁 Git",      callback_data="accion:git")],
        [InlineKeyboardButton("📋 Tareas",   callback_data="accion:tareas"),
         InlineKeyboardButton("🔄 Refresh",  callback_data="accion:estado")],
    ])

def kb_git() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Status",   callback_data="cmd:git status"),
         InlineKeyboardButton("📊 Diff",     callback_data="cmd:git diff")],
        [InlineKeyboardButton("🌿 Branch",   callback_data="cmd:git branch"),
         InlineKeyboardButton("📜 Log",      callback_data="cmd:git log")],
    ])

def kb_tareas(tareas_pendientes: list) -> InlineKeyboardMarkup:
    rows = []
    for t in tareas_pendientes[:5]:
        tid = t["id"]
        txt = t["titulo"][:28]
        rows.append([
            InlineKeyboardButton(f"✅ {txt}", callback_data=f"completar:{tid}"),
            InlineKeyboardButton("🗑",         callback_data=f"borrar:{tid}"),
        ])
    rows.append([InlineKeyboardButton("➕ Nueva tarea",  callback_data="accion:nueva_tarea")])
    rows.append([InlineKeyboardButton("🏠 Menú",         callback_data="accion:menu")])
    return InlineKeyboardMarkup(rows)


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())

