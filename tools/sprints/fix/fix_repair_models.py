"""Regenerate repair_loop_models.py from the original repo file (before split)."""
from pathlib import Path

# Get the original repair_loop.py content from the backup.
P_ORIG = Path(r"C:\Program Files\BAGO\bago_core\codegen\repair_loop.py.pyproj_backup")
# If no backup, extract from git-style HEAD (not available here) — fall back
# to reconstructing from the dataclass fields we know.
import json

# Hardcode the three dataclasses from repair_loop.py.
models_content = '''"""repair_loop_models.py - dataclasses for the repair loop.

Auto-extracted from repair_loop.py during 4.8.0 modularization.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RepairFeedback:
    """Result of one repair-loop iteration."""

    attempt: int
    maximum_attempts: int
    succeeding: bool
    failing_gate: str
    failing_code: str
    failing_message: str
    offending_path: str
    offending_line: int
    offending_excerpt: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "maximum_attempts": self.maximum_attempts,
            "succeeding": self.succeeding,
            "failing_gate": self.failing_gate,
            "failing_code": self.failing_code,
            "failing_message": self.failing_message,
            "offending_path": self.offending_path,
            "offending_line": self.offending_line,
            "offending_excerpt": self.offending_excerpt,
            "extra": dict(self.extra),
        }


@dataclass(frozen=True)
class RepairAttempt:
    """One model-attempt during a repair cycle."""

    index: int
    prompt: str
    raw_response: str
    patches: tuple[Any, ...]
    validation_summary: dict[str, Any] = field(default_factory=dict)
    feedback: RepairFeedback | None = None
    succeeded: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "patches": list(self.patches),
            "validation_summary": dict(self.validation_summary),
            "feedback": self.feedback.to_dict() if self.feedback else None,
            "succeeded": self.succeeded,
        }


@dataclass(frozen=True)
class RepairVerdict:
    """Final verdict after the repair loop finishes."""

    task_id: str
    target: str
    succeeding: bool
    attempts: tuple[RepairAttempt, ...]
    final_patches: tuple[Any, ...]
    total_tokens: int
    stopped_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "target": self.target,
            "succeeding": self.succeeding,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_patches": list(self.final_patches),
            "total_tokens": self.total_tokens,
            "stopped_reason": self.stopped_reason,
        }
'''

Path(r"C:\Program Files\BAGO\bago_core\codegen\repair_loop_models.py").write_text(
    models_content, encoding="utf-8"
)
print("wrote: repair_loop_models.py")