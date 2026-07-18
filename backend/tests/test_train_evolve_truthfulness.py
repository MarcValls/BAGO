from __future__ import annotations

from types import SimpleNamespace
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from commands import cmd_evolve, cmd_train


class _FakeProc:
    def __init__(self, argv):
        self.argv = argv
        self.stdout = iter(["ok\n"])
        self.returncode = 0
        self.killed = False

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True


def _install_popen_spy(monkeypatch, calls):
    def _fake_popen(argv, **kwargs):
        calls.append(argv)
        return _FakeProc(argv)

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)


def test_cmd_evolve_does_not_claim_certification():
    mgr = SimpleNamespace(
        auto_evolve=lambda: {
            "ok": True,
            "total": 4,
            "counts": {"chat": 2, "work": 2},
            "bc": {"ok": False, "reason": "numpy no disponible"},
        }
    )

    result = cmd_evolve(mgr, object(), [])

    assert result["ok"] is True
    assert "sin certificación independiente" in result["message"]
    assert "Autoevolución completada" not in result["message"]


def test_cmd_train_default_uses_novel_phrases(monkeypatch):
    calls: list[list[str]] = []
    _install_popen_spy(monkeypatch, calls)

    mgr = SimpleNamespace()
    result = cmd_train(mgr, object(), [])

    assert result["ok"] is True
    assert len(calls) == 1
    assert calls[0][-1].endswith("test_novel_phrases.py")


def test_cmd_train_all_runs_novel_then_exact(monkeypatch):
    calls: list[list[str]] = []
    _install_popen_spy(monkeypatch, calls)

    mgr = SimpleNamespace()
    result = cmd_train(mgr, object(), ["all"])

    assert result["ok"] is True
    assert len(calls) == 2
    assert calls[0][-1].endswith("test_novel_phrases.py")
    assert calls[1][-1].endswith("test_command_intents.py")


def test_novel_script_emits_three_splits_and_passes():
    proc = subprocess.run(
        ["python", "test_novel_phrases.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).resolve().parents[1]),
    )

    assert proc.returncode == 0
    assert "SPLIT: TRAIN" in proc.stdout
    assert "SPLIT: VAL" in proc.stdout
    assert "SPLIT: TEST" in proc.stdout
    assert "Split test aprobado" in proc.stdout
