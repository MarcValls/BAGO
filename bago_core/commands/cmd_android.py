#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

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


def _is_termux() -> bool:
    home = str(Path.home())
    return "com.termux" in home or bool(os.environ.get("TERMUX_VERSION"))


def _doctor_payload(base_path: Path, cm: ConfigManager, creds: CredentialManager) -> dict:
    providers = []
    for name in ANDROID_NON_LOCAL:
        required = creds.required_keys(name)
        missing = [key for key in required if not creds.get(name, key)]
        providers.append({
            "name": name,
            "enabled": bool(cm.is_provider_enabled(name)),
            "configured": bool(creds.is_configured(name)),
            "required_keys": required,
            "missing_keys": missing,
            "base_url": cm.get(f"providers.{name}.base_url", ""),
        })
    return {
        "ok": True,
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

    required = creds.required_keys(provider)
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


def cmd_android(args: argparse.Namespace) -> int:
    base_path = Path(args.base_path).resolve()
    cm = ConfigManager(base_path=str(base_path))
    creds = CredentialManager(base_path=str(base_path))
    action = (args.android_action or "doctor").strip().lower()
    as_json = bool(getattr(args, "android_json", False))

    if action == "doctor":
        payload = _doctor_payload(base_path, cm, creds)
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        print("BAGO Android doctor")
        print(f"Base path: {payload['base_path']}")
        print(f"Termux detectado: {'sí' if payload['android_termux_detected'] else 'no'}")
        print(f"Default: {payload['default_provider']} / {payload['default_model']}")
        for item in payload["providers"]:
            state = "enabled" if item["enabled"] else "disabled"
            creds_state = "configured" if item["configured"] else "no-config"
            print(f"- {item['name']}: {state}, {creds_state}")
            if item["missing_keys"]:
                print(f"  faltan: {', '.join(item['missing_keys'])}")
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

    print("Uso: bago android [doctor|init]")
    return 1
