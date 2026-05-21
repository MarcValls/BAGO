"""REPL slash-command dispatch tests."""
from __future__ import annotations

import subprocess

from bago.cmd import cmd


def test_repl_slash_registry_command_dispatches(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="OK\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert cmd("/start", object()) is True
    assert calls, "/start did not dispatch to the BAGO launcher"
    assert calls[0][-1] == "start"


def test_repl_bang_registry_command_dispatches(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, stdout="OK\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert cmd("!restart", object()) is True
    assert calls, "!restart did not dispatch to the BAGO launcher"
    assert calls[0][-1] == "restart"
