"""guardrails.py — F4: Forbidden paths, structured tool log, no claims without execution.

Three guardrails integrated into SessionManager.send():

1. PathGuard — inspects tool call arguments for forbidden path segments
   (.git, .env, state, .bago, node_modules, etc.) and blocks execution.

2. ToolLogger — appends a structured JSONL entry per tool call with timestamp,
   tool name, arguments, result ok/error, and latency.

3. ClaimValidator — scans LLM responses for claim verbs ("he ejecutado",
   "creé el archivo", "ya apliqué el patch") and verifies that a
   corresponding tool call was logged.  If no evidence is found, appends
   a warning to the response.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

# ── 1. PathGuard ────────────────────────────────────────────────────

FORBIDDEN_PATH_SEGMENTS: tuple[str, ...] = (
    ".git",
    ".env",
    "state",
    "dist",
    "release",
    "__pycache__",
    ".bago",
    "node_modules",
    ".venv",
    "venv",
)


def _extract_path_values(arguments: dict[str, Any]) -> list[str]:
    """Extract string values from arguments that look like file paths."""
    paths: list[str] = []
    for value in arguments.values():
        if isinstance(value, str) and ("/" in value or "\\" in value or "." in value):
            paths.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    paths.append(item)
    return paths


def is_forbidden_path(path_str: str, forbidden: Sequence[str] = FORBIDDEN_PATH_SEGMENTS) -> bool:
    """Check if a path contains any forbidden segment (case-insensitive)."""
    normalized = path_str.replace("\\", "/").lower()
    for segment in forbidden:
        seg_lower = segment.lower()
        if seg_lower in normalized.split("/") or seg_lower in normalized:
            return True
    return False


@dataclass(slots=True)
class PathGuardResult:
    blocked: bool
    reason: str
    blocked_paths: list[str] = field(default_factory=list)


class PathGuard:
    """Validates tool call arguments against forbidden paths.

    When dev_mode=True, forbidden path checking is disabled — allowing
    edits to .bago/, state/, .git/ etc. for development and debugging.
    Dev mode does NOT disable workspace boundary enforcement (that's
    handled by the tools themselves).
    """

    def __init__(
        self,
        forbidden: Sequence[str] = FORBIDDEN_PATH_SEGMENTS,
        dev_mode: bool = False,
    ) -> None:
        self.forbidden = tuple(forbidden)
        self.dev_mode = dev_mode

    def check(self, tool_name: str, arguments: dict[str, Any]) -> PathGuardResult:
        if self.dev_mode:
            return PathGuardResult(blocked=False, reason="")
        paths = _extract_path_values(arguments)
        blocked: list[str] = []
        for p in paths:
            if is_forbidden_path(p, self.forbidden):
                blocked.append(p)
        if blocked:
            return PathGuardResult(
                blocked=True,
                reason=f"Tool '{tool_name}' targets forbidden path(s): {', '.join(blocked)}",
                blocked_paths=blocked,
            )
        return PathGuardResult(blocked=False, reason="")


# ── 2. ToolLogger ────────────────────────────────────────────────────

@dataclass(slots=True)
class ToolLogEntry:
    timestamp: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    returncode: int
    latency_ms: float
    content_preview: str
    blocked: bool = False
    block_reason: str = ""


class ToolLogger:
    """Structured JSONL logger for tool executions."""

    def __init__(self, log_path: str | os.PathLike[str] | None = None) -> None:
        self.log_path = Path(log_path) if log_path else None
        self.entries: list[ToolLogEntry] = []
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        ok: bool,
        returncode: int,
        latency_ms: float,
        content: str,
        blocked: bool = False,
        block_reason: str = "",
    ) -> ToolLogEntry:
        entry = ToolLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            ok=ok,
            returncode=returncode,
            latency_ms=round(latency_ms, 2),
            content_preview=content[:500] if content else "",
            blocked=blocked,
            block_reason=block_reason,
        )
        self.entries.append(entry)
        if self.log_path:
            self._append_to_file(entry)
        return entry

    def _append_to_file(self, entry: ToolLogEntry) -> None:
        if not self.log_path:
            return
        line = json.dumps(
            {
                "timestamp": entry.timestamp,
                "session_id": entry.session_id,
                "tool_name": entry.tool_name,
                "arguments": entry.arguments,
                "ok": entry.ok,
                "returncode": entry.returncode,
                "latency_ms": entry.latency_ms,
                "content_preview": entry.content_preview,
                "blocked": entry.blocked,
                "block_reason": entry.block_reason,
            },
            ensure_ascii=False,
        )
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def tool_names_executed(self) -> list[str]:
        """Return list of tool names that were successfully executed (not blocked)."""
        return [e.tool_name for e in self.entries if not e.blocked and e.ok]

    def has_evidence_for(self, tool_name: str) -> bool:
        """Check if a tool was successfully executed (non-blocked, ok=True)."""
        return any(
            e.tool_name == tool_name and not e.blocked and e.ok
            for e in self.entries
        )

    def clear(self) -> None:
        self.entries.clear()


# ── 3. ClaimValidator ───────────────────────────────────────────────

# Patterns that indicate the model is claiming to have done something.
# Matches common Spanish and English claim verbs in first person.
_CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:he ejecutado|ejecuté|ya ejecuté)\b", re.IGNORECASE),
    re.compile(r"\b(?:creé el archivo|he creado|creé)\b", re.IGNORECASE),
    re.compile(r"\b(?:ya apliqué|he aplicado|apliqué el patch)\b", re.IGNORECASE),
    re.compile(r"\b(?:I ran|I executed|I have run)\b", re.IGNORECASE),
    re.compile(r"\b(?:I created|I have created)\b", re.IGNORECASE),
    re.compile(r"\b(?:I applied|I have applied)\b", re.IGNORECASE),
    re.compile(r"\b(?:I wrote|I have written)\b", re.IGNORECASE),
    re.compile(r"\b(?:he escrito|he modificado|modifiqué)\b", re.IGNORECASE),
    re.compile(r"\b(?:I modified|I have modified)\b", re.IGNORECASE),
    re.compile(r"\b(?:I installed|he instalado|instalé)\b", re.IGNORECASE),
    re.compile(r"\b(?:he inspeccionado|inspeccioné|he revisado|revisé)\b", re.IGNORECASE),
    re.compile(r"\b(?:I inspected|I have inspected|I reviewed|I have reviewed)\b", re.IGNORECASE),
    re.compile(r"\b(?:he encontrado|encontré)\b", re.IGNORECASE),
    re.compile(r"\b(?:I found|I have found)\b", re.IGNORECASE),
]


@dataclass(slots=True)
class ClaimValidation:
    has_claim: bool
    has_evidence: bool
    warning: str


class ClaimValidator:
    """Validates that LLM response claims are backed by tool execution evidence."""

    def __init__(self, patterns: list[re.Pattern[str]] | None = None) -> None:
        self.patterns = patterns if patterns is not None else _CLAIM_PATTERNS

    def validate(self, response_text: str, tool_logger: ToolLogger) -> ClaimValidation:
        has_claim = any(p.search(response_text) for p in self.patterns)
        if not has_claim:
            return ClaimValidation(has_claim=False, has_evidence=True, warning="")

        has_evidence = len(tool_logger.tool_names_executed()) > 0
        if has_evidence:
            return ClaimValidation(has_claim=True, has_evidence=True, warning="")

        warning = (
            "\n\n⚠️ AVISO: La respuesta afirma haber ejecutado una acción, "
            "pero no se registró ninguna ejecución de herramienta. "
            "Las afirmaciones sin evidencia de ejecución no son válidas."
        )
        return ClaimValidation(has_claim=True, has_evidence=False, warning=warning)


__all__ = [
    "FORBIDDEN_PATH_SEGMENTS",
    "PathGuard",
    "PathGuardResult",
    "is_forbidden_path",
    "ToolLogger",
    "ToolLogEntry",
    "ClaimValidator",
    "ClaimValidation",
]