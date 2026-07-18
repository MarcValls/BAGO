from __future__ import annotations

import argparse
import importlib
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

cmd_chat = importlib.import_module("bago_core.commands.cmd_chat")  # noqa: E402
from bago_core.parsers import build_parser  # noqa: E402


class _DummyRepl:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.ran = False

    def run(self) -> None:
        self.ran = True


def test_cmd_chat_autostarts_ollama_for_local(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(cmd_chat, "_ensure_ollama_local_ready", lambda base_path: calls.append(base_path) or (True, "Ollama arrancado en 127.0.0.1:11434"))
    monkeypatch.setattr(cmd_chat, "_start_monitor_bg", lambda base_path: None)
    monkeypatch.setattr(cmd_chat, "_resolve_state_root", lambda: tmp_path / "state")
    monkeypatch.setitem(sys.modules, "repl", types.SimpleNamespace(BagoREPL=_DummyRepl))
    monkeypatch.setitem(sys.modules, "system_prompt", types.SimpleNamespace(get_system_prompt=lambda: ""))

    args = argparse.Namespace(
        provider="ollama-local",
        model="llama3.2:3b",
        base_path=str(tmp_path),
        active_bridges=[],
        llm_bridges=[],
        no_monitor=True,
    )

    assert cmd_chat.cmd_chat(args) == 0
    assert calls == [str(tmp_path)]


def test_cmd_chat_skips_autostart_for_cloud(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(cmd_chat, "_ensure_ollama_local_ready", lambda base_path: calls.append(base_path) or (True, "Ollama arrancado"))
    monkeypatch.setattr(cmd_chat, "_start_monitor_bg", lambda base_path: None)
    monkeypatch.setattr(cmd_chat, "_resolve_state_root", lambda: tmp_path / "state")
    monkeypatch.setitem(sys.modules, "repl", types.SimpleNamespace(BagoREPL=_DummyRepl))
    monkeypatch.setitem(sys.modules, "system_prompt", types.SimpleNamespace(get_system_prompt=lambda: ""))

    args = argparse.Namespace(
        provider="openrouter",
        model="gpt-4o",
        base_path=str(tmp_path),
        active_bridges=[],
        llm_bridges=[],
        no_monitor=True,
    )

    assert cmd_chat.cmd_chat(args) == 0
    assert calls == []


def test_parser_exposes_ollama_autostart_flag():
    parser = build_parser("4.8.0", "C:/tmp", "ollama-local", "llama3.2:3b")
    chat_args = parser.parse_args(["chat", "--no-ollama-autostart"])
    llm_args = parser.parse_args(["llm", "start", "--provider", "ollama-local", "--no-ollama-autostart"])

    assert getattr(chat_args, "no_ollama_autostart", False) is True
    assert getattr(llm_args, "no_ollama_autostart", False) is True


def test_llm_start_disables_extra_startup_prompt(monkeypatch, tmp_path):
    captured = {}

    def fake_cmd_chat(args):
        captured["startup_prompt"] = getattr(args, "startup_prompt", None)
        return 0

    monkeypatch.setattr(cmd_chat, "cmd_chat", fake_cmd_chat)

    args = argparse.Namespace(
        llm_action="start",
        llm_provider="ollama-local",
        llm_model="llama3.2:3b",
        llm_bridges=[],
        include_experimental=False,
        allow_unconfigured=False,
        persist_default=False,
        dry_run=False,
        no_monitor=True,
        no_ollama_autostart=True,
        base_path=str(tmp_path),
    )

    assert cmd_chat.cmd_llm(args) == 0
    assert captured["startup_prompt"] is False
