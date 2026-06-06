from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .bago_true_bridge import detect_bago_true
except ImportError:
    from bago_true_bridge import detect_bago_true

DEFAULT_MODE = "shadow"
ALLOWED_MODES = {"off", "shadow"}

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class RLBridge:
    """Shadow-first RL bridge. It records observations; it never executes actions."""

    _CREATED_VERSION = "4.0.0"  # Version en que fue creado este archivo

    def __init__(self, base_path: str | Path, true_root: str | Path | None = None) -> None:
        self.base_path = Path(base_path)
        self.true_root = true_root
        self.state_dir = self.base_path / ".bago" / "state"
        self.state_file = self.state_dir / "rl_bridge.json"
        self.transition_log = self.state_dir / "rl_transitions.jsonl"

    def _read_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {
                "mode": DEFAULT_MODE,
                "enabled": True,
                "can_execute": False,
                "updated_at": None,
            }
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        mode = data.get("mode") if data.get("mode") in ALLOWED_MODES else DEFAULT_MODE
        return {
            "mode": mode,
            "enabled": mode == "shadow",
            "can_execute": False,
            "updated_at": data.get("updated_at"),
        }

    def _write_state(self, mode: str) -> dict[str, Any]:
        if mode not in ALLOWED_MODES:
            raise ValueError(f"unsupported RL mode: {mode}")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": mode,
            "enabled": mode == "shadow",
            "can_execute": False,
            "updated_at": _utc_now(),
        }
        self.state_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload

    def append_transition(self, event: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": _utc_now(),
            "can_execute": False,
            **event,
        }
        with self.transition_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def status(self) -> dict[str, Any]:
        state = self._read_state()
        external = detect_bago_true(self.true_root)
        return {
            **state,
            "state_file": str(self.state_file),
            "transition_log": str(self.transition_log),
            "external_rl": external["rl"],
            "rules": {
                "executes_actions": False,
                "default_mode": DEFAULT_MODE,
                "allowed_modes": sorted(ALLOWED_MODES),
            },
        }

    def shadow(self, enabled: bool) -> dict[str, Any]:
        mode = "shadow" if enabled else "off"
        state = self._write_state(mode)
        self.append_transition({
            "kind": "mode_change",
            "mode": mode,
            "status": "enabled" if enabled else "disabled",
            "source": "cli",
        })
        return self.status() | state

def render_status(status: dict[str, Any]) -> str:
    external = status.get("external_rl", {})
    lines = [
        "BAGO RL STATUS",
        "-" * 40,
        f"mode       : {status['mode']}",
        f"enabled    : {'yes' if status['enabled'] else 'no'}",
        f"can execute: {'yes' if status['can_execute'] else 'no'}",
        f"external rl: {'available' if external.get('available') else 'unavailable'}",
        f"shadow src : {'yes' if external.get('shadow_adapter') else 'no'}",
        f"policy src : {'yes' if external.get('policies_py') else 'no'}",
        f"state file : {status['state_file']}",
        f"log file   : {status['transition_log']}",
        "rule       : RL observes/recommends only; v4 decides",
    ]
    return "\n".join(lines)
