"""diagnostics.py — estado de cuarentena y capacidades activas.

La ruta `/integrations/pi/status` consume `snapshot()` y devuelve
exactamente lo que el bridge está autorizado a hacer, sin descubrir
ningún dato de PI. En Fase 0 todo está en `disabled` o `false`.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import BRIDGE_PROTOCOL_VERSION, QUARANTINE_PHASE, is_quarantined
from .config import PiBridgeConfig


@dataclass(frozen=True)
class BridgeStatus:
    protocol_version: str
    quarantine_phase: int
    quarantined: bool
    config: dict[str, Any]
    runtime: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, bool] = field(default_factory=dict)
    kill_switch: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_lockfile_hash(integrations_dir: Path) -> str:
    lock = integrations_dir / "sidecar" / "package-lock.json"
    if not lock.exists():
        return ""
    try:
        import hashlib

        return hashlib.sha256(lock.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def snapshot(config: PiBridgeConfig, integrations_dir: Path) -> BridgeStatus:
    runtime = {
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
        "bago_pi_enabled_env": os.environ.get("BAGO_PI_BRIDGE_ENABLED", "unset"),
        "bago_pi_max_phase_env": os.environ.get("BAGO_PI_MAX_PHASE", "unset"),
        "lockfile_hash": _read_lockfile_hash(integrations_dir),
    }
    capabilities = {
        "infer": config.max_phase >= 1 and config.enabled,
        "read_only_tools": config.max_phase >= 2 and config.enabled,
        "agent_runner": config.max_phase >= 3 and config.enabled,
        "mutations": config.allow_mutations,
        "skills": config.allow_skills,
        "extensions": config.allow_extensions,
        "packages": config.allow_packages,
        "native_tools": config.allow_native_tools,
        "process_spawn": config.allow_process_spawn,
        "pi_auth_store": config.allow_pi_auth_store,
        "pi_sessions": config.allow_pi_sessions,
        "pi_settings": config.allow_pi_settings,
        "pi_system_prompt_discovery": config.allow_pi_system_prompt_discovery,
    }
    kill_switch = {
        "global": not config.enabled,
        "phase_lock": config.max_phase < 3,
        "fail_on_provider_drift": config.fail_on_provider_drift,
        "fail_on_unknown_event": config.fail_on_unknown_event,
    }
    return BridgeStatus(
        protocol_version=BRIDGE_PROTOCOL_VERSION,
        quarantine_phase=QUARANTINE_PHASE,
        quarantined=is_quarantined(),
        config=config.to_dict(),
        runtime=runtime,
        capabilities=capabilities,
        kill_switch=kill_switch,
    )


__all__ = ["BridgeStatus", "snapshot"]
