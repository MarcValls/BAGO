"""Tests del preflight."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from integrations.pi.errors import (
    BridgeError,
    ContextEnvelopeRequired,
    DigestMismatch,
    NonceReplayDenied,
    PiAutoloadSourceDetected,
    SessionRevisionObsolete,
)
from integrations.pi.preflight import preflight


def _request(
    tmp_path: Path,
    *,
    envelope_id: str = "env-1",
    session_revision: str = "rev-1",
    nonce: str | None = None,
    scope_root: Path | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    future = (now + timedelta(seconds=60)).isoformat()
    return {
        "protocol_version": "0.1.0",
        "bridge_request_id": "br-1",
        "execution_id": "exec-1",
        "correlation_id": "corr-1",
        "request_nonce": nonce or f"nonce-{time.time_ns()}",
        "issued_at": now.isoformat(),
        "deadline": future,
        "session_id": "sess-1",
        "session_revision": session_revision,
        "workspace_id": "ws-1",
        "project_root": str(tmp_path),
        "workspace_root": str(tmp_path),
        "workspace_scope_root": str(scope_root or tmp_path),
        "context_envelope_id": envelope_id,
        "context_envelope_digest": envelope_id,
        "policy_profile": "disabled",
        "policy_digest": "policy-1",
        "capability_claims": {
            "filesystem_read": False,
            "filesystem_write": False,
            "process_spawn": False,
            "network_mode": "none",
            "tools_allowed": [],
            "skills_imported_ids": [],
            "extensions_allowed": [],
            "packages_allowed": [],
        },
        "requested_provider": "ollama-local",
        "requested_model": "llama3.2:3b",
        "credential_ref": "ref-1",
        "input": {"messages": []},
        "output_limits": {
            "max_tokens": 100,
            "max_bytes_per_event": 65536,
            "max_events": 1024,
            "max_seconds": 30,
        },
    }


def test_preflight_ok(tmp_path: Path) -> None:
    preflight(
        _request(tmp_path),
        observed_envelope_digest="env-1",
        active_session_revision="rev-1",
        phase=0,
    )


def test_preflight_rejects_envelope_digest_mismatch(tmp_path: Path) -> None:
    with pytest.raises(DigestMismatch):
        preflight(
            _request(tmp_path, envelope_id="env-1"),
            observed_envelope_digest="other-digest",
            active_session_revision="rev-1",
            phase=0,
        )


def test_preflight_rejects_session_revision_drift(tmp_path: Path) -> None:
    with pytest.raises(SessionRevisionObsolete):
        preflight(
            _request(tmp_path, session_revision="rev-2"),
            observed_envelope_digest="env-1",
            active_session_revision="rev-1",
            phase=0,
        )


def test_preflight_rejects_nonce_replay(tmp_path: Path) -> None:
    nonce = f"nonce-fixed-{time.time_ns()}"
    preflight(
        _request(tmp_path, nonce=nonce),
        observed_envelope_digest="env-1",
        active_session_revision="rev-1",
        phase=0,
    )
    with pytest.raises(NonceReplayDenied):
        preflight(
            _request(tmp_path, nonce=nonce),
            observed_envelope_digest="env-1",
            active_session_revision="rev-1",
            phase=0,
        )


def test_preflight_rejects_past_deadline(tmp_path: Path) -> None:
    req = _request(tmp_path)
    now = datetime.now(timezone.utc)
    req["issued_at"] = (now - timedelta(hours=2)).isoformat()
    req["deadline"] = (now - timedelta(hours=1)).isoformat()
    with pytest.raises(BridgeError) as exc:
        preflight(
            req,
            observed_envelope_digest="env-1",
            active_session_revision="rev-1",
            phase=0,
        )
    assert "deadline" in str(exc.value.reason)


def test_preflight_detects_implicit_pi_sources(tmp_path: Path) -> None:
    (tmp_path / ".pi").mkdir()
    with pytest.raises(PiAutoloadSourceDetected):
        preflight(
            _request(tmp_path),
            observed_envelope_digest="env-1",
            active_session_revision="rev-1",
            phase=0,
        )


def test_preflight_rejects_unknown_request_fields(tmp_path: Path) -> None:
    req = _request(tmp_path)
    req["mystery_field"] = True
    with pytest.raises(BridgeError):
        preflight(
            req,
            observed_envelope_digest="env-1",
            active_session_revision="rev-1",
            phase=0,
        )
