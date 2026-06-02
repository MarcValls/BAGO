#!/usr/bin/env python3
from __future__ import annotations

NODE_CONTROL_SCHEMA_VERSION = 1

PIECE_STORE_TYPES = ("tools", "agents", "skills", "repos", "knowledge", "models", "connectors", "blobs", "cache")

ALLOWED_MODES = ("connected", "shadow", "locked", "detached", "read-only", "writable overlay")

CLI_MODES = {
    "connected": "connected",
    "shadow": "shadow",
    "locked": "locked",
    "detached": "detached",
    "readonly": "read-only",
    "overlay": "writable overlay",
}

DEFAULT_PIECE_CATALOG: list[dict[str, str]] = [
    {
        "piece_id": "tool.ollama-local",
        "type": "tool",
        "scope": "local",
        "version": "1.0",
        "hash": "sha256:ollama-local",
        "store_path": r"C:\ProgramData\BAGO\pieces\tools\ollama-local",
    },
    {
        "piece_id": "tool.openrouter-provider",
        "type": "tool",
        "scope": "cloud",
        "version": "1.0",
        "hash": "sha256:openrouter-provider",
        "store_path": r"C:\ProgramData\BAGO\pieces\tools\openrouter-provider",
    },
    {
        "piece_id": "skill.evidence-ledger",
        "type": "skill",
        "scope": "local",
        "version": "1.0",
        "hash": "sha256:evidence-ledger",
        "store_path": r"C:\ProgramData\BAGO\pieces\skills\evidence-ledger",
    },
    {
        "piece_id": "repo.bago",
        "type": "repo",
        "scope": "shared",
        "version": "main",
        "hash": "git:main",
        "store_path": r"C:\ProgramData\BAGO\pieces\repos\MarcValls-BAGO",
    },
    {
        "piece_id": "knowledge.shared",
        "type": "knowledge",
        "scope": "shared",
        "version": "db",
        "hash": "sqlite:knowledge",
        "store_path": r"C:\ProgramData\BAGO\pieces\knowledge\knowledge.db",
    },
    {
        "piece_id": "model.granite3.2-8b",
        "type": "model",
        "scope": "local",
        "version": "8b",
        "hash": "sha256:granite3.2-8b",
        "store_path": r"C:\ProgramData\BAGO\pieces\models\granite3.2-8b",
    },
    {
        "piece_id": "agent.rl-bridge",
        "type": "agent",
        "scope": "experimental",
        "version": "shadow",
        "hash": "sha256:rl-bridge",
        "store_path": r"C:\ProgramData\BAGO\pieces\agents\rl-bridge",
    },
    {
        "piece_id": "skill.toolsmith-catalog",
        "type": "skill",
        "scope": "experimental",
        "version": "0.8",
        "hash": "sha256:toolsmith-catalog",
        "store_path": r"C:\ProgramData\BAGO\pieces\skills\toolsmith-catalog",
    },
]
