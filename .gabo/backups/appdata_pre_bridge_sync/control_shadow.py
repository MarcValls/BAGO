#!/usr/bin/env python3
"""
control_shadow.py — Simulación segura del bus de control compartido.

Inspirado en las técnicas de shadow mode de C:\\bago_true\\.bago\\rl:
- instrumentación del flujo real,
- recomendación paralela sin autoridad,
- logging de transiciones para evaluación posterior.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class ControlShadow:
    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        self.state_dir = self.base_path / ".bago" / "state"
        self.logs_dir = self.base_path / ".bago" / "logs"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / "ui_control_shadow.json"
        self.log_path = self.logs_dir / "ui_control_shadow.jsonl"
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        state = {
            "enabled": True,
            "mode": "shadow",
            "events_logged": 0,
            "updated_at": time.time(),
        }
        self._save_state(state)
        return state

    def _save_state(self, state: dict[str, Any] | None = None) -> None:
        self.state = state or self.state
        self.state["updated_at"] = time.time()
        self.state_path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        mode = self.state.get("mode", "shadow")
        if mode in ("canary", "full"):
            note = "Modo futuro: hoy sigue siendo observador y solo registra trazas como shadow."
        elif mode == "off":
            note = "Simulación desactivada."
        else:
            note = "Modo observador activo: registra recomendaciones sin tomar control."
        return {
            "enabled": bool(self.state.get("enabled", True)),
            "mode": mode,
            "authority": "observer-only",
            "mode_note": note,
            "events_logged": int(self.state.get("events_logged", 0)),
            "log_path": str(self.log_path),
            "state_path": str(self.state_path),
        }

    def configure(self, *, enabled: bool | None = None, mode: str | None = None) -> dict[str, Any]:
        if enabled is not None:
            self.state["enabled"] = bool(enabled)
        if mode is not None:
            if mode not in ("off", "shadow", "canary", "full"):
                raise ValueError("Modo inválido. Usa off|shadow|canary|full")
            self.state["mode"] = mode
        self._save_state()
        return self.status()

    def recommend(self, mgr, action_kind: str, payload: dict[str, Any], pre_state: dict[str, Any]) -> dict[str, Any]:
        recommendation: dict[str, Any] = {"kind": "observe", "reason": "sin recomendación"}

        if action_kind in ("chat", "command"):
            candidates = [(p["name"], m) for p in mgr.available_providers() for m in p["models"]]
            if candidates:
                fingerprint = ""
                if action_kind == "chat":
                    fingerprint = mgr.rl_feedback.fingerprint_for(str(payload.get("message", "")))
                elif action_kind == "command":
                    fingerprint = mgr.rl_feedback.fingerprint_for(str(payload.get("command", "")))
                best = mgr.rl_pref.best(fingerprint=fingerprint, candidates=candidates)
                if best:
                    recommendation = {
                        "kind": "provider-model",
                        "provider": best[0],
                        "model": best[1],
                        "reason": "preferencia RL observada",
                    }

        if not pre_state.get("health", {}).get("ok", True):
            recommendation = {"kind": "command", "command": "/providers", "reason": "salud degradada"}
        elif payload.get("command") == "/allow":
            recommendation = {"kind": "command", "command": "/allow", "reason": "tools pendientes"}

        return recommendation

    def _reward(self, *, ok: bool, elapsed_ms: float, post_state: dict[str, Any]) -> float:
        reward = 1.0 if ok else -1.0
        if elapsed_ms < 500:
            reward += 0.1
        if post_state.get("health", {}).get("ok"):
            reward += 0.1
        return round(reward, 3)

    def log_event(
        self,
        *,
        mgr,
        channel: str,
        action_kind: str,
        payload: dict[str, Any],
        pre_state: dict[str, Any],
        post_state: dict[str, Any],
        result: dict[str, Any],
        elapsed_ms: float,
    ) -> dict[str, Any]:
        if not self.state.get("enabled", True) or self.state.get("mode") == "off":
            return {}

        recommendation = self.recommend(mgr, action_kind, payload, pre_state)
        reward = self._reward(ok=bool(result.get("ok", True)), elapsed_ms=elapsed_ms, post_state=post_state)
        event = {
            "id": int(self.state.get("events_logged", 0)) + 1,
            "timestamp": time.time(),
            "mode": self.state.get("mode", "shadow"),
            "channel": channel,
            "action_kind": action_kind,
            "payload": payload,
            "recommended": recommendation,
            "actual": {
                "provider": post_state.get("provider"),
                "model": post_state.get("model"),
                "command": payload.get("command"),
            },
            "reward": reward,
            "elapsed_ms": round(elapsed_ms, 2),
            "pre_state": {
                "provider": pre_state.get("provider"),
                "model": pre_state.get("model"),
                "messages": pre_state.get("messages"),
            },
            "post_state": {
                "provider": post_state.get("provider"),
                "model": post_state.get("model"),
                "messages": post_state.get("messages"),
            },
            "result_ok": bool(result.get("ok", True)),
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.state["events_logged"] = int(self.state.get("events_logged", 0)) + 1
        self._save_state()
        return event

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        events = []
        for line in lines[-limit:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events


def _run_tests() -> int:
    import tempfile

    class DummyFeedback:
        @staticmethod
        def fingerprint_for(text: str) -> str:
            return text[:8]

    class DummyPref:
        @staticmethod
        def best(fingerprint: str, candidates: list[tuple[str, str]]):
            return candidates[0] if candidates else None

    class DummyMgr:
        rl_feedback = DummyFeedback()
        rl_pref = DummyPref()

        @staticmethod
        def available_providers():
            return [{"name": "mock", "models": ["model-1"]}]

    with tempfile.TemporaryDirectory() as td:
        shadow = ControlShadow(base_path=td)
        assert shadow.status()["mode"] == "shadow"
        assert shadow.status()["authority"] == "observer-only"
        configured = shadow.configure(mode="shadow", enabled=True)
        assert configured["enabled"] is True
        event = shadow.log_event(
            mgr=DummyMgr(),
            channel="terminal",
            action_kind="chat",
            payload={"message": "hola"},
            pre_state={"provider": "mock", "model": "model-1", "messages": 0, "health": {"ok": True}},
            post_state={"provider": "mock", "model": "model-1", "messages": 2, "health": {"ok": True}},
            result={"ok": True},
            elapsed_ms=120,
        )
        assert event["recommended"]["provider"] == "mock"
        assert len(shadow.recent_events()) == 1
        print("control_shadow.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
