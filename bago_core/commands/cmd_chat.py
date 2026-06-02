#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BAGO_ROOT = Path(__file__).resolve().parents[2]

for _path in (
    BAGO_ROOT / "bago_core",
    BAGO_ROOT / ".bago" / "core",
    BAGO_ROOT / ".bago" / "chat",
    BAGO_ROOT / ".bago" / "providers",
    BAGO_ROOT / ".bago" / "api",
    BAGO_ROOT / ".bago" / "tools",
):
    _path_s = str(_path)
    if _path_s not in sys.path:
        sys.path.insert(0, _path_s)

EXPERIMENTAL_PROVIDERS = {"cpp-local"}

def _load_install_config(root: Path) -> dict[str, Any]:
    path = root / "install_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _provider_inventory(base_path: str, include_experimental: bool = False) -> list[dict[str, Any]]:
    from session_manager import ADAPTER_REGISTRY, SessionManager

    mgr = SessionManager(base_path=base_path)
    try:
        providers = {item["name"]: item for item in mgr.available_providers()}
        inventory = []
        for name in ADAPTER_REGISTRY:
            if name in EXPERIMENTAL_PROVIDERS and not include_experimental:
                continue
            info = providers.get(name, {"name": name, "configured": False, "models": []})
            enabled = mgr.config.is_provider_enabled(name)
            configured = bool(info.get("configured"))
            models = list(info.get("models") or [])
            inventory.append({
                "name": name,
                "enabled": enabled,
                "configured": configured,
                "installed": enabled or configured,
                "models": models,
            })
        return inventory
    finally:
        mgr.close()

def _default_model_for_provider(base_path: str, provider: str) -> str:
    from session_manager import SessionManager

    mgr = SessionManager(base_path=base_path, provider=provider)
    try:
        models = mgr.list_models(provider)
        if provider == mgr.config.default_provider and mgr.config.default_model in models:
            return mgr.config.default_model
        return models[0] if models else mgr.config.default_model
    finally:
        mgr.close()

def _write_llm_start_state(base_path: str, provider: str, model: str, mode: str) -> Path:
    import json as _json
    from datetime import datetime, timezone

    state_dir = Path(base_path) / ".bago" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "llm_start.json"
    payload = {
        "provider": provider,
        "model": model,
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(_json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

def _start_monitor_bg(base_path: str, port: int = 7890) -> None:
    """Arranca bago monitor serve en un hilo daemon si el puerto no esta en uso."""
    import socket
    import threading

    def _port_free(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return True
            except OSError:
                return False

    if not _port_free(port):
        return  # ya esta corriendo

    def _run():
        try:
            sys.path.insert(0, str(BAGO_ROOT / ".bago" / "tools"))
            from process_monitor import serve
            serve(BAGO_ROOT, port=port, refresh=5)
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True, name="bago-monitor")
    t.start()

def cmd_chat(args: argparse.Namespace) -> int:
    from repl import BagoREPL
    from system_prompt import get_system_prompt

    provider = getattr(args, "provider", "unknown") or "unknown"
    model = getattr(args, "model", "unknown") or "unknown"

    # Registrar sesion LLM en state/ para que el monitor la vea
    _write_llm_start_state(args.base_path, provider, model, mode="chat")

    # Auto-arrancar monitor en background (no bloquea el chat)
    if not getattr(args, "no_monitor", False):
        _start_monitor_bg(args.base_path)

    repl = BagoREPL(
        provider=provider,
        model=model,
        system_prompt=get_system_prompt(),
        base_path=args.base_path,
    )
    repl.run()
    return 0

def cmd_llm(args: argparse.Namespace) -> int:
    from config_manager import ConfigManager

    action = args.llm_action or "list"
    inventory = _provider_inventory(args.base_path, include_experimental=getattr(args, "include_experimental", False))

    if action == "list":
        print("BAGO LLM providers")
        print("Instalados/configurados:")
        installed = [item for item in inventory if item["installed"]]
        pending = [item for item in inventory if not item["installed"]]
        if installed:
            for item in installed:
                markers = []
                if item["enabled"]:
                    markers.append("enabled")
                if item["configured"]:
                    markers.append("configured")
                markers_s = ", ".join(markers) or "local"
                models = len(item["models"])
                print(f"  [ok] {item['name']} ({markers_s}, {models} modelos)")
        else:
            print("  ninguno")
        print("Disponibles para configurar:")
        for item in pending:
            print(f"  [--] {item['name']}")
        if not getattr(args, "include_experimental", False):
            print("Experimentales ocultos: usa --include-experimental para verlos.")
        return 0

    if action != "start":
        print("Uso: bago llm [list|start]")
        return 1

    provider = getattr(args, "llm_provider", "") or ""
    model = getattr(args, "llm_model", "") or ""
    installed = [item for item in inventory if item["installed"]]
    installed_names = {item["name"] for item in installed}
    all_names = {item["name"] for item in inventory}

    if not provider:
        if hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            print("Providers instalados/configurados:")
            for idx, item in enumerate(installed, 1):
                print(f"  {idx}. {item['name']} ({len(item['models'])} modelos)")
            print("Providers disponibles para configurar:")
            for item in inventory:
                if not item["installed"]:
                    print(f"  - {item['name']}")
            choice = input("Elige provider instalado: ").strip()
            try:
                provider = installed[int(choice) - 1]["name"]
            except Exception:
                print("Seleccion invalida.")
                return 1
        elif installed:
            provider = installed[0]["name"]
        else:
            cm = ConfigManager(base_path=args.base_path)
            provider = cm.default_provider

    if provider in EXPERIMENTAL_PROVIDERS and not getattr(args, "include_experimental", False):
        print(f"Provider experimental fuera del camino principal: {provider}")
        print("Usa --include-experimental si quieres probarlo explicitamente.")
        return 1
    if provider not in all_names:
        print(f"Provider no registrado: {provider}")
        return 1
    if provider not in installed_names and not getattr(args, "allow_unconfigured", False):
        print(f"Provider no instalado/configurado: {provider}")
        print("Usa 'bago llm list' para ver instalados y disponibles.")
        return 1

    if not model:
        model = _default_model_for_provider(args.base_path, provider)

    _write_llm_start_state(args.base_path, provider, model, mode="dry-run" if args.dry_run else "chat")
    print(f"LLM session: {provider}/{model}")

    if getattr(args, "persist_default", False):
        cm = ConfigManager(base_path=args.base_path)
        cm.default_provider = provider
        cm.default_model = model
        print("Default provider/model actualizado.")

    if args.dry_run:
        return 0

    # Auto-arrancar monitor (no bloquea)
    if not getattr(args, "no_monitor", False):
        _start_monitor_bg(args.base_path)

    args.provider = provider
    args.model = model
    return cmd_chat(args)
