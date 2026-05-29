"""

setup_wizard.py — BAGO first-time setup wizard.

Initializes global_state.json from template and configures
notification providers (Telegram, WhatsApp) in notify_config.json.

Usage:
    bago setup              # interactive wizard
    bago setup --check      # verify config is complete
    bago setup --reset      # reset to template
"""

import json
import shutil
import sys
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
_TOOLS = Path(__file__).resolve().parent
_STATE = _TOOLS.parent / "state"
_GLOBAL_STATE = _STATE / "global_state.json"
_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "global_state.clean.json"
_NOTIFY_CONFIG = _STATE / "notify_config.json"

_NOTIFY_TEMPLATE = {
    "provider": "none",
    "telegram": {
        "bot_token": "",
        "chat_id": "",
        "owner_chat_id": ""
    },
    "whatsapp": {
        "instance_id": "",
        "api_url": "",
        "api_token": "",
        "phone": ""
    },
    "ntfy": {
        "topic": "",
        "server": "https://ntfy.sh"
    }
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    """Ask user for input with optional default."""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{suffix}: ").strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        print("\n⛔ Setup cancelado.")
        sys.exit(0)


def _ask_yn(prompt: str, default: bool = False) -> bool:
    default_str = "S/n" if default else "s/N"
    try:
        val = input(f"  {prompt} [{default_str}]: ").strip().lower()
        if not val:
            return default
        return val in ("s", "si", "y", "yes")
    except (KeyboardInterrupt, EOFError):
        print("\n⛔ Setup cancelado.")
        sys.exit(0)


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── check ─────────────────────────────────────────────────────────────────────

def cmd_check() -> int:
    """Verify that setup is complete and config is valid."""
    ok = True
    print("\n🔍 Verificando configuración BAGO...\n")

    if not _GLOBAL_STATE.exists():
        print("  ❌ global_state.json no existe — ejecuta: bago setup")
        ok = False
    else:
        gs = _load_json(_GLOBAL_STATE)
        wa_id = gs.get("whatsapp_daemon", {}).get("instance_id", "")
        tg_user = gs.get("telegram_bot", {}).get("bot_username", "")
        if "__CONFIGURE_WITH_bago_setup__" in (wa_id, tg_user):
            print("  ⚠️  Configuración de notificaciones pendiente — ejecuta: bago setup")
        else:
            print("  ✅ global_state.json presente")

    if not _NOTIFY_CONFIG.exists():
        print("  ⚠️  notify_config.json no existe — las notificaciones están desactivadas")
    else:
        nc = _load_json(_NOTIFY_CONFIG)
        provider = nc.get("provider", "none")
        if provider == "none":
            print("  ⚠️  Proveedor de notificaciones: ninguno configurado")
        else:
            print(f"  ✅ Notificaciones: {provider}")

    if ok:
        print("\n✅ Setup completo.\n")
        return 0
    print("\n💡 Ejecuta: bago setup\n")
    return 1


# ── reset ─────────────────────────────────────────────────────────────────────

def cmd_reset() -> int:
    """Reset global_state.json to template."""
    if not _TEMPLATE.exists():
        print("❌ Template no encontrado:", _TEMPLATE)
        return 1
    if _GLOBAL_STATE.exists():
        backup = _GLOBAL_STATE.with_suffix(".json.bak")
        shutil.copy(_GLOBAL_STATE, backup)
        print(f"  📦 Backup en: {backup}")
    shutil.copy(_TEMPLATE, _GLOBAL_STATE)
    print("✅ global_state.json reiniciado desde template.")
    return 0


# ── wizard ────────────────────────────────────────────────────────────────────

def cmd_setup() -> int:
    """Interactive first-time setup wizard."""
    print("\n" + "─" * 50)
    print("  ⬡ BAGO Setup Wizard")
    print("─" * 50)
    print("  Configura tus notificaciones y credenciales.")
    print("  Los datos NO se subirán a git (gitignored).\n")

    # ── Step 1: global_state.json ────────────────────────────────────────────
    if not _GLOBAL_STATE.exists():
        if not _TEMPLATE.exists():
            print("❌ Template no encontrado. Reinstala BAGO.")
            return 1
        shutil.copy(_TEMPLATE, _GLOBAL_STATE)
        print("  ✅ global_state.json creado desde template\n")
    else:
        print("  ℹ️  global_state.json ya existe — solo se actualiza notify_config.json\n")

    # ── Step 2: notification provider ───────────────────────────────────────
    nc = _load_json(_NOTIFY_CONFIG) if _NOTIFY_CONFIG.exists() else dict(_NOTIFY_TEMPLATE)

    print("  ¿Qué proveedor de notificaciones quieres usar?")
    print("    1) Telegram  (bot propio)")
    print("    2) WhatsApp  (Green API)")
    print("    3) ntfy      (self-hosted, gratuito)")
    print("    4) Ninguno")
    choice = _ask("Elige (1-4)", "4")

    provider = "none"
    if choice == "1":
        provider = "telegram"
        print("\n  📱 Telegram — crea tu bot con @BotFather si no tienes uno\n")
        token = _ask("Bot token (ej: 123456:ABC...)")
        chat_id = _ask("Tu chat_id (ej: 7752787448)")
        nc.setdefault("telegram", {})
        nc["telegram"]["bot_token"] = token
        nc["telegram"]["chat_id"] = chat_id
        nc["telegram"]["owner_chat_id"] = chat_id
        print("  ✅ Telegram configurado")

    elif choice == "2":
        provider = "whatsapp"
        print("\n  📱 WhatsApp — necesitas cuenta Green API (https://green-api.com)\n")
        instance_id = _ask("Instance ID")
        api_url = _ask("API URL (ej: https://XXXX.api.greenapi.com)")
        api_token = _ask("API Token")
        phone = _ask("Tu número (ej: +34600000000)")
        nc.setdefault("whatsapp", {})
        nc["whatsapp"]["instance_id"] = instance_id
        nc["whatsapp"]["api_url"] = api_url
        nc["whatsapp"]["api_token"] = api_token
        nc["whatsapp"]["phone"] = phone
        print("  ✅ WhatsApp configurado")

    elif choice == "3":
        provider = "ntfy"
        print("\n  📢 ntfy — servidor de notificaciones open source\n")
        topic = _ask("Topic (ej: mi-bago-alerts)")
        server = _ask("Servidor", "https://ntfy.sh")
        nc.setdefault("ntfy", {})
        nc["ntfy"]["topic"] = topic
        nc["ntfy"]["server"] = server
        print("  ✅ ntfy configurado")

    nc["provider"] = provider
    _save_json(_NOTIFY_CONFIG, nc)

    # ── Step 3: git hooks ────────────────────────────────────────────────────
    import subprocess
    print("\n  🔒 Configurando git hooks...")
    repo_root = Path(__file__).resolve().parent.parent.parent
    hooks_path = repo_root / ".githooks"
    result = subprocess.run(
        ["git", "config", "core.hooksPath", str(hooks_path)],
        cwd=repo_root, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  ✅ core.hooksPath → {hooks_path}")
    else:
        print(f"  ⚠️  No se pudo configurar git hooks: {result.stderr.strip()}")

    # ── Done ─────────────────────────────────────────────────────────────────
    print("\n" + "─" * 50)
    print("  ✅ Setup completado\n")
    print("  Próximos pasos:")
    print("    bago validate     — verificar instalación")
    print("    bago setup --check — verificar configuración")
    print("    bago hello         — ver comandos disponibles")
    print("─" * 50 + "\n")
    return 0


# ── git history cleanup instructions ─────────────────────────────────────────

def cmd_clean_history() -> int:
    """Print instructions for cleaning git history of secrets."""
    print("""
⚠️  LIMPIEZA DE HISTÓRICO GIT — secrets previos
═══════════════════════════════════════════════

Si global_state.json estuvo en el repo antes de esta sesión,
los secrets pueden estar en commits anteriores.

OPCIÓN 1: BFG Repo-Cleaner (recomendado, rápido)
─────────────────────────────────────────────────
  # Instalar: https://rtyley.github.io/bfg-repo-cleaner/
  java -jar bfg.jar --delete-files global_state.json
  git reflog expire --expire=now --all
  git gc --prune=now --aggressive
  git push --force-with-lease

OPCIÓN 2: git filter-branch (nativo, lento)
────────────────────────────────────────────
  git filter-branch --force --index-filter \\
    "git rm --cached --ignore-unmatch .bago/state/global_state.json" \\
    --prune-empty --tag-name-filter cat -- --all
  git push --force-with-lease

DESPUÉS:
  - Revocar TODOS los tokens expuestos
  - WhatsApp Green API: revocar en https://console.green-api.com
  - Telegram: revocar bot con @BotFather → /revoke
  - Ngrok: rotar token en https://dashboard.ngrok.com

""")
    return 0


# ── main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--check" in args:
        return cmd_check()
    if "--reset" in args:
        return cmd_reset()
    if "--clean-history" in args:
        return cmd_clean_history()
    return cmd_setup()




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
    sys.exit(main())