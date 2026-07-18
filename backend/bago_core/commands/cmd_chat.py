#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bago_core.resolver import add_piece_paths, load_piece_module

BAGO_ROOT = Path(__file__).resolve().parents[2]
add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")

EXPERIMENTAL_PROVIDERS: set[str] = set()

def _load_install_config(root: Path) -> dict[str, Any]:
    path = root / "install_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _resolve_state_root() -> Path:
    from state_paths import resolve_state_root
    return resolve_state_root()

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

def _write_llm_start_state(state_root: str | Path, provider: str, model: str, mode: str, bridges: list[str] | None = None) -> Path:
    import json as _json
    from datetime import datetime, timezone

    state_dir = Path(state_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "llm_start.json"
    payload = {
        "provider": provider,
        "model": model,
        "mode": mode,
        "bridges": list(dict.fromkeys([provider] + list(bridges or []))),
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
            os.environ["BAGO_STATE_ROOT"] = str(_resolve_state_root())
            add_piece_paths("tools.package")
            from process_monitor import serve
            serve(BAGO_ROOT, port=port, refresh=5, silent=True)
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True, name="bago-monitor")
    t.start()

def _tcp_ready(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ollama_endpoint(base_path: str) -> tuple[str, int]:
    from config_manager import ConfigManager

    cm = ConfigManager(base_path=base_path)
    base_url = str(cm.provider_config("ollama-local").get("base_url") or "http://127.0.0.1:11434").strip()
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    return host, port


def _find_ollama_exe() -> Path | None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    found = shutil.which("ollama")
    return Path(found) if found else None


def _ensure_ollama_local_ready(base_path: str) -> tuple[bool, str]:
    host, port = _ollama_endpoint(base_path)
    if _tcp_ready(host, port):
        return True, f"Ollama ya activo en {host}:{port}"

    exe = _find_ollama_exe()
    if exe is None:
        return False, "No se encontro ollama.exe para arrancarlo automaticamente"

    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [str(exe), "serve"],
            cwd=str(exe.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception as exc:
        return False, f"No se pudo lanzar Ollama automaticamente: {exc}"

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if _tcp_ready(host, port):
            return True, f"Ollama arrancado en {host}:{port}"
        time.sleep(0.5)
    return False, f"Ollama lanzado pero aun no responde en {host}:{port}"


def _open_context_session(base_path: str):
    from context_store import ContextStore
    from session_manager import SessionManager

    state_root = _resolve_state_root()
    project_root = Path(base_path).resolve()
    sessions = ContextStore.list_sessions(base_dir=state_root)
    if sessions:
        for item in reversed(sessions):
            sid = item["sid"]
            try:
                mgr = SessionManager.load(sid, base_path=base_path, state_root=str(state_root))
            except Exception:
                continue
            try:
                if Path(getattr(mgr, "project_root", mgr.base_path)).resolve() == project_root:
                    return mgr
            except Exception:
                pass
            try:
                mgr.close()
            except Exception:
                pass
    return SessionManager(base_path=base_path, state_root=str(state_root))


def cmd_context(args: argparse.Namespace) -> int:
    """Inspeccion/medicion del contexto real desde CLI."""
    mgr = _open_context_session(args.base_path)
    try:
        subcmd = getattr(args, "context_cmd", None) or "inspect"
        if subcmd == "inspect":
            data = mgr.inspect_context()
        elif subcmd == "measure":
            data = mgr.measure_context()
        elif subcmd == "benchmark":
            data = mgr.benchmark_context(getattr(args, "iterations", 3))
            if getattr(args, "cognitive", False):
                data["cognitive"] = mgr.benchmark_cognitive(getattr(args, "iterations", 1))
        elif subcmd == "certify":
            data = mgr.certify_context()
        elif subcmd == "history":
            data = mgr.context_history(getattr(args, "limit", 10))
        elif subcmd == "invalidate":
            if not getattr(args, "confirm", False):
                print("Uso: bago context invalidate --confirm")
                return 1
            data = mgr.invalidate_context(getattr(args, "reason", ""))
        elif subcmd == "calibrate":
            data = mgr.calibrate_context(getattr(args, "iterations", 3))
        elif subcmd == "tune":
            if not getattr(args, "confirm", False):
                print("Uso: bago context tune --confirm")
                return 1
            data = mgr.tune_context(authorized=True, patch={"requested": True})
        else:
            print("Uso: bago context [inspect|measure|benchmark|certify|history|invalidate|calibrate|tune]")
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data.get("ok", True) else 1
    finally:
        mgr.close()

def cmd_chat(args: argparse.Namespace) -> int:
    from repl import BagoREPL
    from system_prompt import get_system_prompt

    provider = getattr(args, "provider", "unknown") or "unknown"
    model = getattr(args, "model", "unknown") or "unknown"
    state_root = _resolve_state_root()

    if provider == "ollama-local" and not getattr(args, "no_ollama_autostart", False):
        ready, detail = _ensure_ollama_local_ready(args.base_path)
        print(detail)

    # Registrar sesion LLM en state/ para que el monitor la vea
    bridges = list(getattr(args, "active_bridges", None) or getattr(args, "llm_bridges", None) or [])
    _write_llm_start_state(state_root, provider, model, mode="chat", bridges=bridges)

    # Auto-arrancar monitor en background (no bloquea el chat)
    if not getattr(args, "no_monitor", False):
        _start_monitor_bg(args.base_path)

    repl = BagoREPL(
        provider=provider,
        model=model,
        system_prompt=get_system_prompt(),
        base_path=args.base_path,
        state_root=str(state_root),
        active_bridges=bridges,
        startup_prompt=getattr(args, "startup_prompt", True),
    )
    repl.run()
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    """Ejecuta un comando slash sin abrir el REPL interactivo."""
    from session_manager import SessionManager
    from switch_engine import SwitchEngine
    from system_prompt import get_system_prompt

    module = load_piece_module("chat.package", "bago_repl_commands_exec", "commands.py")
    execute = module.execute

    raw_command = getattr(args, "slash_command", None) or getattr(args, "command", None) or []
    command_line = " ".join(str(part) for part in raw_command).strip()
    if not command_line:
        print("Uso: bago exec /comando [args...]")
        return 1
    if not command_line.startswith("/"):
        command_line = f"/{command_line}"

    provider = getattr(args, "provider", "ollama-local") or "ollama-local"
    model = getattr(args, "model", "llama3.2:3b") or "llama3.2:3b"
    mgr = SessionManager(
        base_path=args.base_path,
        provider=provider,
        model=model,
        system_prompt=get_system_prompt(),
    )
    try:
        engine = SwitchEngine(mgr.adapters)
        result = execute(command_line, mgr, engine)
        action = result.get("action")
        message = result.get("message", "")
        if action == "menu":
            menu_text = message or module.execute("/help", mgr, engine)["message"]
            print(menu_text)
            return 0
        if message:
            print(message)
        return 0 if result.get("ok") else 1
    finally:
        mgr.close()

def cmd_llm(args: argparse.Namespace) -> int:
    from config_manager import ConfigManager

    action = args.llm_action or "list"
    inventory = _provider_inventory(args.base_path, include_experimental=getattr(args, "include_experimental", False))
    state_root = _resolve_state_root()

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
            cm = ConfigManager(base_path=args.base_path, state_root=str(state_root))
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

    bridges = list(dict.fromkeys([provider] + list(getattr(args, "llm_bridges", []) or [])))
    invalid_bridges = [name for name in bridges if name not in installed_names]
    if invalid_bridges and not getattr(args, "allow_unconfigured", False):
        print("Bridges no instalados/configurados: " + ", ".join(invalid_bridges))
        return 1

    if not model:
        model = _default_model_for_provider(args.base_path, provider)

    _write_llm_start_state(state_root, provider, model, mode="dry-run" if args.dry_run else "chat", bridges=bridges)
    print(f"LLM session: {provider}/{model}")
    print("Bridges activos: " + ", ".join(bridges))

    if getattr(args, "persist_default", False):
        cm = ConfigManager(base_path=args.base_path, state_root=str(state_root))
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
    args.active_bridges = bridges
    args.startup_prompt = False
    return cmd_chat(args)
