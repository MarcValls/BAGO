"""Tests del process_boundary."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from integrations.pi.errors import (
    BridgeIntegrityMismatch,
    BridgeTimeout,
    ProcessCapabilityDenied,
)
from integrations.pi.process_boundary import (
    ALLOWED_ENV_KEYS,
    BoundarySpec,
    build_boundary,
    run_sidecar,
    verify_integrity,
    _filter_env,
)


def test_filter_env_blocks_pi_prefix() -> None:
    base = {
        "PATH": "/usr/bin",
        "PI_AUTH_TOKEN": "secret",
        "PI_CUSTOM": "evil",
        "BAGO_BRIDGE_CORRELATION_ID": "corr-1",
        "BAGO_BRIDGE_EXECUTION_ID": "exec-1",
    }
    out = _filter_env(source=base)
    assert "PI_AUTH_TOKEN" not in out
    assert "PI_CUSTOM" not in out
    assert out["PATH"] == "/usr/bin"
    assert out["BAGO_BRIDGE_CORRELATION_ID"] == "corr-1"


def test_filter_env_strips_unallowed() -> None:
    base = {"AWS_SECRET_ACCESS_KEY": "x", "PI_X": "y"}
    out = _filter_env(source=base)
    assert "AWS_SECRET_ACCESS_KEY" not in out
    assert "PI_X" not in out


def test_build_boundary_creates_ephemeral_home(tmp_path: Path) -> None:
    spec = build_boundary(
        argv=[sys.executable, "-c", "import os,sys;sys.stdout.write(os.environ.get('HOME',''))"],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="corr-1",
        execution_id="exec-1",
        parent_home=tmp_path,
    )
    assert os.path.isdir(spec.home_dir)
    assert spec.env["BAGO_BRIDGE_CORRELATION_ID"] == "corr-1"
    assert spec.env["BAGO_BRIDGE_EXECUTION_ID"] == "exec-1"
    assert spec.env["HOME"] == spec.home_dir


def test_build_boundary_rejects_empty_argv(tmp_path: Path) -> None:
    with pytest.raises(ProcessCapabilityDenied):
        build_boundary(
            argv=[],
            cwd=str(tmp_path),
            timeout_seconds=10,
            correlation_id="c",
            execution_id="e",
        )


def test_build_boundary_rejects_huge_timeout(tmp_path: Path) -> None:
    with pytest.raises(ProcessCapabilityDenied):
        build_boundary(
            argv=[sys.executable, "-c", "pass"],
            cwd=str(tmp_path),
            timeout_seconds=10_000,
            correlation_id="c",
            execution_id="e",
        )


def test_build_boundary_rejects_missing_cwd(tmp_path: Path) -> None:
    with pytest.raises(ProcessCapabilityDenied):
        build_boundary(
            argv=[sys.executable, "-c", "pass"],
            cwd=str(tmp_path / "missing"),
            timeout_seconds=10,
            correlation_id="c",
            execution_id="e",
        )


def test_run_sidecar_uses_ephemeral_home(tmp_path: Path) -> None:
    spec = build_boundary(
        argv=[
            sys.executable,
            "-c",
            "import os,sys;sys.stdout.write(os.environ.get('HOME',''))",
        ],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="corr",
        execution_id="exec",
        parent_home=tmp_path,
    )
    result = run_sidecar(spec)
    assert result.returncode == 0
    assert result.stdout.strip() == spec.home_dir


def test_run_sidecar_timeout(tmp_path: Path) -> None:
    spec = build_boundary(
        argv=[sys.executable, "-c", "import time;time.sleep(10)"],
        cwd=str(tmp_path),
        timeout_seconds=1,
        correlation_id="c",
        execution_id="e",
        parent_home=tmp_path,
    )
    with pytest.raises(BridgeTimeout):
        run_sidecar(spec)


def test_run_sidecar_uses_allowlist_env(tmp_path: Path) -> None:
    spec = build_boundary(
        argv=[
            sys.executable,
            "-c",
            "import os,sys;sys.stdout.write(','.join(sorted(os.environ.keys())))",
        ],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="c",
        execution_id="e",
        parent_home=tmp_path,
    )
    result = run_sidecar(spec)
    keys = set(result.stdout.strip().split(","))
    for required in {"BAGO_BRIDGE_CORRELATION_ID", "BAGO_BRIDGE_EXECUTION_ID", "HOME"}:
        assert required in keys


def test_run_sidecar_rejects_injected_pi_env(tmp_path: Path) -> None:
    spec = build_boundary(
        argv=[
            sys.executable,
            "-c",
            "import os,sys;sys.stdout.write(','.join(sorted(os.environ.keys())))",
        ],
        cwd=str(tmp_path),
        timeout_seconds=10,
        correlation_id="c",
        execution_id="e",
        parent_home=tmp_path,
        extra_env={
            "PI_AUTH_TOKEN": "leaked",
            "PI_CUSTOM": "evil",
        },
    )
    result = run_sidecar(spec)
    keys = set(result.stdout.strip().split(","))
    assert "PI_AUTH_TOKEN" not in keys
    assert "PI_CUSTOM" not in keys


def test_verify_integrity_mismatch() -> None:
    spec = BoundarySpec(
        argv=("x",),
        cwd=".",
        env={},
        timeout_seconds=1.0,
        home_dir="",
        integrity={"sidecar_artifact_hash": "expected"},
    )
    with pytest.raises(BridgeIntegrityMismatch):
        verify_integrity(spec, "effective")


def test_verify_integrity_match() -> None:
    spec = BoundarySpec(
        argv=("x",),
        cwd=".",
        env={},
        timeout_seconds=1.0,
        home_dir="",
        integrity={"sidecar_artifact_hash": "abc"},
    )
    verify_integrity(spec, "abc")
