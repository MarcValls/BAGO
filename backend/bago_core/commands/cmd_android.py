#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

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

from config_manager import ConfigManager
from credential_manager import CredentialManager

ANDROID_PRESETS: dict[str, dict[str, str]] = {
    "openrouter": {
        "default_model": "openai/gpt-4o-mini",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "codex": {
        "default_model": "gpt-5.4-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "default_model": "claude-3-5-sonnet-latest",
        "base_url": "https://api.anthropic.com/v1",
    },
}
ANDROID_NON_LOCAL = tuple(ANDROID_PRESETS.keys())
ANDROID_LOCAL_ONLY = ("ollama-local", "cpp-local")
ANDROID_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "codex": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}
ANDROID_LAYERS_STATE = Path(".bago") / "state" / "android_layers.json"


def _is_termux() -> bool:
    home = str(Path.home())
    return (
        "com.termux" in home
        or bool(os.environ.get("TERMUX_VERSION"))
        or shutil.which("termux-info") is not None
    )


def _required_keys(provider: str) -> tuple[str, ...]:
    return ANDROID_REQUIRED_KEYS.get(provider, ())


def _pick_provider(requested: str, cm: ConfigManager) -> str:
    candidate = (requested or "").strip().lower()
    if candidate in ANDROID_PRESETS:
        return candidate
    default_provider = str(cm.default_provider or "").strip().lower()
    if default_provider in ANDROID_PRESETS:
        return default_provider
    return "openrouter"


def _pick_model(provider: str, requested_model: str) -> str:
    model = (requested_model or "").strip()
    if model:
        return model
    return ANDROID_PRESETS[provider]["default_model"]


def _pick_base_url(cm: ConfigManager, provider: str, requested_base_url: str) -> str:
    if (requested_base_url or "").strip():
        return requested_base_url.strip().rstrip("/")
    configured = str(cm.get(f"providers.{provider}.base_url", "") or "").strip().rstrip("/")
    if configured:
        return configured
    return ANDROID_PRESETS[provider]["base_url"]


def _provider_rows(cm: ConfigManager, creds: CredentialManager) -> list[dict]:
    providers = []
    for name in ANDROID_NON_LOCAL:
        required = list(_required_keys(name))
        missing = [key for key in required if not creds.get(name, key)]
        providers.append({
            "name": name,
            "enabled": bool(cm.is_provider_enabled(name)),
            "configured": len(missing) == 0,
            "required_keys": required,
            "missing_keys": missing,
            "base_url": cm.get(f"providers.{name}.base_url", ""),
        })
    return providers


def _runtime_layer() -> dict:
    termux = _is_termux()
    python_ok = sys.version_info >= (3, 11)
    git_ok = shutil.which("git") is not None
    pkg_ok = shutil.which("pkg") is not None or not termux
    ok = termux and python_ok and git_ok and pkg_ok
    actions = []
    if not termux:
        actions.append("Instalar/usar Termux para ejecutar BAGO CLI en Android.")
    if not python_ok:
        actions.append("Actualizar Python a 3.11+ dentro de Termux.")
    if not git_ok:
        actions.append("Instalar git en Termux: pkg install -y git")
    if termux and not pkg_ok:
        actions.append("Verificar gestor de paquetes Termux (pkg).")
    return {
        "ok": ok,
        "details": {
            "termux_detected": termux,
            "python_ok": python_ok,
            "git_ok": git_ok,
            "pkg_ok": pkg_ok,
        },
        "actions": actions,
    }


def _provider_layer(cm: ConfigManager, creds: CredentialManager, provider: str, model: str, base_url: str) -> dict:
    required = list(_required_keys(provider))
    missing = [key for key in required if not creds.get(provider, key)]
    enabled = bool(cm.is_provider_enabled(provider))
    ok = enabled and not missing and bool(model.strip()) and bool(base_url.strip())
    actions = []
    if not enabled:
        actions.append(f"Habilitar provider {provider}.")
    if missing:
        actions.append(f"Definir credenciales: {', '.join(missing)}")
    if not model.strip():
        actions.append("Definir modelo Android por defecto.")
    if not base_url.strip():
        actions.append("Definir base URL del provider.")
    return {
        "ok": ok,
        "details": {
            "provider": provider,
            "enabled": enabled,
            "model": model,
            "base_url": base_url,
            "required_keys": required,
            "missing_keys": missing,
        },
        "actions": actions,
    }


def _security_layer(cm: ConfigManager) -> dict:
    local_disabled = all(not bool(cm.is_provider_enabled(name)) for name in ANDROID_LOCAL_ONLY)
    prompt_provider_on_start = bool(cm.get("ui.prompt_provider_on_start", False))
    default_non_local = str(cm.default_provider or "").strip().lower() not in ANDROID_LOCAL_ONLY
    ok = local_disabled and prompt_provider_on_start and default_non_local
    actions = []
    if not local_disabled:
        actions.append("Deshabilitar providers locales (ollama-local/cpp-local).")
    if not prompt_provider_on_start:
        actions.append("Activar ui.prompt_provider_on_start para confirmar provider al inicio.")
    if not default_non_local:
        actions.append("Mover default_provider a un provider cloud Android.")
    return {
        "ok": ok,
        "details": {
            "local_providers_disabled": local_disabled,
            "prompt_provider_on_start": prompt_provider_on_start,
            "default_provider": cm.default_provider,
            "default_provider_non_local": default_non_local,
        },
        "actions": actions,
    }


def _ui_layer(base_path: Path) -> dict:
    ui_file = base_path / "manager" / "android" / "index.html"
    ok = ui_file.exists()
    actions = [] if ok else ["Añadir gestor Android en manager/android/index.html."]
    return {
        "ok": ok,
        "details": {"android_manager_path": str(ui_file), "exists": ok},
        "actions": actions,
    }


def _network_layer(base_url: str, provider: str) -> dict:
    endpoint = (base_url or "").strip()
    if not endpoint:
        return {
            "ok": False,
            "details": {"provider": provider, "reachable": False, "reason": "base_url vacía"},
            "actions": ["Configurar base_url del provider para test de red."],
        }
    parsed = urlparse(endpoint)
    host = parsed.hostname or ""
    port = parsed.port or (443 if (parsed.scheme or "https") == "https" else 80)
    if not host:
        return {
            "ok": False,
            "details": {"provider": provider, "reachable": False, "reason": "host inválido"},
            "actions": ["Corregir base_url del provider."],
        }
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
        return {
            "ok": True,
            "details": {"provider": provider, "reachable": True, "host": host, "port": port},
            "actions": [],
        }
    except OSError as exc:
        return {
            "ok": False,
            "details": {"provider": provider, "reachable": False, "host": host, "port": port, "reason": str(exc)},
            "actions": [f"Verificar red Android o acceso a {host}:{port}."],
        }


def _build_layers_payload(
    base_path: Path,
    cm: ConfigManager,
    creds: CredentialManager,
    provider: str = "",
    model: str = "",
    base_url: str = "",
) -> dict:
    selected_provider = _pick_provider(provider, cm)
    selected_model = _pick_model(selected_provider, model)
    selected_base_url = _pick_base_url(cm, selected_provider, base_url)
    layers = {
        "layer_runtime": _runtime_layer(),
        "layer_provider": _provider_layer(cm, creds, selected_provider, selected_model, selected_base_url),
        "layer_network": _network_layer(selected_base_url, selected_provider),
        "layer_security": _security_layer(cm),
        "layer_ui": _ui_layer(base_path),
    }
    ordered = ("layer_runtime", "layer_provider", "layer_network", "layer_security", "layer_ui")
    actions = []
    for layer_name in ordered:
        for action in layers[layer_name]["actions"]:
            if action not in actions:
                actions.append(action)
    return {
        "ok": all(layers[layer]["ok"] for layer in ordered),
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "selected_base_url": selected_base_url,
        "layers": layers,
        "next_actions": actions,
    }


def _write_layers_state(base_path: Path, payload: dict) -> Path:
    target = base_path / ANDROID_LAYERS_STATE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _doctor_payload(base_path: Path, cm: ConfigManager, creds: CredentialManager) -> dict:
    layers_report = _build_layers_payload(base_path, cm, creds)
    providers = _provider_rows(cm, creds)
    return {
        "ok": layers_report["ok"],
        "mode": "doctor",
        "android_termux_detected": _is_termux(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "base_path": str(base_path),
        "default_provider": cm.default_provider,
        "default_model": cm.default_model,
        "local_providers_disabled": {
            key: not bool(cm.is_provider_enabled(key))
            for key in ANDROID_LOCAL_ONLY
        },
        "providers": providers,
        "layers_report": layers_report,
    }


def _init_payload(
    base_path: Path,
    cm: ConfigManager,
    creds: CredentialManager,
    provider: str,
    model: str,
    base_url: str,
) -> dict:
    for local_provider in ANDROID_LOCAL_ONLY:
        cm.set_provider_enabled(local_provider, False)
    for name in ANDROID_NON_LOCAL:
        cm.set_provider_enabled(name, name == provider)
    cm.default_provider = provider
    cm.default_model = model
    cm.set(f"providers.{provider}.base_url", base_url)
    cm.set("ui.prompt_provider_on_start", True)

    required = _required_keys(provider)
    missing = [key for key in required if not creds.get(provider, key)]
    termux_cmd = [
        f"bago android init --provider {provider} --model {model}",
        f"export {required[0]}='<tu_clave>'" if required else "# sin claves requeridas",
        f"bago llm start --provider {provider} --model {model} --dry-run",
    ]

    return {
        "ok": True,
        "mode": "init",
        "android_termux_detected": _is_termux(),
        "base_path": str(base_path),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "missing_keys": missing,
        "local_providers_disabled": {
            key: not bool(cm.is_provider_enabled(key))
            for key in ANDROID_LOCAL_ONLY
        },
        "termux_next_steps": termux_cmd,
    }


def _apply_android_layers(
    base_path: Path,
    cm: ConfigManager,
    provider: str,
    model: str,
    base_url: str,
    force: bool = False,
) -> list[str]:
    if not _is_termux() and not force:
        raise RuntimeError("`android layers --apply` solo aplica en Termux. Usa --force si quieres aplicarlo fuera de Android.")
    changes: list[str] = []
    for local_provider in ANDROID_LOCAL_ONLY:
        if cm.is_provider_enabled(local_provider):
            changes.append(f"Deshabilitado {local_provider}.")
        cm.set_provider_enabled(local_provider, False)
    for name in ANDROID_NON_LOCAL:
        cm.set_provider_enabled(name, name == provider)
    if cm.default_provider != provider:
        changes.append(f"default_provider -> {provider}")
    cm.default_provider = provider
    if cm.default_model != model:
        changes.append(f"default_model -> {model}")
    cm.default_model = model
    cm.set(f"providers.{provider}.base_url", base_url)
    cm.set("ui.prompt_provider_on_start", True)
    if not changes:
        changes.append("Sin cambios: baseline Android ya aplicado.")
    return changes


def cmd_android(args: argparse.Namespace) -> int:
    base_path = Path(args.base_path).resolve()
    cm = ConfigManager(base_path=str(base_path))
    creds = CredentialManager(base_path=str(base_path))
    action = (args.android_action or "doctor").strip().lower()
    as_json = bool(getattr(args, "android_json", False))

    if action == "doctor":
        payload = _doctor_payload(base_path, cm, creds)
        _write_layers_state(base_path, payload["layers_report"])
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        print("BAGO Android doctor")
        print(f"Base path: {payload['base_path']}")
        print(f"Termux detectado: {'sí' if payload['android_termux_detected'] else 'no'}")
        print(f"Default: {payload['default_provider']} / {payload['default_model']}")
        print(f"Capas OK: {'sí' if payload['layers_report']['ok'] else 'no'}")
        for item in payload["providers"]:
            state = "enabled" if item["enabled"] else "disabled"
            creds_state = "configured" if item["configured"] else "missing-creds"
            print(f"- {item['name']}: {state}, {creds_state}")
            if item["missing_keys"]:
                print(f"  faltan: {', '.join(item['missing_keys'])}")
        if payload["layers_report"]["next_actions"]:
            print("Siguientes acciones por capas:")
            for step in payload["layers_report"]["next_actions"]:
                print(f"  - {step}")
        return 0

    if action == "init":
        provider = getattr(args, "android_provider", "openrouter")
        if provider not in ANDROID_PRESETS:
            print(f"Provider Android no soportado: {provider}")
            return 1
        preset = ANDROID_PRESETS[provider]
        model = (getattr(args, "android_model", "") or "").strip() or preset["default_model"]
        base_url = (getattr(args, "android_base_url", "") or "").strip() or preset["base_url"]
        payload = _init_payload(base_path, cm, creds, provider=provider, model=model, base_url=base_url)
        _write_layers_state(base_path, _build_layers_payload(base_path, cm, creds, provider=provider, model=model, base_url=base_url))
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        print("BAGO Android init")
        print(f"Provider: {provider}")
        print(f"Model   : {model}")
        print(f"Base URL: {base_url}")
        if payload["missing_keys"]:
            print("Credenciales pendientes:")
            for key in payload["missing_keys"]:
                print(f"- {key}")
        print("Siguientes pasos (Termux):")
        for step in payload["termux_next_steps"]:
            print(f"  {step}")
        return 0

    if action == "layers":
        provider = getattr(args, "android_provider", "")
        selected_provider = _pick_provider(provider, cm)
        model = _pick_model(selected_provider, getattr(args, "android_model", ""))
        base_url = _pick_base_url(cm, selected_provider, getattr(args, "android_base_url", ""))
        applied = False
        changes: list[str] = []
        if getattr(args, "android_apply", False):
            try:
                changes = _apply_android_layers(
                    base_path,
                    cm,
                    provider=selected_provider,
                    model=model,
                    base_url=base_url,
                    force=bool(getattr(args, "android_force", False)),
                )
                applied = True
            except RuntimeError as exc:
                print(str(exc))
                return 1
        layers_report = _build_layers_payload(base_path, cm, creds, provider=selected_provider, model=model, base_url=base_url)
        state_file = _write_layers_state(base_path, layers_report)
        payload = {
            "ok": layers_report["ok"],
            "mode": "layers",
            "applied": applied,
            "changes": changes,
            "state_file": str(state_file),
            **layers_report,
        }
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        print("BAGO Android layers")
        print(f"Provider: {payload['selected_provider']} / {payload['selected_model']}")
        print(f"Base URL: {payload['selected_base_url']}")
        print(f"Estado global: {'OK' if payload['ok'] else 'PENDIENTE'}")
        if applied:
            print("Cambios aplicados:")
            for item in changes:
                print(f"  - {item}")
        for layer_name, layer in payload["layers"].items():
            print(f"- {layer_name}: {'ok' if layer['ok'] else 'pendiente'}")
        if payload["next_actions"]:
            print("Siguientes acciones:")
            for step in payload["next_actions"]:
                print(f"  - {step}")
        print(f"Estado guardado en: {payload['state_file']}")
        return 0

    print("Uso: bago android [doctor|init|layers]")
    return 1
