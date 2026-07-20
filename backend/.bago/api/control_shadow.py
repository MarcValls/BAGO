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
import warnings
from pathlib import Path
from typing import Any


ALLOWED_MODES = {"off", "shadow"}

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class ControlShadow:
    def __init__(
        self,
        base_path: str | None = None,
        state_root: str | None = None,
    ):
        """Construye el ControlShadow.

        Args:
            base_path: ruta del proyecto del usuario (LEGACY, deprecated en v0.3).
                Si se pasa, las rutas se computan como base_path/.bago/{state,logs}.
                Esto contamina el workspace del usuario; solo se mantiene para
                backward compat con código que aún no pasa state_root.
            state_root: ruta canónica de estado del backend (recomendado en v0.3+).
                Si se pasa, los archivos se crean en state_root/ui_control_shadow/
                y state_root/logs/. Resuelto por resolve_state_root() en api_state.

        Prioridad:
            1. Si state_root está presente → usarlo (CANON).
            2. Si solo base_path → usarlo con DEPRECATION WARNING.
            3. Si ninguno → fallback a resolve_state_root() para coherencia.
        """
        if state_root is not None:
            # Camino canónico (v0.3+)
            self.base_path = None
            self.state_dir = Path(state_root) / "ui_control_shadow"
            self.logs_dir = Path(state_root) / "logs"
        elif base_path is not None:
            # Camino legacy (deprecado pero funcional)
            warnings.warn(
                "ControlShadow(base_path=...) está deprecado en v0.3; "
                "pasa state_root= explícitamente. En v0.4 se eliminará.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.base_path = Path(base_path or os.getcwd())
            self.state_dir = self.base_path / ".bago" / "state"
            self.logs_dir = self.base_path / ".bago" / "logs"
        else:
            # Fallback canónico via api_state
            from api_state import resolve_state_root
            self.base_path = None
            _root = resolve_state_root(None)  # type: ignore[arg-type]
            self.state_dir = _root / "ui_control_shadow"
            self.logs_dir = _root / "logs"
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
        if mode not in ALLOWED_MODES:
            mode = "shadow"
        if mode == "off":
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
            if mode not in ALLOWED_MODES:
                raise ValueError(
                    "Modo bloqueado. Solo off|shadow están autorizados; "
                    "canary/full requieren evidencia y un gate de promoción explícito."
                )
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
        try:
            shadow.configure(mode="canary")
        except ValueError as exc:
            assert "gate de promoción" in str(exc)
        else:
            raise AssertionError("canary no puede habilitarse sin gate")
        assert shadow.status()["mode"] == "shadow"
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

    # T1 v0.3 — test de humo: state_root canónico (no contamina proyecto del usuario)
    with tempfile.TemporaryDirectory() as state_root_td:
        state_root = Path(state_root_td)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            # state_root explícito → no debe emitir DeprecationWarning
            shadow = ControlShadow(state_root=str(state_root))
        assert shadow.base_path is None, "state_root canónico debe anular base_path"
        assert shadow.state_dir == state_root / "ui_control_shadow", f"state_dir: {shadow.state_dir}"
        assert shadow.logs_dir == state_root / "logs", f"logs_dir: {shadow.logs_dir}"
        assert shadow.state_path.exists(), "state_path debe existir tras __init__"
        # Verificar que NO se escribió en un subdirectorio .bago/ del proyecto
        assert not (state_root / ".bago").exists(), "No debe haber .bago/ en state_root"

    # T1 v0.3 — test de humo: base_path legacy sigue funcionando con DeprecationWarning
    with tempfile.TemporaryDirectory() as project_td:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            shadow = ControlShadow(base_path=project_td)
            assert any(issubclass(x.category, DeprecationWarning) for x in w), \
                "base_path debe emitir DeprecationWarning"
        assert shadow.base_path == Path(project_td)
        assert shadow.state_dir == Path(project_td) / ".bago" / "state"
        assert shadow.logs_dir == Path(project_td) / ".bago" / "logs"

        print("control_shadow.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
