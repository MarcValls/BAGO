#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from bago_core.node_control_ssot import ALLOWED_MODES, CLI_MODES

def policy_for(installation: dict[str, Any], piece: dict[str, Any]) -> dict[str, Any]:
    profile = installation.get("profile", "production")
    scope = piece.get("scope", "shared")
    ptype = piece.get("type", "tool")
    piece_id = piece.get("piece_id", "")

    mode = "connected"
    if profile == "production":
        if scope == "cloud" or scope == "experimental" or ptype == "agent":
            mode = "locked"
        elif ptype in {"repo", "knowledge"}:
            mode = "read-only"
        else:
            mode = "connected"
    elif profile == "beta":
        if scope == "cloud":
            mode = "shadow"
        elif scope == "experimental" or ptype == "agent":
            mode = "shadow"
        elif ptype in {"repo", "knowledge"}:
            mode = "read-only"
        else:
            mode = "connected"
    elif profile == "lab":
        if scope == "cloud":
            mode = "connected"
        elif scope == "experimental":
            mode = "writable overlay"
        elif ptype in {"repo", "knowledge"}:
            mode = "writable overlay"
        else:
            mode = "connected"
    elif profile == "offline":
        if scope == "cloud":
            mode = "locked"
        elif scope == "experimental":
            mode = "locked"
        elif ptype in {"repo", "knowledge"}:
            mode = "read-only"
        else:
            mode = "connected"
    elif profile == "quarantine":
        mode = "locked"

    can_execute = mode in {"connected", "writable overlay"}
    can_modify = mode == "writable overlay"
    sync_mode = {
        "connected": "pull",
        "shadow": "observe",
        "locked": "deny",
        "detached": "none",
        "read-only": "pull",
        "writable overlay": "overlay",
    }[mode]
    visibility = {
        "connected": "visible",
        "shadow": "shadow",
        "locked": "hidden",
        "detached": "detached",
        "read-only": "readonly",
        "writable overlay": "overlay",
    }[mode]
    reason = f"profile={profile};scope={scope};type={ptype};piece={piece_id}"
    return {
        "mode": mode,
        "policy": {
            "can_execute": can_execute,
            "can_modify": can_modify,
            "sync_mode": sync_mode,
            "visibility": visibility,
        },
        "reason": reason,
    }

def connector_id(installation_id: str, piece_id: str) -> str:
    digest = hashlib.sha1(f"{installation_id}:{piece_id}".encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    return f"conn-{digest}"

def build_connectors(installations: list[dict[str, Any]], pieces: list[dict[str, Any]], now_fn) -> list[dict[str, Any]]:
    connectors: list[dict[str, Any]] = []
    for install in installations:
        for piece in pieces:
            resolved = policy_for(install, piece)
            connectors.append(
                {
                    "connector_id": connector_id(install["installation_id"], piece["piece_id"]),
                    "installation_id": install["installation_id"],
                    "piece_id": piece["piece_id"],
                    "mode": resolved["mode"],
                    "policy": resolved["policy"],
                    "reason": resolved["reason"],
                    "created_at": now_fn(),
                    "updated_at": now_fn(),
                }
            )
    return connectors

def build_compatibility(connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for connector in connectors:
        rows.append(
            {
                "installation_id": connector["installation_id"],
                "piece_id": connector["piece_id"],
                "mode": connector["mode"],
                "can_execute": connector["policy"]["can_execute"],
                "can_modify": connector["policy"]["can_modify"],
                "sync_mode": connector["policy"]["sync_mode"],
                "visibility": connector["policy"]["visibility"],
                "allowed": connector["mode"] != "locked",
            }
        )
    return rows

def normalize_mode(mode: str | None) -> str:
    if not mode:
        return "connected"
    return CLI_MODES.get(mode.lower(), mode.lower())

# R5 SSoT: tables for the per-mode policy flags. ``policy_for`` inlines
# these for the read-side (``mode -> {can_execute, can_modify, ...}``);
# the connect side consumes them via :func:`policy_dict_for_mode` to
# avoid duplicating the dict literals.
_MODE_SYNC: dict[str, str] = {
    "connected": "pull",
    "shadow": "observe",
    "locked": "deny",
    "detached": "none",
    "read-only": "pull",
    "writable overlay": "overlay",
}
_MODE_VISIBILITY: dict[str, str] = {
    "connected": "visible",
    "shadow": "shadow",
    "locked": "hidden",
    "detached": "detached",
    "read-only": "readonly",
    "writable overlay": "overlay",
}


def policy_dict_for_mode(mode: str) -> dict[str, bool | str]:
    """Build the per-mode policy dict consumed by the connector state.

    This is the write-side counterpart of :func:`policy_for`: it turns
    a target mode (possibly user-supplied) into the same shape that
    ``policy_for`` produces, so the connect path stays consistent with
    the read path. R5 SSoT: both call sites read from ``_MODE_SYNC`` /
    ``_MODE_VISIBILITY``; the literals are not duplicated.
    """
    return {
        "can_execute": mode in {"connected", "writable overlay"},
        "can_modify": mode == "writable overlay",
        "sync_mode": _MODE_SYNC[mode],
        "visibility": _MODE_VISIBILITY[mode],
    }

def is_valid_mode(mode: str) -> bool:
    return mode in ALLOWED_MODES

def find_installation(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    key_norm = str(key).strip().lower()
    for install in state["installations"]:
        if install["installation_id"].lower() == key_norm:
            return install
        if Path(install["path"]).resolve().as_posix().lower() == Path(key).resolve().as_posix().lower():
            return install
    return None

def find_piece(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    key_norm = str(key).strip().lower()
    for piece in state["pieces"]:
        if piece["piece_id"].lower() == key_norm:
            return piece
    return None

def find_connector(state: dict[str, Any], installation_id: str, piece_id: str) -> dict[str, Any] | None:
    for connector in state["connectors"]:
        if connector["installation_id"] == installation_id and connector["piece_id"] == piece_id:
            return connector
    return None


# -- FASE 12.6: translator policy gate ----------------------------------------
#
# The Policy Engine must refuse to "connect" an installation to a piece when
# the installation has no translator capable of encoding/decoding the model's
# dialect. This is the FASE 12.6 contract: a missing translator is a hard
# policy failure (evidence: missing_translator), not a warning.

MISSING_TRANSLATOR_REASON = "missing_translator"


def installation_has_translator(installation: dict[str, Any], piece_id: str) -> bool:
    """Return True iff `installation['translators']` lists `piece_id` as enabled."""
    for entry in installation.get("translators", []) or []:
        if not isinstance(entry, dict):
            continue
        if not entry.get("enabled", True):
            continue
        if entry.get("piece_id") == piece_id:
            return True
    return False


def gate_translator(installation: dict[str, Any], piece: dict[str, Any]) -> dict[str, Any]:
    """Apply the translator gate for a (installation, piece) pair.

    For translator pieces, the installation must have the piece itself bound
    in its `translators` list. For non-translator pieces (tools, agents,
    repos, knowledge, models, skills) the gate is trivially satisfied.

    Returns:
        {
          "ok":     bool,
          "reason": str (empty if ok),
          "mode":   "connected" | "locked"  (locked if missing translator)
        }
    """
    ptype = piece.get("type", "")
    if ptype != "translator":
        return {"ok": True, "reason": "", "mode": "connected"}
    piece_id = piece.get("piece_id", "")
    if installation_has_translator(installation, piece_id):
        return {"ok": True, "reason": "", "mode": "connected"}
    return {
        "ok": False,
        "reason": MISSING_TRANSLATOR_REASON,
        "mode": "locked",
    }
