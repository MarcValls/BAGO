"""config.py — carga de configuración del BagoPiBridge.

Lee la sección `integrations.pi` desde el config canónico
`backend/.bago/config.json`. Si el bloque no existe, aplica defaults de
cuarentena (Fase 0). Cualquier flag desconocido provoca rechazo
fail-closed. Los valores son inmutables una vez cargados.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import BRIDGE_PROTOCOL_VERSION, QUARANTINE_PHASE
from .errors import BridgeError


DEFAULT_CONFIG_PATH_CANDIDATES: tuple[str, ...] = (
    "backend/.bago/config.json",
    ".bago/config.json",
)

# Flags permitidos. Cualquier clave adicional provoca `UnknownConfigFlag`.
_ALLOWED_FLAGS: frozenset[str] = frozenset(
    {
        "enabled",
        "quarantine_mode",
        "max_phase",
        "allow_pi_auth_store",
        "allow_pi_sessions",
        "allow_pi_settings",
        "allow_pi_system_prompt_discovery",
        "allow_skills",
        "allow_extensions",
        "allow_packages",
        "allow_native_tools",
        "allow_process_spawn",
        "allow_mutations",
        "network_mode",
        "fail_on_provider_drift",
        "fail_on_unknown_event",
        "sidecar_lockfile_hash",
    }
)

# Valores permitidos para flags discretos.
_ALLOWED_NETWORK_MODES: frozenset[str] = frozenset(
    {"none", "provider_endpoints_only", "disabled"}
)


def _quarantine_defaults() -> dict[str, Any]:
    return {
        "enabled": False,
        "quarantine_mode": True,
        "max_phase": 0,
        "allow_pi_auth_store": False,
        "allow_pi_sessions": False,
        "allow_pi_settings": False,
        "allow_pi_system_prompt_discovery": False,
        "allow_skills": False,
        "allow_extensions": False,
        "allow_packages": False,
        "allow_native_tools": False,
        "allow_process_spawn": False,
        "allow_mutations": False,
        "network_mode": "none",
        "fail_on_provider_drift": True,
        "fail_on_unknown_event": True,
    }


@dataclass(frozen=True)
class PiBridgeConfig:
    """Config inmutable del bridge."""

    raw: dict[str, Any] = field(default_factory=dict)
    enabled: bool = False
    quarantine_mode: bool = True
    max_phase: int = 0
    allow_pi_auth_store: bool = False
    allow_pi_sessions: bool = False
    allow_pi_settings: bool = False
    allow_pi_system_prompt_discovery: bool = False
    allow_skills: bool = False
    allow_extensions: bool = False
    allow_packages: bool = False
    allow_native_tools: bool = False
    allow_process_spawn: bool = False
    allow_mutations: bool = False
    network_mode: str = "none"
    fail_on_provider_drift: bool = True
    fail_on_unknown_event: bool = True
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "quarantine_mode": self.quarantine_mode,
            "max_phase": self.max_phase,
            "allow_pi_auth_store": self.allow_pi_auth_store,
            "allow_pi_sessions": self.allow_pi_sessions,
            "allow_pi_settings": self.allow_pi_settings,
            "allow_pi_system_prompt_discovery": self.allow_pi_system_prompt_discovery,
            "allow_skills": self.allow_skills,
            "allow_extensions": self.allow_extensions,
            "allow_packages": self.allow_packages,
            "allow_native_tools": self.allow_native_tools,
            "allow_process_spawn": self.allow_process_spawn,
            "allow_mutations": self.allow_mutations,
            "network_mode": self.network_mode,
            "fail_on_provider_drift": self.fail_on_provider_drift,
            "fail_on_unknown_event": self.fail_on_unknown_event,
            "source_path": self.source_path,
            "protocol_version": BRIDGE_PROTOCOL_VERSION,
            "quarantine_phase": QUARANTINE_PHASE,
        }


def _resolve_config_path(start: Path | None) -> Path | None:
    base = start or Path.cwd().resolve()
    for candidate in DEFAULT_CONFIG_PATH_CANDIDATES:
        path = base / candidate
        if path.exists():
            return path
    return None


def _load_raw_config(path: Path | None) -> tuple[dict[str, Any], str]:
    if path is None or not path.exists():
        return _quarantine_defaults(), ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BridgeError(
            "config json invalid",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise BridgeError(
            "config root must be an object",
            details={"path": str(path)},
        )
    return data, str(path)


def _extract_section(raw: dict[str, Any]) -> dict[str, Any]:
    section = raw.get("integrations")
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise BridgeError("integrations section must be an object")
    pi_section = section.get("pi")
    if pi_section is None:
        return {}
    if not isinstance(pi_section, dict):
        raise BridgeError("integrations.pi must be an object")
    return pi_section


def load_config(start: Path | None = None) -> PiBridgeConfig:
    """Carga y valida la configuración del bridge.

    - Defaults de cuarentena si el archivo no existe o si la sección
      `integrations.pi` no está presente.
    - Falla con `BridgeError` ante claves desconocidas o valores no
      permitidos (fail-closed).
    """
    path = _resolve_config_path(start)
    raw, source = _load_raw_config(path)
    section = _extract_section(raw)

    unknown = sorted(key for key in section if key not in _ALLOWED_FLAGS)
    if unknown:
        raise BridgeError(
            "unknown config flag",
            details={"flags": unknown},
        )

    merged = _quarantine_defaults()
    merged.update(section)

    if not isinstance(merged["max_phase"], int) or not 0 <= merged["max_phase"] <= 4:
        raise BridgeError(
            "max_phase must be int 0..4",
            details={"value": merged["max_phase"]},
        )
    if merged["network_mode"] not in _ALLOWED_NETWORK_MODES:
        raise BridgeError(
            "network_mode not allowed",
            details={"value": merged["network_mode"]},
        )

    # Si el env pide Fase 0 estricta, forzar.
    forced = os.environ.get("BAGO_PI_MAX_PHASE", "").strip()
    if forced:
        try:
            merged["max_phase"] = int(forced)
        except ValueError as exc:
            raise BridgeError(
                "BAGO_PI_MAX_PHASE invalid",
                details={"value": forced},
            ) from exc

    return PiBridgeConfig(
        raw=merged,
        source_path=source,
        enabled=bool(merged["enabled"]),
        quarantine_mode=bool(merged["quarantine_mode"]),
        max_phase=int(merged["max_phase"]),
        allow_pi_auth_store=bool(merged["allow_pi_auth_store"]),
        allow_pi_sessions=bool(merged["allow_pi_sessions"]),
        allow_pi_settings=bool(merged["allow_pi_settings"]),
        allow_pi_system_prompt_discovery=bool(merged["allow_pi_system_prompt_discovery"]),
        allow_skills=bool(merged["allow_skills"]),
        allow_extensions=bool(merged["allow_extensions"]),
        allow_packages=bool(merged["allow_packages"]),
        allow_native_tools=bool(merged["allow_native_tools"]),
        allow_process_spawn=bool(merged["allow_process_spawn"]),
        allow_mutations=bool(merged["allow_mutations"]),
        network_mode=str(merged["network_mode"]),
        fail_on_provider_drift=bool(merged["fail_on_provider_drift"]),
        fail_on_unknown_event=bool(merged["fail_on_unknown_event"]),
    )


__all__ = [
    "PiBridgeConfig",
    "load_config",
    "DEFAULT_CONFIG_PATH_CANDIDATES",
]
