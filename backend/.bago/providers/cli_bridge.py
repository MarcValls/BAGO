"""Safe non-interactive helpers shared by CLI-backed provider adapters."""

from __future__ import annotations

import shutil
import subprocess
import json
from pathlib import Path


def find_cli(name: str, configured_path: str = "") -> str:
    if configured_path:
        return configured_path
    return shutil.which(name) or ""


def build_prompt(messages: list[dict], system: str = "") -> str:
    payload = {
        "instruction": "Answer the final user message directly. Do not edit files or run tools.",
        "system": system,
        "messages": [
            {"role": str(message.get("role", "user")), "content": str(message.get("content", ""))}
            for message in messages
            if message.get("content")
        ],
    }
    return "BAGO_PROVIDER_BRIDGE_JSON=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def run_cli(command: list[str], cwd: str | Path, timeout: float = 180.0, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        lines = [line.strip() for line in detail.splitlines() if line.strip()]
        decisive = [line for line in lines if "error" in line.lower() or "limit" in line.lower()]
        detail = "\n".join((decisive or lines[-4:])[-4:])
        raise RuntimeError(detail)
    return (result.stdout or result.stderr).strip()
