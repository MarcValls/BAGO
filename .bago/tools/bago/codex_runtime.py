"""Helpers for running Codex CLI as a backend."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .cwd import get_user_cwd


def resolve_codex_cli() -> str | None:
    for name in ("codex", "codex.cmd", "codex.ps1"):
        found = shutil.which(name)
        if found:
            return found
    try:
        out = subprocess.run(
            ["where.exe", "codex"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in out.stdout.splitlines():
            candidate = line.strip()
            if candidate:
                return candidate
    except Exception:
        pass
    return None


def codex_cli_available() -> bool:
    return resolve_codex_cli() is not None


def build_codex_prompt(messages: list[dict]) -> str:
    system_parts: list[str] = []
    transcript: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user")).strip().lower() or "user"
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
        else:
            transcript.append(f"{role.upper()}:\n{content}")

    parts: list[str] = []
    if system_parts:
        parts.append("SYSTEM:\n" + "\n\n".join(system_parts))
    if transcript:
        parts.append("CONVERSATION:\n" + "\n\n".join(transcript))
    parts.append(
        "INSTRUCCION FINAL:\n"
        "Responde solo al ultimo mensaje del usuario. "
        "Devuelve solo la respuesta final."
    )
    return "\n\n".join(parts).strip()


def _extract_last_json_text(stdout: str) -> str:
    last_text = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        item = data.get("item")
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                last_text = text.strip()
    return last_text


def _extract_usage(stdout: str) -> dict:
    usage: dict = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue
        if data.get("type") == "turn.completed" and isinstance(data.get("usage"), dict):
            usage = data["usage"]
    return usage


def _classify_codex_error(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("auth", "login", "sign in", "sign-in", "not authenticated")):
        return "auth"
    if any(k in low for k in ("quota", "rate limit", "rate-limit", "billing", "credits", "insufficient")):
        return "quota"
    if any(k in low for k in ("timeout", "timed out", "connection", "unreachable", "network")):
        return "connection"
    return "unknown"


def run_codex_exec(
    messages: list[dict],
    model: str,
    *,
    workdir: str | Path | None = None,
    timeout: int = 120,
    sandbox: str = "read-only",
) -> tuple[str, dict]:
    """Run Codex CLI non-interactively and return (text, usage)."""
    cli = resolve_codex_cli()
    if not cli:
        raise RuntimeError("codex CLI no disponible")

    prompt = build_codex_prompt(messages)
    base_dir = Path(workdir or get_user_cwd()).resolve()

    fd, out_path = tempfile.mkstemp(prefix="bago_codex_", suffix=".txt")
    os.close(fd)
    out_file = Path(out_path)
    try:
        cmd = [
            cli,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "-C",
            str(base_dir),
            "--sandbox",
            sandbox,
            "--model",
            model,
            "--json",
            "--color",
            "never",
            "--output-last-message",
            str(out_file),
            prompt,
        ]
        if cli.lower().endswith((".cmd", ".bat", ".ps1")):
            cmd = ["cmd", "/c", *cmd]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

        text = ""
        if out_file.exists():
            try:
                text = out_file.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                text = ""

        usage = _extract_usage(proc.stdout)
        if not text:
            text = _extract_last_json_text(proc.stdout)

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            kind = _classify_codex_error(detail)
            if kind == "auth":
                raise RuntimeError(f"codex auth required: {detail or 'login required'}")
            if kind == "quota":
                raise RuntimeError(f"codex quota error: {detail or 'quota/retry later'}")
            if kind == "connection":
                raise RuntimeError(f"codex connection error: {detail or 'connection failed'}")
            raise RuntimeError(f"codex exec failed ({proc.returncode}): {detail or 'unknown error'}")

        if not text:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"codex exec produced empty output: {detail or 'no output'}")

        return text, usage
    finally:
        try:
            out_file.unlink(missing_ok=True)
        except Exception:
            pass
