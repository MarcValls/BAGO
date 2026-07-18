#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

NODE_CONTROL_SCHEMA_VERSION = 1

PIECE_STORE_ROOT_ENV = "BAGO_PIECES_ROOT"

PIECE_STORE_TYPES = ("tools", "agents", "skills", "repos", "knowledge", "models", "connectors", "blobs", "cache", "translators")

ALLOWED_MODES = ("connected", "shadow", "locked", "detached", "read-only", "writable overlay")

CLI_MODES = {
    "connected": "connected",
    "shadow": "shadow",
    "locked": "locked",
    "detached": "detached",
    "readonly": "read-only",
    "overlay": "writable overlay",
}


def _piece_store_root() -> Path:
    override = os.environ.get(PIECE_STORE_ROOT_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    data_root = os.environ.get("BAGO_DATA_ROOT", "").strip()
    if data_root:
        return Path(data_root).expanduser().resolve() / "pieces"
    program_data = os.environ.get("ProgramData", "").strip()
    if program_data:
        return Path(program_data) / "BAGO" / "pieces"
    return Path.home() / "AppData" / "Local" / "BAGO" / "pieces"


def _piece_store_path(*parts: str) -> str:
    return str(_piece_store_root().joinpath(*parts))

DEFAULT_PIECE_CATALOG: list[dict[str, str]] = [
    {
        "piece_id": "tool.ollama-local",
        "type": "tool",
        "scope": "local",
        "version": "1.0",
        "hash": "sha256:ollama-local",
        "store_path": _piece_store_path("tools", "ollama-local"),
    },
    {
        "piece_id": "tool.openrouter-provider",
        "type": "tool",
        "scope": "cloud",
        "version": "1.0",
        "hash": "sha256:openrouter-provider",
        "store_path": _piece_store_path("tools", "openrouter-provider"),
    },
    {
        "piece_id": "skill.evidence-ledger",
        "type": "skill",
        "scope": "local",
        "version": "1.0",
        "hash": "sha256:evidence-ledger",
        "store_path": _piece_store_path("skills", "evidence-ledger"),
    },
    {
        "piece_id": "repo.bago",
        "type": "repo",
        "scope": "shared",
        "version": "main",
        "hash": "git:main",
        "store_path": _piece_store_path("repos", "MarcValls-BAGO"),
    },
    {
        "piece_id": "knowledge.shared",
        "type": "knowledge",
        "scope": "shared",
        "version": "db",
        "hash": "sqlite:knowledge",
        "store_path": _piece_store_path("knowledge", "knowledge.db"),
    },
    {
        "piece_id": "model.granite3.2-8b",
        "type": "model",
        "scope": "local",
        "version": "8b",
        "hash": "sha256:granite3.2-8b",
        "store_path": _piece_store_path("models", "granite3.2-8b"),
    },
    {
        "piece_id": "agent.rl-bridge",
        "type": "agent",
        "scope": "experimental",
        "version": "shadow",
        "hash": "sha256:rl-bridge",
        "store_path": _piece_store_path("agents", "rl-bridge"),
    },
    {
        "piece_id": "skill.toolsmith-catalog",
        "type": "skill",
        "scope": "experimental",
        "version": "0.8",
        "hash": "sha256:toolsmith-catalog",
        "store_path": _piece_store_path("skills", "toolsmith-catalog"),
    },
    {
        "piece_id": "translator.shared.base",
        "type": "translator",
        "scope": "shared",
        "version": "1.0",
        "hash": "sha256:translator-base-v1",
        "store_path": _piece_store_path("translators", "shared", "base"),
    },
    {
        "piece_id": "translator.openai.gpt-4o",
        "type": "translator",
        "scope": "cloud",
        "version": "1.0",
        "hash": "sha256:translator-openai-gpt4o-v1",
        "store_path": _piece_store_path("translators", "openai", "gpt-4o"),
    },
    {
        "piece_id": "translator.anthropic.claude-3-5-sonnet",
        "type": "translator",
        "scope": "cloud",
        "version": "1.0",
        "hash": "sha256:translator-anthropic-claude35-v1",
        "store_path": _piece_store_path("translators", "anthropic", "claude-3-5-sonnet"),
    },
    {
        "piece_id": "translator.ollama.llama3.2",
        "type": "translator",
        "scope": "local",
        "version": "1.0",
        "hash": "sha256:translator-ollama-llama32-v1",
        "store_path": _piece_store_path("translators", "ollama", "llama3.2"),
    },
    {
        "piece_id": "translator.ollama.granite3.2-8b",
        "type": "translator",
        "scope": "local",
        "version": "1.0",
        "hash": "sha256:translator-ollama-granite32-v1",
        "store_path": _piece_store_path("translators", "ollama", "granite3.2-8b"),
    },
]
