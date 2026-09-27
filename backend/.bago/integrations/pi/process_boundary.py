"""process_boundary.py — frontera de proceso con el sidecar.

Construye el entorno mínimo para el sidecar (allowlist explícita,
HOME efímero, cwd fijado, timeout, kill switch) y nunca hereda
`os.environ` del backend. El proceso se materializa únicamente en el owner
registrado del `ExecutionGateway`.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .errors import BridgeIntegrityMismatch, BridgeTimeout, ProcessCapabilityDenied


# Variables de entorno que el sidecar puede ver. Cualquier clave fuera
# de esta allowlist es removida.
ALLOWED_ENV_KEYS: frozenset[str] = frozenset(
    {
        "PATH",
        "SystemRoot",  # Windows
        "SYSTEMROOT",  # alias
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "TMP",
        "TEMP",
        "TMPDIR",
        "BAGO_BRIDGE_CORRELATION_ID",
        "BAGO_BRIDGE_EXECUTION_ID",
        "BAGO_BRIDGE_PHASE",
    }
)


@dataclass
class BoundarySpec:
    """Solicitud de proceso; el owner materializa HOME al despachar."""

    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    timeout_seconds: float
    home_parent: str
    integrity: dict[str, str] = field(default_factory=dict)


def _filter_env(
    extra: Mapping[str, str] | None = None,
    *,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Devuelve un dict con sólo las claves permitidas + extras explícitos.

    Los extras explícitos **no** deben incluir secretos. La regla es
    que `extra` se evalúa como código de programador, no como entrada
    de usuario final.

    `source` permite pasar un mapping arbitrario (útil en tests); por
    defecto se lee `os.environ`.
    """
    base_source: Mapping[str, str] = source if source is not None else os.environ
    base: dict[str, str] = {}
    for key in ALLOWED_ENV_KEYS:
        value = base_source.get(key)
        if value is None:
            continue
        # Bloquea explícitamente variables PI no declaradas.
        if key.startswith("PI_") and key not in {
            "BAGO_BRIDGE_CORRELATION_ID",
            "BAGO_BRIDGE_EXECUTION_ID",
            "BAGO_BRIDGE_PHASE",
        }:
            continue
        base[key] = value
    if extra:
        for key, value in extra.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            if key in base:
                continue
            if key.startswith("PI_") and key not in {
                "BAGO_BRIDGE_CORRELATION_ID",
                "BAGO_BRIDGE_EXECUTION_ID",
                "BAGO_BRIDGE_PHASE",
            }:
                # Bloquea cualquier PI_ no explícitamente permitida.
                continue
            base[key] = value
    return base


def build_boundary(
    *,
    argv: Sequence[str],
    cwd: str,
    timeout_seconds: float,
    correlation_id: str,
    execution_id: str,
    extra_env: Mapping[str, str] | None = None,
    parent_home: Path | None = None,
    integrity: Mapping[str, str] | None = None,
) -> BoundarySpec:
    if not argv:
        raise ProcessCapabilityDenied("argv is empty")
    if timeout_seconds <= 0 or timeout_seconds > 600:
        raise ProcessCapabilityDenied(
            "timeout_seconds out of range",
            details={"value": timeout_seconds},
        )
    if not cwd:
        raise ProcessCapabilityDenied("cwd is empty")
    if not Path(cwd).exists():
        raise ProcessCapabilityDenied("cwd missing", details={"cwd": cwd})

    home_root = (parent_home or Path(tempfile.gettempdir())).expanduser().resolve()
    if not home_root.is_dir():
        raise ProcessCapabilityDenied("ephemeral HOME parent is missing", details={"path": str(home_root)})
    env = _filter_env(
        {
            "BAGO_BRIDGE_CORRELATION_ID": correlation_id,
            "BAGO_BRIDGE_EXECUTION_ID": execution_id,
            **(dict(extra_env) if extra_env else {}),
        }
    )
    return BoundarySpec(
        argv=tuple(argv),
        cwd=str(Path(cwd).resolve()),
        env=env,
        timeout_seconds=float(timeout_seconds),
        home_parent=str(home_root),
        integrity=dict(integrity or {}),
    )


def verify_integrity(spec: BoundarySpec, sidecar_artifact_hash: str) -> None:
    expected = spec.integrity.get("sidecar_artifact_hash")
    if expected and expected != sidecar_artifact_hash:
        raise BridgeIntegrityMismatch(
            "sidecar artifact hash mismatch",
            details={"expected": expected, "effective": sidecar_artifact_hash},
        )


def run_sidecar(
    spec: BoundarySpec,
    *,
    stdin_payload: str | None = None,
    sidecar_artifact_hash: str = "",
    cancel_token: Any | None = None,
) -> subprocess.CompletedProcess:
    """Resolve PI process authority in ExecutionGateway before sidecar spawn."""
    if len(spec.argv) != 2:
        raise ProcessCapabilityDenied("PI provider sidecar requires exactly node and the canonical script")
    from execution_gateway import ExecutionContext, ExecutionGateway, ExecutionGatewayError
    from execution_request import build_execution_request

    try:
        sidecar_path = Path(spec.argv[1]).expanduser().resolve(strict=True)
        digest = hashlib.sha256(sidecar_path.read_bytes()).hexdigest()
        expected_digest = sidecar_artifact_hash or str(spec.integrity.get("sidecar_artifact_hash") or "")
        if expected_digest and expected_digest != digest:
            raise BridgeIntegrityMismatch(
                "sidecar artifact hash mismatch",
                details={"expected": expected_digest, "effective": digest},
            )
        if spec.integrity.get("sidecar_artifact_hash"):
            verify_integrity(spec, digest)

        session_id = str(spec.env.get("BAGO_BRIDGE_CORRELATION_ID") or "")
        execution_id = str(spec.env.get("BAGO_BRIDGE_EXECUTION_ID") or "")
        request = build_execution_request(
            effect_id="process.sidecar.execute",
            actor_kind="server",
            principal_id="bago-pi-provider",
            session_id=session_id,
            source_surface="server.pi.sidecar",
            target={
                "operation": "provider-sidecar",
                "node_path": spec.argv[0],
                "sidecar_path": str(sidecar_path),
                "sidecar_sha256": digest,
                "cwd": spec.cwd,
                "timeout_seconds": spec.timeout_seconds,
                "home_parent": spec.home_parent,
            },
            arguments={
                "stdin_payload": str(stdin_payload or ""),
                "environment": dict(spec.env),
                "execution_id": execution_id,
            },
            scope="external",
        )
        result, _authorization = ExecutionGateway().execute_server_owned(
            request=request,
            context=ExecutionContext(services={"_pi_cancel_token": cancel_token}),
        )
        if not isinstance(result, dict) or result.get("effect_id") != request.effect_id or result.get("executed") is not True:
            raise ProcessCapabilityDenied("ExecutionGateway did not return a PI process receipt")
        return subprocess.CompletedProcess(
            args=list(spec.argv),
            returncode=int(result.get("exit_code", 1)),
            stdout=str(result.get("stdout") or ""),
            stderr=str(result.get("stderr") or ""),
        )
    except ExecutionGatewayError as exc:
        if getattr(exc, "code", "") == "pi_sidecar_timeout":
            raise BridgeTimeout("sidecar timeout", details={"timeout_seconds": spec.timeout_seconds}) from exc
        raise ProcessCapabilityDenied("ExecutionGateway rejected PI sidecar", details={"code": getattr(exc, "code", "")}) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProcessCapabilityDenied("PI sidecar dispatch failed", details={"error": str(exc)}) from exc


__all__ = [
    "ALLOWED_ENV_KEYS",
    "BoundarySpec",
    "build_boundary",
    "verify_integrity",
    "run_sidecar",
    "_filter_env",
]
