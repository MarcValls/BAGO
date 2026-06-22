#!/usr/bin/env python3
"""tests/test_cmd_provider.py -- Evidence for bago provider command.

Anti-hardcoded rule:
- Provider names are resolved from config, not asserted literally except
  when exercising the canonical fallback path.
- Test state lives in a temporary directory and is never written to the
  user's real ~/.bago/state.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[1]
if str(BAGO_ROOT) not in sys.path:
    sys.path.insert(0, str(BAGO_ROOT))
_core_dir = str(BAGO_ROOT / ".bago" / "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

from bago_core.commands import cmd_provider
from config_manager import ConfigManager


def _capture_stdout(handler, args) -> tuple[int, str]:
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        rc = handler(args)
    finally:
        sys.stdout = old_stdout
    return rc, buffer.getvalue()


def _mock_state_root():
    td = tempfile.TemporaryDirectory()
    state_root = Path(td.name) / "state"
    return td, state_root


def _provider_body(state_root: Path, provider: str) -> dict:
    cm = ConfigManager(state_root=str(state_root))
    return cm.get("providers", {}).get(provider, {})


def test_provider_list_includes_defaults():
    """list should resolve defaults from config without hardcoding provider names."""
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("default_provider", "mock-p")
        cm.set("default_model", "mock-model:v1")

        args = argparse.Namespace(user_bago=str(state_root), provider_cmd="list")
        rc, out = _capture_stdout(cmd_provider.cmd_provider_list, args)
        assert rc == 0
        assert "default_provider: mock-p" in out
        assert "default_model: mock-model:v1" in out
    finally:
        td.cleanup()


def test_provider_show_resolves_default_provider():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("default_provider", "mock-p")
        cm.set("providers", {"mock-p": {"enabled": True}})

        args = argparse.Namespace(
            user_bago=str(state_root), provider_cmd="show", provider=None
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_show, args)
        assert rc == 0
        assert "mock-p" in out
    finally:
        td.cleanup()


def test_provider_set_and_show_default_model():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("default_provider", "mock-p")

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="set-default-model",
            provider="mock-p",
            model="mock-model:v1",
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_set_default_model, args)
        assert rc == 0
        assert "mock-p.default_model=mock-model:v1" in out
        assert _provider_body(state_root, "mock-p").get("default_model") == "mock-model:v1"

        args_show = argparse.Namespace(
            user_bago=str(state_root), provider_cmd="show", provider="mock-p"
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_show, args_show)
        assert rc == 0
        assert "mock-model:v1" in out
    finally:
        td.cleanup()


def test_provider_unset_default_model():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("providers", {"mock-p": {"default_model": "x", "enabled": True}})

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="unset-default-model",
            provider="mock-p",
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_unset_default_model, args)
        assert rc == 0
        assert "unset mock-p default model" in out
        assert "default_model" not in _provider_body(state_root, "mock-p")
    finally:
        td.cleanup()


def test_provider_set_key_boolean_and_numeric():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="set-key",
            provider="mock-p",
            key="enabled",
            value="false",
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_set_key, args)
        assert rc == 0
        assert "set mock-p.enabled=false" in out
        assert _provider_body(state_root, "mock-p").get("enabled") is False

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="set-key",
            provider="mock-p",
            key="timeout_seconds",
            value="42",
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_set_key, args)
        assert rc == 0
        assert "set mock-p.timeout_seconds=42" in out
        assert _provider_body(state_root, "mock-p").get("timeout_seconds") == 42
    finally:
        td.cleanup()


def test_provider_unset_key():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("providers", {"mock-p": {"enabled": True, "base_url": "http://example"}})

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="unset-key",
            provider="mock-p",
            key="base_url",
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_unset_key, args)
        assert rc == 0
        assert "unset mock-p.base_url" in out
        assert "base_url" not in _provider_body(state_root, "mock-p")
    finally:
        td.cleanup()


def test_provider_enable_disable():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))

        args = argparse.Namespace(
            user_bago=str(state_root), provider_cmd="enable", provider="mock-p"
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_enable, args)
        assert rc == 0
        assert _provider_body(state_root, "mock-p").get("enabled") is True

        args = argparse.Namespace(
            user_bago=str(state_root), provider_cmd="disable", provider="mock-p"
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_disable, args)
        assert rc == 0
        assert _provider_body(state_root, "mock-p").get("enabled") is False
    finally:
        td.cleanup()


def test_provider_fallback_alias_uses_default_provider():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("default_provider", "ollama-local")

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="set-fallback",
            provider=None,
            model="qwen2.5:1.5b",
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_set_fallback, args)
        assert rc == 0
        assert "ollama-local.default_model=qwen2.5:1.5b" in out
        assert _provider_body(state_root, "ollama-local").get("default_model") == "qwen2.5:1.5b"
    finally:
        td.cleanup()


def test_provider_remove_fallback_alias():
    td, state_root = _mock_state_root()
    try:
        cm = ConfigManager(state_root=str(state_root))
        cm.set("default_provider", "ollama-local")
        cm.set("providers", {"ollama-local": {"default_model": "x"}})

        args = argparse.Namespace(
            user_bago=str(state_root),
            provider_cmd="remove-fallback",
            provider=None,
        )
        rc, out = _capture_stdout(cmd_provider.cmd_provider_remove_fallback, args)
        assert rc == 0
        assert "unset ollama-local default model" in out
        assert "default_model" not in _provider_body(state_root, "ollama-local")
    finally:
        td.cleanup()


def test_provider_dispatch_table():
    # The CLI command is singular "provider" to keep the parser facade thin.
    # The REPL slash command remains plural "/providers" for user ergonomics.
    from bago_core import launcher

    assert "provider" in launcher._DISPATCH_TABLE
    assert launcher._DISPATCH_TABLE["provider"] == "cmd_provider"
    assert "providers" not in launcher._DISPATCH_TABLE


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-only", action="store_true")
    args = parser.parse_args()

    tests = [
        test_provider_list_includes_defaults,
        test_provider_show_resolves_default_provider,
        test_provider_set_and_show_default_model,
        test_provider_unset_default_model,
        test_provider_set_key_boolean_and_numeric,
        test_provider_unset_key,
        test_provider_enable_disable,
        test_provider_fallback_alias_uses_default_provider,
        test_provider_remove_fallback_alias,
        test_provider_dispatch_table,
    ]

    failed = 0
    for fn in tests:
        try:
            fn()
            if not args.fail_only:
                print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {fn.__name__}: {exc}")

    if failed:
        print(f"\n{failed} failed")
        raise SystemExit(1)
    print("\nAll provider tests passed")
