"""process_boundary.py — frontera de proceso con el sidecar.

Construye el entorno mínimo para el sidecar (allowlist explícita,
HOME efímero, cwd fijado, timeout, kill switch) y nunca hereda
`os.environ` del backend. La función principal `spawn_sidecar` está
pensada para ser sustituida por un wrapper que use `subprocess.Popen`
real; aquí exponemos una versión abstracta y una implementación
`LocalPopen` que sólo arranca un proceso de prueba inerte.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
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
        "NODE_OPTIONS",
        "BAGO_BRIDGE_CORRELATION_ID",
        "BAGO_BRIDGE_EXECUTION_ID",
        "BAGO_BRIDGE_PHASE",
    }
)


@dataclass
class BoundarySpec:
    """Especificación de la frontera de proceso del sidecar.

    Mantiene viva la referencia a `tempfile.TemporaryDirectory` para
    que el directorio efímero `HOME` no se limpie mientras el sidecar
    está en ejecución. La limpieza ocurre al destruir el `BoundarySpec`.
    """

    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    timeout_seconds: float
    home_dir: str
    integrity: dict[str, str] = field(default_factory=dict)
    _home_handle: "object | None" = field(default=None, repr=False, compare=False)


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


def _make_ephemeral_home(parent: Path | None = None) -> tempfile.TemporaryDirectory:
    base = parent or Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="bago-pi-home-", dir=str(base))


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

    tmp_home = _make_ephemeral_home(parent_home)
    home_name = tmp_home.name
    env = _filter_env(
        {
            "HOME": home_name,
            "USERPROFILE": home_name,  # Windows
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
        home_dir=home_name,
        integrity=dict(integrity or {}),
        _home_handle=tmp_home,
    )


def verify_integrity(spec: BoundarySpec, sidecar_artifact_hash: str) -> None:
    expected = spec.integrity.get("sidecar_artifact_hash")
    if expected and expected != sidecar_artifact_hash:
        raise BridgeIntegrityMismatch(
            "sidecar artifact hash mismatch",
            details={"expected": expected, "effective": sidecar_artifact_hash},
        )


def _run_with_timeout(
    spec: BoundarySpec, stdin_payload: str | None = None
) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.Popen(
            list(spec.argv),
            cwd=spec.cwd,
            env=spec.env,
            stdin=subprocess.PIPE if stdin_payload is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise ProcessCapabilityDenied(
            "sidecar binary not found",
            details={"argv": list(spec.argv), "error": str(exc)},
        ) from exc
    try:
        stdout, stderr = proc.communicate(input=stdin_payload, timeout=spec.timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        raise BridgeTimeout(
            "sidecar timeout",
            details={"timeout_seconds": spec.timeout_seconds},
        ) from exc
    return subprocess.CompletedProcess(
        args=list(spec.argv),
        returncode=proc.returncode,
        stdout=stdout or "",
        stderr=stderr or "",
    )


def run_sidecar(
    spec: BoundarySpec,
    *,
    stdin_payload: str | None = None,
    sidecar_artifact_hash: str = "",
) -> subprocess.CompletedProcess:
    """Lanza el sidecar. Valida integridad si se proporciona hash."""
    if sidecar_artifact_hash:
        verify_integrity(spec, sidecar_artifact_hash)
    return _run_with_timeout(spec, stdin_payload)


__all__ = [
    "ALLOWED_ENV_KEYS",
    "BoundarySpec",
    "build_boundary",
    "verify_integrity",
    "run_sidecar",
    "_filter_env",
]
