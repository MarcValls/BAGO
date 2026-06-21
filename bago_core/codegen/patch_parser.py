"""BAGO Code Forge 3B - unified diff parser.

Helper module for the Code Forge pipeline. The model returns patches in
``unified_diff`` format; before the validation pipeline can gate them
and the repair loop can fix them, we need a deterministic, *strict*
parser that turns raw diff text into structured :class:`Patch` objects.

Design rules (R0-R10):

- R0: <200 lines, no I/O, no subprocess.
- R1: pure data - :class:`Patch` and :class:`Hunk` are frozen dataclasses.
- R2: deterministic. No global state, no time, no random.
- R3: defensive. Malformed diffs raise :class:`PatchParseError` with a
  stable, machine-readable ``code``. The pipeline uses that code to
  decide whether a repair attempt is worth running.
- R4: never silently drops lines; every byte of a hunk is accounted for.
- R8: no ``print``, no ``subprocess``.

The parser is intentionally limited to the subset of unified diff that
the generation_pass is allowed to emit:

- ``--- a/path`` and ``+++ b/path`` headers
- ``@@ -<old_start>,<old_len> +<new_start>,<new_len> @@`` hunk headers
- `` `` (context), ``-`` (deletion), ``+`` (addition) lines
- ``\\`` (no newline at end of file) markers
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


# Cap the size of a single patch. A 3B model emitting gigabytes of diff
# is a bug, not a feature. 1 MiB is more than enough for any realistic
# Code Forge patch and still small enough to round-trip in memory.
MAX_PATCH_BYTES = 1 * 1024 * 1024

# Pre-compiled line patterns. Keep them cheap and explicit.
_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_len>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_len>\d+))? @@"
)
_FILE_OLD_RE = re.compile(r"^--- (?P<path>.+?)(?:\t.*)?$")
_FILE_NEW_RE = re.compile(r"^\+\+\+ (?P<path>.+?)(?:\t.*)?$")


class PatchParseError(ValueError):
    """Raised when a diff cannot be safely interpreted.

    Attributes
    ----------
    code:
        Stable machine-readable error id. The repair loop dispatches
        on this value.
    line_number:
        1-based line in the original diff where parsing failed, or 0
        if the failure is structural (e.g. too large).
    """

    _ALLOWED_CODES: frozenset[str] = frozenset(
        {
            "patch_too_large",
            "missing_file_headers",
            "malformed_file_header",
            "hunk_outside_file",
            "malformed_hunk_header",
            "hunk_line_count_mismatch",
            "unknown_hunk_line_prefix",
            "context_count_mismatch",
            "inconsistent_file_pair",
        }
    )

    def __init__(self, code: str, message: str, *, line_number: int = 0) -> None:
        if code not in self._ALLOWED_CODES:
            code = "malformed_hunk_header"
        super().__init__(f"{code}: {message}")
        self.code = code
        self.line_number = line_number


@dataclass(frozen=True)
class HunkLine:
    """A single line inside a hunk.

    ``marker`` is one of ``" "``, ``"-"``, ``"+"``, ``"\\"``. ``text`` is
    the line content *without* the marker (and without the trailing
    newline).
    """

    marker: str
    text: str
    source_line_no: int = 0  # 1-based line in the *new* file (best effort)

    def to_dict(self) -> dict[str, object]:
        return {
            "marker": self.marker,
            "text": self.text,
            "source_line_no": self.source_line_no,
        }


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: tuple[HunkLine, ...] = field(default_factory=tuple)

    def additions(self) -> int:
        return sum(1 for line in self.lines if line.marker == "+")

    def deletions(self) -> int:
        return sum(1 for line in self.lines if line.marker == "-")

    def to_dict(self) -> dict[str, object]:
        return {
            "old_start": self.old_start,
            "old_len": self.old_len,
            "new_start": self.new_start,
            "new_len": self.new_len,
            "lines": [line.to_dict() for line in self.lines],
            "additions": self.additions(),
            "deletions": self.deletions(),
        }


@dataclass(frozen=True)
class Patch:
    old_path: str
    new_path: str
    hunks: tuple[Hunk, ...] = field(default_factory=tuple)
    raw: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "old_path": self.old_path,
            "new_path": self.new_path,
            "hunks": [h.to_dict() for h in self.hunks],
            "additions": sum(h.additions() for h in self.hunks),
            "deletions": sum(h.deletions() for h in self.hunks),
        }


def _normalise_path(raw: str) -> str:
    """Strip the optional ``a/`` / ``b/`` prefix the diff format uses."""
    if raw.startswith(("a/", "b/")) and len(raw) > 2:
        return raw[2:]
    return raw


def _parse_hunk(
    header_line: str,
    body: Iterable[str],
    *,
    source_offset: int,
) -> Hunk:
    match = _HUNK_HEADER_RE.match(header_line)
    if not match:
        raise PatchParseError(
            "malformed_hunk_header",
            f"could not parse hunk header: {header_line!r}",
        )
    old_start = int(match.group("old_start"))
    # GNU diff omits the length when it equals 1. Default both lengths
    # to 1 - a single-line context is the most common case and matches
    # what the rest of the pipeline expects to see.
    raw_old_len = match.group("old_len")
    old_len = int(raw_old_len) if raw_old_len is not None else 1
    new_start = int(match.group("new_start"))
    raw_new_len = match.group("new_len")
    new_len = int(raw_new_len) if raw_new_len is not None else 1

    lines: list[HunkLine] = []
    context_count = 0
    addition_count = 0
    deletion_count = 0
    new_line_cursor = new_start

    for raw_line in body:
        if not raw_line:
            # Treat empty line as a context line with empty text. The
            # diff format technically requires a leading space; anything
            # else is a parse error.
            raise PatchParseError(
                "unknown_hunk_line_prefix",
                "encountered an empty line inside a hunk body",
            )
        marker = raw_line[0]
        text = raw_line[1:]
        if marker == " ":
            lines.append(HunkLine(marker, text, new_line_cursor))
            context_count += 1
            new_line_cursor += 1
        elif marker == "-":
            lines.append(HunkLine(marker, text, 0))
            deletion_count += 1
        elif marker == "+":
            lines.append(HunkLine(marker, text, new_line_cursor))
            addition_count += 1
            new_line_cursor += 1
        elif marker == "\\":
            # "\\ No newline at end of file" - informational, not a real
            # line. Stored as a no-op marker for round-tripping.
            lines.append(HunkLine("\\", text[1:] if text.startswith(" ") else text, 0))
        else:
            raise PatchParseError(
                "unknown_hunk_line_prefix",
                f"unexpected hunk line prefix {marker!r}",
            )

    # If the header omitted the lengths, GNU diff uses "1" as default.
    # We have already defaulted to 1 above, but the counts must still
    # match what the body actually carries. old_len = context + deletions
    # and new_len = context + additions, which is exactly what unified
    # diff semantics promise. The "\\ No newline at end of file" marker
    # is informational and does not contribute to either count.
    body_old_len = context_count + deletion_count
    body_new_len = context_count + addition_count
    if body_old_len != old_len or body_new_len != new_len:
        raise PatchParseError(
            "hunk_line_count_mismatch",
            (
                f"hunk header says -{old_len} +{new_len} but body has "
                f"-{deletion_count} +{addition_count} (context={context_count})"
            ),
        )

    return Hunk(
        old_start=old_start,
        old_len=old_len,
        new_start=new_start,
        new_len=new_len,
        lines=tuple(lines),
    )


def parse_patch(text: str) -> Patch:
    """Parse a single ``unified_diff`` blob into a :class:`Patch`.

    Raises :class:`PatchParseError` on any structural problem. The
    returned ``raw`` field preserves the original text so the repair
    loop can quote it back to the model verbatim.
    """
    if not isinstance(text, str):
        raise PatchParseError(
            "malformed_hunk_header", "patch must be a string"
        )
    if len(text) > MAX_PATCH_BYTES:
        raise PatchParseError(
            "patch_too_large",
            f"patch exceeds {MAX_PATCH_BYTES} bytes",
            line_number=0,
        )

    # Normalise line endings. The model frequently emits "\r\n".
    # splitlines() (vs split("\n")) handles trailing newlines cleanly
    # and never produces phantom empty lines at the end of the input.
    lines = text.replace("\r\n", "\n").splitlines()

    old_path = ""
    new_path = ""
    hunks: list[Hunk] = []
    i = 0

    # Skip any preamble (e.g. "diff --git ..."). We require the first
    # meaningful header to be "--- ".
    while i < len(lines) and not lines[i].startswith("--- "):
        i += 1

    if i + 1 >= len(lines):
        raise PatchParseError(
            "missing_file_headers", "diff is missing --- / +++ headers"
        )

    old_match = _FILE_OLD_RE.match(lines[i])
    new_match = _FILE_NEW_RE.match(lines[i + 1])
    if not old_match or not new_match:
        raise PatchParseError(
            "malformed_file_header",
            f"file headers not well-formed at line {i + 1}",
            line_number=i + 1,
        )
    old_path = _normalise_path(old_match.group("path"))
    new_path = _normalise_path(new_match.group("path"))
    if old_path != new_path:
        raise PatchParseError(
            "inconsistent_file_pair",
            f"old/new paths differ: {old_path!r} vs {new_path!r}",
            line_number=i + 1,
        )
    i += 2

    # Consume hunks. Each hunk header is followed by a contiguous block
    # of body lines terminated by either the next hunk header or end of
    # input. We pre-collect the indices of every hunk header so the
    # body collector can use them as explicit terminators. This avoids
    # the "the body is everything until the next 'interesting' line"
    # trap, which misclassifies the very last context line of a hunk
    # as the first line of the next one when the model emits tight
    # diffs.
    hunk_indices: list[int] = [
        idx for idx, line in enumerate(lines) if line.startswith("@@")
    ]
    for hunk_index, header_index in enumerate(hunk_indices):
        header_line = lines[header_index]
        i = header_index + 1
        body_end = (
            hunk_indices[hunk_index + 1]
            if hunk_index + 1 < len(hunk_indices)
            else len(lines)
        )
        body: list[str] = []
        while i < body_end:
            current = lines[i]
            # A bare file header inside a hunk body is structural; we
            # treat it as end-of-hunk. The outer parser will catch a
            # truly missing "+++ b/path" line.
            if current.startswith("--- "):
                break
            if current == "":
                # An empty line is a context line of empty text. Patch
                # and git apply both treat it that way, and the model
                # is told to emit the leading space explicitly.
                i += 1
                continue
            body.append(current)
            i += 1
        hunks.append(_parse_hunk(header_line, iter(body), source_offset=0))

    if not hunks:
        raise PatchParseError(
            "missing_file_headers", "diff has file headers but no hunks"
        )

    return Patch(old_path=old_path, new_path=new_path, hunks=tuple(hunks), raw=text)
