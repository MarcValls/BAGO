#!/usr/bin/env python3
"""
cmd_provider.py -- Inspect and patch providers in .bago/config.json.

Uso:
    python bago_core\\cli.py provider list
    python bago_core\\cli.py provider show ollama-local
    python bago_core\\cli.py provider set-key ollama-local base_url http://127.0.0.1:11434
    python bago_core\\cli.py provider set-default-model ollama-local qwen2.5:1.5b
    python bago_core\\cli.py provider unset-default-model ollama-local
    python bago_core\\cli.py provider enable ollama-local
    python bago_core\\cli.py provider disable ollama-local

Compatibilidad histórica:
    python bago_core\\cli.py provider set-fallback qwen2.5:1.5b   # alias
    python bago_core\\cli.py provider remove-fallback              # alias
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow standalone execution from source tree.
_BAGO_ROOT = Path(__file__).resolve().parents[2]
if str(_BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(_BAGO_ROOT))
_core_dir = str(_BAGO_ROOT / ".bago" / "core")
if Path(_core_dir).exists() and _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

# Canonical config keys. Kept as constants to avoid magic strings scattered in code.
_KEY_ENABLED = "enabled"
_KEY_DEFAULT_MODEL = "default_model"
_KEY_FALLBACK_MODEL = "fallback_model"

# Fallback default provider only used when ConfigManager has no preference.
_DEFAULT_LOCAL_PROVIDER = "ollama-local"


def _user_bago_root() -> Path:
    return Path.home() / ".bago" / "state"


def _config_manager(args: argparse.Namespace) -> Any:
    from config_manager import ConfigManager

    user_root = Path(args.user_bago or str(_user_bago_root()))
    return ConfigManager(state_root=str(user_root))


def _default_provider(cm: Any) -> str:
    return cm.get("default_provider") or _DEFAULT_LOCAL_PROVIDER


def _provider_config(cm: Any, provider: str, create: bool = False) -> dict:
    providers = cm.get("providers", {})
    if create:
        return providers.setdefault(provider, {})
    return providers.get(provider, {})


def _save_providers(cm: Any, providers: dict) -> None:
    cm.set("providers", providers)


def cmd_provider_list(args: argparse.Namespace) -> int:
    cm = _config_manager(args)
    providers = cm.get("providers", {})
    for name, body in sorted(providers.items()):
        print(f"{name}: {json.dumps(body, ensure_ascii=False)}")
    default_model = cm.get(_KEY_DEFAULT_MODEL)
    default_provider = cm.get("default_provider")
    if default_provider:
        print(f"default_provider: {default_provider}")
    if default_model:
        print(f"{_KEY_DEFAULT_MODEL}: {default_model}")
    return 0


def cmd_provider_show(args: argparse.Namespace) -> int:
    cm = _config_manager(args)
    provider = args.provider or _default_provider(cm)
    body = _provider_config(cm, provider)
    print(f"{provider}: {json.dumps(body, ensure_ascii=False)}")
    return 0


def cmd_provider_set_key(args: argparse.Namespace) -> int:
    cm = _config_manager(args)
    provider = args.provider or _default_provider(cm)
    providers = cm.get("providers", {})
    body = providers.setdefault(provider, {})

    key = args.key
    value = args.value
    # Boolean coercion for known toggle keys.
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif _looks_numeric(value):
        value = _coerce_numeric(value)

    body[key] = value
    _save_providers(cm, providers)
    print(f"set {provider}.{key}={json.dumps(value, ensure_ascii=False)}")
    return 0


def cmd_provider_unset_key(args: argparse.Namespace) -> int:
    cm = _config_manager(args)
    provider = args.provider or _default_provider(cm)
    providers = cm.get("providers", {})
    body = providers.get(provider, {})
    key = args.key
    if key in body:
        body.pop(key, None)
        if not body:
            providers.pop(provider, None)
        _save_providers(cm, providers)
        print(f"unset {provider}.{key}")
    else:
        print(f"no key '{key}' in {provider}")
    return 0


def cmd_provider_set_default_model(args: argparse.Namespace) -> int:
    cm = _config_manager(args)
    provider = args.provider or _default_provider(cm)
    providers = cm.get("providers", {})
    body = providers.setdefault(provider, {})
    model = args.model

    # Align both canonical keys so downstream consumers stay consistent.
    body[_KEY_DEFAULT_MODEL] = model
    if _KEY_FALLBACK_MODEL in body:
        body[_KEY_FALLBACK_MODEL] = model

    _save_providers(cm, providers)
    print(f"set {provider}.{_KEY_DEFAULT_MODEL}={model}")
    return 0


def cmd_provider_unset_default_model(args: argparse.Namespace) -> int:
    cm = _config_manager(args)
    provider = args.provider or _default_provider(cm)
    providers = cm.get("providers", {})
    body = providers.get(provider, {})

    changed = False
    for key in (_KEY_DEFAULT_MODEL, _KEY_FALLBACK_MODEL):
        if key in body:
            body.pop(key, None)
            changed = True

    if changed:
        if not body:
            providers.pop(provider, None)
        _save_providers(cm, providers)
        print(f"unset {provider} default model")
    else:
        print(f"no default model set in {provider}")
    return 0


def cmd_provider_enable(args: argparse.Namespace) -> int:
    return _set_enabled(args, True)


def cmd_provider_disable(args: argparse.Namespace) -> int:
    return _set_enabled(args, False)


def _set_enabled(args: argparse.Namespace, enabled: bool) -> int:
    cm = _config_manager(args)
    provider = args.provider or _default_provider(cm)
    providers = cm.get("providers", {})
    body = providers.setdefault(provider, {})
    body[_KEY_ENABLED] = enabled
    _save_providers(cm, providers)
    print(f"set {provider}.{_KEY_ENABLED}={enabled}")
    return 0


# Historical aliases for backwards compatibility.
def cmd_provider_set_fallback(args: argparse.Namespace) -> int:
    args.provider = getattr(args, "provider", None) or _DEFAULT_LOCAL_PROVIDER
    args.key = _KEY_DEFAULT_MODEL
    args.value = args.model
    return cmd_provider_set_default_model(args)


def cmd_provider_remove_fallback(args: argparse.Namespace) -> int:
    args.provider = getattr(args, "provider", None) or _DEFAULT_LOCAL_PROVIDER
    return cmd_provider_unset_default_model(args)


def _looks_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _coerce_numeric(value: str) -> int | float:
    if value.isdigit():
        return int(value)
    return float(value)


def build_subparser(sub: argparse._SubParsersAction) -> None:
    pp = sub.add_parser("provider", help="Provider inspection/patching")
    sp = pp.add_subparsers(dest="provider_cmd", required=False)

    sl = sp.add_parser("list", help="List providers and defaults")
    sl.add_argument("--user-bago", default=None)

    ss = sp.add_parser("show", help="Show a provider configuration")
    ss.add_argument("--user-bago", default=None)
    ss.add_argument("provider", nargs="?", default=None)

    sk = sp.add_parser("set-key", help="Set a provider config key")
    sk.add_argument("--user-bago", default=None)
    sk.add_argument("provider", nargs="?", default=None)
    sk.add_argument("key")
    sk.add_argument("value")

    suk = sp.add_parser("unset-key", help="Unset a provider config key")
    suk.add_argument("--user-bago", default=None)
    suk.add_argument("provider", nargs="?", default=None)
    suk.add_argument("key")

    sdm = sp.add_parser("set-default-model", help="Set the default model for a provider")
    sdm.add_argument("--user-bago", default=None)
    sdm.add_argument("provider", nargs="?", default=None)
    sdm.add_argument("model")

    udm = sp.add_parser("unset-default-model", help="Unset the default model for a provider")
    udm.add_argument("--user-bago", default=None)
    udm.add_argument("provider", nargs="?", default=None)

    se = sp.add_parser("enable", help="Enable a provider")
    se.add_argument("--user-bago", default=None)
    se.add_argument("provider", nargs="?", default=None)

    sd = sp.add_parser("disable", help="Disable a provider")
    sd.add_argument("--user-bago", default=None)
    sd.add_argument("provider", nargs="?", default=None)

    # Aliases
    sf = sp.add_parser("set-fallback", help="Alias for set-default-model (default provider)")
    sf.add_argument("--user-bago", default=None)
    sf.add_argument("--provider", default=None)
    sf.add_argument("model")

    rf = sp.add_parser("remove-fallback", help="Alias for unset-default-model (default provider)")
    rf.add_argument("--user-bago", default=None)
    rf.add_argument("--provider", default=None)


def cmd_provider(args: argparse.Namespace) -> int:
    """Entry point used by launcher.py dispatch table."""
    cmd = getattr(args, "provider_cmd", "list") or "list"
    dispatch = {
        "list": cmd_provider_list,
        "show": cmd_provider_show,
        "set-key": cmd_provider_set_key,
        "unset-key": cmd_provider_unset_key,
        "set-default-model": cmd_provider_set_default_model,
        "unset-default-model": cmd_provider_unset_default_model,
        "enable": cmd_provider_enable,
        "disable": cmd_provider_disable,
        "set-fallback": cmd_provider_set_fallback,
        "remove-fallback": cmd_provider_remove_fallback,
    }
    handler = dispatch.get(cmd)
    if handler is None:
        print(f"unknown provider subcommand: {cmd}")
        return 1
    return handler(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bago")
    sub = parser.add_subparsers(dest="command")
    build_subparser(sub)
    raw = argv if argv is not None else sys.argv[1:]
    # Standalone usage: accept both "provider list" and "list"
    argv = (["provider"] + raw) if raw and raw[0] != "provider" else raw
    args = parser.parse_args(argv)
    if args.command != "provider":
        parser.print_help()
        return 0
    return cmd_provider(args)


if __name__ == "__main__":
    raise SystemExit(main())
