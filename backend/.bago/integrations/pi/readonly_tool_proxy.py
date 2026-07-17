"""readonly_tool_proxy.py — proxy BAGO de tools de solo lectura.

Las 4 tools (`read`, `ls`, `grep`, `find`) son **proxies BAGO**, no
implementaciones del sidecar. El flujo es:

    1. El sidecar emite `tool_requested` con argumentos normalizados.
    2. El bridge, **dentro del proceso BAGO**, decide si la tool es
       invocable (`decide_tool`).
    3. El bridge ejecuta la tool aquí, con los servicios canónicos:
       - `assert_within_scope` para resolver la ruta
       - `verify_toctou` para re-stat antes de devolver contenido
       - `is_within_root` y case-folding en Windows
    4. El bridge emite `ToolReceipt` (canónico) y `tool_result_attached`.
    5. La ejecución **descarta** el resultado si falta el receipt.

Restricciones (Fase 2):
    - Tools distintas a `read|ls|grep|find` → `TOOL_NOT_ALLOWED` y la
      ejecución se cancela.
    - Ninguna tool escribe, renombra, borra ni parchea.
    - El contenido devuelto se trunca a `MAX_READ_BYTES` y se marca
      como dato no confiable frente al prompt.
    - Symlinks/junctions que escapan de scope → `SCOPE_LINK_ESCAPE_DENIED`.
    - TOCTOU: el archivo debe tener la misma identidad (st_dev/st_ino)
      antes y después de la lectura.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .contracts import ALLOWED_TOOLS
from .errors import (
    BridgeError,
    CapabilityDenied,
    OutputLimitExceeded,
    ScopeLinkEscapeDenied,
    ScopePathDenied,
    ScopeReadDenied,
    ScopeToctouDetected,
    ToolNotAllowed,
)
from .policy_gate import decide_tool
from .scope_validator import (
    ResolvedPath,
    assert_within_scope,
    verify_toctou,
)


# ── Límites de Fase 2 ──────────────────────────────────────────────────────

MAX_READ_BYTES: int = 256 * 1024  # 256 KiB por lectura
MAX_LS_ENTRIES: int = 4096
MAX_GREP_RESULTS: int = 1024
MAX_GREP_BYTES_PER_FILE: int = 1024 * 1024  # 1 MiB
MAX_FIND_ENTRIES: int = 4096
MAX_FIND_DEPTH: int = 16
PROXY_VERSION: str = "0.1.0"


# ── Resultado de tool call ─────────────────────────────────────────────────


@dataclass
class ToolResult:
    """Resultado crudo de una tool ejecutada por el proxy BAGO."""

    tool: str
    output: Any  # str para read/grep, list[dict] para ls/find
    size_bytes: int
    truncated: bool
    started_at: str
    finished_at: str

    def content_hash(self) -> str:
        text = self.output if isinstance(self.output, str) else repr(self.output)
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


@dataclass
class ToolDecision:
    """Decisión + resultado de una tool, antes de emitir ToolReceipt."""

    allowed: bool
    tool: str
    rule_code: str
    result: ToolResult | None = None
    redactions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "tool": self.tool,
            "rule_code": self.rule_code,
            "redactions": list(self.redactions),
        }


# ── Helpers de scope ──────────────────────────────────────────────────────


def _path_from_arguments(arguments: dict[str, Any]) -> str:
    """Extrae el path del argumento de la tool. Acepta `path` o primer arg."""
    if "path" in arguments:
        return str(arguments["path"])
    # Acepta también `file`, `target` como alias.
    for key in ("file", "target"):
        if key in arguments:
            return str(arguments[key])
    return ""


def _safe_stat(path: Path) -> os.stat_result:
    return os.stat(path)


# ── Implementación de las 4 tools ─────────────────────────────────────────


def _execute_read(
    arguments: dict[str, Any],
    scope_root: str,
) -> ToolResult:
    from .contracts import _now_iso

    raw_path = _path_from_arguments(arguments)
    if not raw_path:
        raise ScopeReadDenied("read requires path argument")

    resolved = assert_within_scope(raw_path, scope_root)
    if not resolved.exists:
        raise BridgeError("file not found", details={"path": raw_path})

    target = Path(resolved.canonical)
    stat_before = _safe_stat(target)
    if not target.is_file():
        raise ScopeReadDenied("not a regular file", details={"path": raw_path})

    truncated = False
    with target.open("rb") as f:
        data = f.read(MAX_READ_BYTES + 1)
    if len(data) > MAX_READ_BYTES:
        data = data[:MAX_READ_BYTES]
        truncated = True
    text = data.decode("utf-8", errors="replace")
    # TOCTOU: re-stat tras la lectura.
    stat_after = _safe_stat(target)
    if (stat_after.st_dev, stat_after.st_ino) != (
        stat_before.st_dev,
        stat_before.st_ino,
    ):
        raise ScopeToctouDetected(
            "file identity changed during read",
            details={"path": str(target)},
        )
    return ToolResult(
        tool="read",
        output=text,
        size_bytes=len(data),
        truncated=truncated,
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )


def _execute_ls(
    arguments: dict[str, Any],
    scope_root: str,
) -> ToolResult:
    from .contracts import _now_iso

    raw_path = _path_from_arguments(arguments) or "."
    resolved = assert_within_scope(raw_path, scope_root)
    target = Path(resolved.canonical)
    if not target.exists:
        raise BridgeError("directory not found", details={"path": raw_path})
    if not target.is_dir():
        raise ScopeReadDenied("not a directory", details={"path": raw_path})

    entries: list[dict[str, Any]] = []
    truncated = False
    with os.scandir(target) as it:
        for i, entry in enumerate(it):
            if i >= MAX_LS_ENTRIES:
                truncated = True
                break
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            try:
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                is_file = False
            try:
                is_symlink = entry.is_symlink()
            except OSError:
                is_symlink = False
            entries.append(
                {
                    "name": entry.name,
                    "is_dir": is_dir,
                    "is_file": is_file,
                    "is_symlink": is_symlink,
                }
            )
    return ToolResult(
        tool="ls",
        output=entries,
        size_bytes=len(entries),
        truncated=truncated,
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )


def _execute_grep(
    arguments: dict[str, Any],
    scope_root: str,
) -> ToolResult:
    from .contracts import _now_iso

    pattern = arguments.get("pattern") or arguments.get("regex")
    if not isinstance(pattern, str) or not pattern:
        raise CapabilityDenied("grep requires non-empty pattern")
    raw_path = _path_from_arguments(arguments) or "."
    resolved = assert_within_scope(raw_path, scope_root)
    target = Path(resolved.canonical)
    if not target.exists:
        raise BridgeError("path not found", details={"path": raw_path})
    if target.is_dir():
        # Búsqueda recursiva limitada a archivos regulares bajo el dir.
        files: list[Path] = []
        for p in target.rglob("*"):
            if not p.is_file():
                continue
            files.append(p)
            if len(files) >= MAX_FIND_ENTRIES:
                break
    elif target.is_file():
        files = [target]
    else:
        raise ScopeReadDenied("not a regular file or directory", details={"path": raw_path})

    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise CapabilityDenied("invalid regex", details={"error": str(exc)})

    results: list[dict[str, Any]] = []
    truncated = False
    for file in files:
        if len(results) >= MAX_GREP_RESULTS:
            truncated = True
            break
        try:
            with file.open("rb") as f:
                data = f.read(MAX_GREP_BYTES_PER_FILE + 1)
            if len(data) > MAX_GREP_BYTES_PER_FILE:
                data = data[:MAX_GREP_BYTES_PER_FILE]
                truncated = True
            text = data.decode("utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                results.append(
                    {
                        "file": str(file.relative_to(target if target.is_dir() else file.parent)),
                        "line": line_no,
                        "content": line[:1024],
                    }
                )
                if len(results) >= MAX_GREP_RESULTS:
                    truncated = True
                    break
    return ToolResult(
        tool="grep",
        output=results,
        size_bytes=len(results),
        truncated=truncated,
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )


def _execute_find(
    arguments: dict[str, Any],
    scope_root: str,
) -> ToolResult:
    from .contracts import _now_iso

    raw_path = _path_from_arguments(arguments) or "."
    name = arguments.get("name")
    type_filter = arguments.get("type")  # "file" | "dir" | "any"
    max_depth = int(arguments.get("max_depth") or MAX_FIND_DEPTH)
    if max_depth < 0 or max_depth > MAX_FIND_DEPTH:
        raise CapabilityDenied(
            "max_depth out of range",
            details={"max": MAX_FIND_DEPTH, "got": max_depth},
        )

    resolved = assert_within_scope(raw_path, scope_root)
    target = Path(resolved.canonical)
    if not target.exists:
        raise BridgeError("path not found", details={"path": raw_path})

    entries: list[dict[str, Any]] = []
    truncated = False

    def _walk(path: Path, depth: int) -> Iterable[Path]:
        if depth > max_depth:
            return
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            # No seguimos symlinks (defensa contra escape).
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            yield Path(entry.path)
                            yield from _walk(Path(entry.path), depth + 1)
                        elif entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                    except OSError:
                        continue
        except (OSError, PermissionError):
            return

    for path in _walk(target, 0):
        if len(entries) >= MAX_FIND_ENTRIES:
            truncated = True
            break
        if name and name not in path.name:
            continue
        is_dir = path.is_dir()
        is_file = path.is_file()
        if type_filter == "file" and not is_file:
            continue
        if type_filter == "dir" and not is_dir:
            continue
        entries.append({"path": str(path), "is_dir": is_dir, "is_file": is_file})
    return ToolResult(
        tool="find",
        output=entries,
        size_bytes=len(entries),
        truncated=truncated,
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )


_EXECUTORS = {
    "read": _execute_read,
    "ls": _execute_ls,
    "grep": _execute_grep,
    "find": _execute_find,
}


# ── API pública ───────────────────────────────────────────────────────────


def invoke_tool(
    *,
    tool: str,
    arguments: dict[str, Any],
    scope_root: str,
    execution_id: str,
    tool_call_id: str,
    claims,
) -> ToolDecision:
    """Invoca una tool y devuelve la decisión + resultado.

    Lanza `ToolNotAllowed` si la tool no está en el allowlist o si
    `claims` no la habilita. Lanza `ScopeReadDenied` / `ScopePathDenied`
    / `ScopeLinkEscapeDenied` / `ScopeToctouDetected` si la tool
    toca rutas inválidas.
    """
    # 1. Tool en allowlist global.
    if tool not in ALLOWED_TOOLS:
        raise ToolNotAllowed(
            f"tool not in allowlist: {tool}",
            details={"tool": tool},
        )
    # 2. Tool declarada en claims.
    policy = decide_tool(claims, tool)
    if not policy.allowed:
        raise ToolNotAllowed(
            f"tool not allowed by claims: {tool}",
            details={"reason_code": policy.reason_code},
        )
    # 3. Ejecutar.
    executor = _EXECUTORS[tool]
    try:
        result = executor(arguments, scope_root)
    except ToolNotAllowed:
        raise
    except ScopePathDenied:
        raise
    except ScopeLinkEscapeDenied:
        raise
    except ScopeToctouDetected:
        raise
    except ScopeReadDenied:
        raise
    except OutputLimitExceeded:
        raise
    except BridgeError:
        raise
    except OSError as exc:
        # Errores de I/O se traducen a BridgeError.
        raise BridgeError(
            "tool I/O failed",
            details={"tool": tool, "error": str(exc)},
        ) from exc
    return ToolDecision(allowed=True, tool=tool, rule_code="PI_TOOL_OK", result=result)


def build_tool_receipt(
    *,
    tool_call_id: str,
    execution_id: str,
    tool: str,
    arguments: dict[str, Any],
    requested_path: str,
    scope_root: str,
    decision: ToolDecision,
) -> Any:
    """Construye el `ToolReceipt` canónico (o uno de denegación)."""
    from .contracts import ToolReceipt as CanonicalToolReceipt
    now_args = {
        "tool_call_id": tool_call_id,
        "execution_id": execution_id,
        "tool": tool,
        "arguments": arguments,
        "requested_path": requested_path,
        "scope_root": scope_root,
        "rule_code": decision.rule_code,
    }
    if not decision.allowed or decision.result is None:
        return CanonicalToolReceipt.deny(**now_args)
    result = decision.result
    # Resolved path: para `read`/`ls`/`grep`/`find` el path resuelto
    # vive en la lógica de scope_validator; el bridge lo extrae del
    # resultado si está disponible.
    resolved_path = requested_path
    if tool == "read" and isinstance(result.output, str):
        # En read el path canónico viene del assert_within_scope
        # ejecutado dentro de _execute_read; no lo duplicamos aquí.
        resolved_path = requested_path
    content_hash = result.content_hash()
    from .contracts import _now_iso

    now = _now_iso()
    return CanonicalToolReceipt(
        tool_call_id=tool_call_id,
        execution_id=execution_id,
        tool=tool,
        proxy_version=PROXY_VERSION,
        arguments=dict(arguments),
        arguments_hash=hashlib.sha256(
            _canonical_json(arguments).encode("utf-8")
        ).hexdigest()[:16],
        requested_path=requested_path,
        resolved_path=resolved_path,
        scope_root=scope_root,
        policy_decision="allow",
        policy_rule_code=decision.rule_code,
        approval_id="",
        status="completed" if not result.truncated else "allowed_truncated",
        result_size_bytes=result.size_bytes,
        result_hash=content_hash,
        evidence_refs=(),
        redactions_applied=("content",) if result.truncated else (),
        requested_at=result.started_at,
        decided_at=now,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


def _canonical_json(payload: Any) -> str:
    import json

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


__all__ = [
    "ToolResult",
    "ToolDecision",
    "invoke_tool",
    "build_tool_receipt",
    "MAX_READ_BYTES",
    "MAX_LS_ENTRIES",
    "MAX_GREP_RESULTS",
    "MAX_FIND_ENTRIES",
    "MAX_FIND_DEPTH",
    "PROXY_VERSION",
]
