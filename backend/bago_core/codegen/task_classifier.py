"""Deterministic request classifier for BAGO Code Forge 3B."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CODE_TASK_KINDS = (
    "explain",
    "inspect",
    "create_file",
    "modify_file",
    "fix_error",
    "add_test",
    "refactor_local",
    "generate_project",
    "unsafe_or_unsupported",
)

_FILE_EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".ps1",
    ".cmd",
    ".sh",
}
_DANGEROUS_TOKENS = (
    "cmd /c",
    "powershell -c",
    "powershell /c",
    "bash -c",
    "sh -c",
    "rm -rf",
    "del /s",
    "del /q",
    "format c:",
    "git push --force",
    "git push -f",
    "curl | sh",
    "wget | sh",
)
_UNSAFE_PATH_TOKENS = (
    ".env",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "token",
    "password",
)
_CODE_HINTS = (
    "archivo",
    "file",
    "module",
    "modulo",
    "módulo",
    "function",
    "funcion",
    "función",
    "script",
    "code",
    "código",
    "codigo",
    "repo",
    "test",
)
_EXPLAIN_HINTS = (
    "explica",
    "explicar",
    "explain",
    "why",
    "what does",
    "que hace",
    "qué hace",
)
_INSPECT_HINTS = (
    "inspecciona",
    "inspeccionar",
    "inspect",
    "review",
    "revisa",
    "revisar",
    "read",
    "lee",
    "leer",
    "analiza",
    "analizar",
    "list",
    "show",
)
_CREATE_HINTS = (
    "crea",
    "crear",
    "create",
    "new file",
    "nuevo archivo",
    "añade archivo",
    "anade archivo",
    "add file",
    "scaffold",
    "bootstrap",
    # Spanish write/generate verbs for file creation
    "escribe",
    "escribir",
    "escribelo",
    "escríbelo",
    "redacta",
    "redactar",
    "genera",
    "generar",
    "haz un archivo",
    "haz un fichero",
    "make a file",
    "write a file",
    "write file",
    "write me",
)
_GENERATE_HINTS = (
    "genera",
    "generate",
    "scaffold",
    "bootstrap",
    "starter",
    "template",
)
_ADD_TEST_PHRASES = (
    "add test",
    "add tests",
    "create test",
    "create tests",
    "write test",
    "write tests",
    "añade un test",
    "anade un test",
    "añadir test",
    "anadir test",
    "crea un test",
    "crea tests",
    "crear test",
    "crear tests",
    "genera pruebas",
    "crear pruebas",
    "add a test",
    "write a test",
)
_MODIFY_HINTS = (
    "modifica",
    "modificar",
    "modify",
    "update",
    "edit",
    "patch",
    "cambia",
    "cambiar",
    "ajusta",
    "adjust",
    "fix",
)
_TEST_HINTS = (
    "test",
    "tests",
    "pytest",
    "unittest",
    "spec",
    "prueba",
    "pruebas",
)
_REFACTOR_HINTS = (
    "refactor",
    "refactoriza",
    "refactorizar",
    "cleanup",
    "clean up",
    "modulariza",
    "modularizar",
)
_PROJECT_HINTS = (
    "project",
    "proyecto",
    "app",
    "application",
    "skeleton",
    "from scratch",
    "desde cero",
)
_ERROR_HINTS = (
    "traceback",
    "syntaxerror",
    "indentationerror",
    "valueerror",
    "typeerror",
    "nameerror",
    "attributeerror",
    "importerror",
    "exception",
    "error",
    "stack trace",
    "failed",
    "falló",
    "fallo",
)
_ACTION_HINTS = _MODIFY_HINTS + _CREATE_HINTS + _EXPLAIN_HINTS + _INSPECT_HINTS + _REFACTOR_HINTS + _ADD_TEST_PHRASES + _ERROR_HINTS
_FILE_RE = re.compile(
    r"""
    (?:
        [A-Za-z]:[\\/][^\s"'`]+
        |
        (?:\.\.?[\\/]|[\\/])[^\s"'`]+
        |
        \b[\w.\-\\/]+\.(?:py|js|mjs|cjs|ts|tsx|json|yaml|yml|toml|md|ps1|cmd|sh)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_TRACEBACK_RE = re.compile(
    r"(Traceback \(most recent call last\)|SyntaxError|IndentationError|ValueError|TypeError|NameError|AttributeError|ImportError|AssertionError)",
    re.IGNORECASE,
)


def _looks_like_pasted_document(text: str) -> bool:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(text) < 400 or len(lines) < 8:
        return False

    structured_lines = sum(
        1
        for line in lines
        if line.startswith(("#", "-", "*")) or re.match(r"^\d+\.\s", line)
    )
    section_hits = sum(
        1
        for marker in (
            "dictamen",
            "verificaciones ejecutadas",
            "bloqueos p0",
            "riesgos p1",
            "problemas p2",
            "conclusión",
            "conclusion",
            "hallazgos",
            "auditoría",
            "auditoria",
        )
        if marker in text.lower()
    )
    paragraph_lines = sum(1 for line in lines if len(line.split()) >= 8)
    return section_hits >= 1 and structured_lines >= 4 and paragraph_lines >= 4


@dataclass(frozen=True)
class CodeTaskClassification:
    kind: str
    confidence: float
    reasons: tuple[str, ...]
    target_files: tuple[str, ...] = ()
    is_code_request: bool = False
    blocked: bool = False
    existing_files: tuple[str, ...] = ()
    missing_files: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "confidence": round(self.confidence, 3),
            "reasons": list(self.reasons),
            "target_files": list(self.target_files),
            "is_code_request": self.is_code_request,
            "blocked": self.blocked,
            "existing_files": list(self.existing_files),
            "missing_files": list(self.missing_files),
        }

    def refusal_message(self) -> str:
        if not self.blocked:
            return ""
        return (
            "Solicitud rechazada por el clasificador determinista: "
            f"{self.kind}. "
            + ("; ".join(self.reasons) if self.reasons else "sin razones adicionales.")
        )


def _has_any(text: str, needles: Iterable[str]) -> bool:
    return any(needle in text for needle in needles)


def _extract_paths(text: str) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for match in _FILE_RE.finditer(text):
        token = match.group(0).strip().strip("`'\".,:;()[]{}<>")
        if not token:
            continue
        if token.endswith(":"):
            continue
        seen.setdefault(token, None)
    return tuple(seen.keys())


def _resolve_paths(
    raw_paths: Iterable[str],
    workspace_root: str | Path | None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    root = Path(workspace_root).resolve() if workspace_root else None
    normalized: list[str] = []
    existing: list[str] = []
    missing: list[str] = []
    for raw in raw_paths:
        candidate = Path(raw)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate if root else candidate)
        try:
            if root and resolved.is_relative_to(root):
                pretty = str(resolved.relative_to(root))
            else:
                pretty = str(resolved)
        except Exception:
            pretty = str(resolved)
        normalized.append(pretty)
        if resolved.exists():
            existing.append(pretty)
        else:
            missing.append(pretty)
    dedup = lambda items: tuple(dict.fromkeys(items))
    return dedup(normalized), dedup(existing), dedup(missing)


def _confidence(base: float, *, bonus: float = 0.0, cap: float = 0.99) -> float:
    return round(min(cap, max(0.0, base + bonus)), 3)


def classify_code_request(
    request: str,
    *,
    workspace_root: str | Path | None = None,
    allowed_files: Iterable[str] | None = None,
) -> CodeTaskClassification:
    text = (request or "").strip()
    lowered = text.lower()
    if not text:
        return CodeTaskClassification(
            kind="unsafe_or_unsupported",
            confidence=0.0,
            reasons=("empty_request",),
            is_code_request=False,
            blocked=False,
        )

    file_mentions = _extract_paths(text)
    target_files, existing_files, missing_files = _resolve_paths(file_mentions, workspace_root)
    if _looks_like_pasted_document(text):
        return CodeTaskClassification(
            kind="unsafe_or_unsupported",
            confidence=_confidence(0.18),
            reasons=("pasted_document_detected",),
            target_files=(),
            is_code_request=False,
            blocked=False,
            existing_files=(),
            missing_files=(),
        )

    code_signals = _has_any(lowered, _CODE_HINTS) or bool(_TRACEBACK_RE.search(text))
    if allowed_files is not None:
        allowed_norm = {str(Path(path)).replace("/", "\\").lower() for path in allowed_files}
        disallowed = [
            path for path in target_files
            if str(Path(path)).replace("/", "\\").lower() not in allowed_norm
        ]
    else:
        disallowed = []

    reasons: list[str] = []
    if file_mentions:
        reasons.append("file_mentioned")
    if existing_files:
        reasons.append("existing_target_detected")
    if missing_files:
        reasons.append("missing_target_detected")

    if _has_any(lowered, _DANGEROUS_TOKENS) or (
        _has_any(lowered, _UNSAFE_PATH_TOKENS) and _has_any(lowered, _MODIFY_HINTS + _CREATE_HINTS + _INSPECT_HINTS)
    ):
        reasons.append("dangerous_or_sensitive_request")
        if disallowed:
            reasons.append("allowed_files_violation")
        return CodeTaskClassification(
            kind="unsafe_or_unsupported",
            confidence=_confidence(0.95, bonus=0.04),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=True,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if file_mentions and not _has_any(lowered, _ACTION_HINTS):
        reasons.append("file_mentioned_reference_only")
        return CodeTaskClassification(
            kind="unsafe_or_unsupported",
            confidence=_confidence(0.2),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=False,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if disallowed:
        reasons.append("allowed_files_violation")
        return CodeTaskClassification(
            kind="unsafe_or_unsupported",
            confidence=_confidence(0.9),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=True,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _TRACEBACK_RE.search(text) or _has_any(lowered, _ERROR_HINTS):
        if _has_any(lowered, _CREATE_HINTS):
            kind = "create_file"
        else:
            kind = "fix_error"
        reasons.append("error_signal_detected")
        return CodeTaskClassification(
            kind=kind,
            confidence=_confidence(0.78, bonus=0.12 if _TRACEBACK_RE.search(text) else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _REFACTOR_HINTS):
        reasons.append("refactor_signal_detected")
        return CodeTaskClassification(
            kind="refactor_local",
            confidence=_confidence(0.82, bonus=0.08 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _PROJECT_HINTS) and _has_any(lowered, _GENERATE_HINTS):
        reasons.append("project_generation_signal_detected")
        return CodeTaskClassification(
            kind="generate_project",
            confidence=_confidence(0.84, bonus=0.06 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if file_mentions and _has_any(lowered, _CREATE_HINTS):
        reasons.append("create_signal_detected")
        if not file_mentions and _has_any(lowered, _ADD_TEST_PHRASES):
            return CodeTaskClassification(
                kind="add_test",
                confidence=_confidence(0.83, bonus=0.08 if target_files else 0.0),
                reasons=tuple(reasons + ["test_signal_overrode_create"]),
                target_files=target_files,
                is_code_request=True,
                blocked=False,
                existing_files=existing_files,
                missing_files=missing_files,
            )
        kind = "create_file"
        if existing_files and not missing_files:
            kind = "modify_file"
            reasons.append("target_already_exists")
        return CodeTaskClassification(
            kind=kind,
            confidence=_confidence(0.77, bonus=0.1 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _ADD_TEST_PHRASES):
        reasons.append("test_signal_detected")
        return CodeTaskClassification(
            kind="add_test",
            confidence=_confidence(0.82, bonus=0.08 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _CREATE_HINTS):
        reasons.append("create_signal_detected")
        if not file_mentions and _has_any(lowered, _ADD_TEST_PHRASES):
            return CodeTaskClassification(
                kind="add_test",
                confidence=_confidence(0.82, bonus=0.08 if target_files else 0.0),
                reasons=tuple(reasons + ["test_signal_overrode_create"]),
                target_files=target_files,
                is_code_request=True,
                blocked=False,
                existing_files=existing_files,
                missing_files=missing_files,
            )
        kind = "create_file"
        if existing_files and not missing_files:
            kind = "modify_file"
            reasons.append("target_already_exists")
        return CodeTaskClassification(
            kind=kind,
            confidence=_confidence(0.76, bonus=0.1 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _MODIFY_HINTS):
        reasons.append("modify_signal_detected")
        kind = "modify_file"
        if not target_files and not _has_any(lowered, _CODE_HINTS):
            kind = "unsafe_or_unsupported"
            reasons.append("no_target_or_code_hint")
            return CodeTaskClassification(
                kind=kind,
                confidence=_confidence(0.65),
                reasons=tuple(reasons),
                target_files=target_files,
                is_code_request=bool(file_mentions or _has_any(lowered, _CODE_HINTS)),
                blocked=bool(file_mentions or _has_any(lowered, _CODE_HINTS)),
                existing_files=existing_files,
                missing_files=missing_files,
            )
        return CodeTaskClassification(
            kind=kind,
            confidence=_confidence(0.8, bonus=0.08 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _INSPECT_HINTS):
        reasons.append("inspect_signal_detected")
        return CodeTaskClassification(
            kind="inspect",
            confidence=_confidence(0.74, bonus=0.08 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=bool(file_mentions or _has_any(lowered, _CODE_HINTS)),
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if _has_any(lowered, _EXPLAIN_HINTS):
        reasons.append("explain_signal_detected")
        return CodeTaskClassification(
            kind="explain",
            confidence=_confidence(0.72, bonus=0.08 if target_files else 0.0),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=bool(file_mentions or _has_any(lowered, _CODE_HINTS)),
            blocked=False,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    if code_signals:
        reasons.append("code_signal_without_specific_route")
        return CodeTaskClassification(
            kind="unsafe_or_unsupported",
            confidence=_confidence(0.61),
            reasons=tuple(reasons),
            target_files=target_files,
            is_code_request=True,
            blocked=True,
            existing_files=existing_files,
            missing_files=missing_files,
        )

    return CodeTaskClassification(
        kind="unsafe_or_unsupported",
        confidence=0.0,
        reasons=("not_a_code_request",),
        target_files=(),
        is_code_request=False,
        blocked=False,
    )
