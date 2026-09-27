#!/usr/bin/env python3
"""Static inventory of BAGO effect sinks.

This is an audit tool, not an authorization mechanism. It answers:

    Where can BAGO currently cause observable effects?
    Which canonical effect_id best describes each sink?
    Is that sink already behind the ExecutionGateway?

Default mode is report-only so the existing migration can be measured without
breaking CI. ``--strict`` is the runtime closure gate: it exits non-zero while
runtime sinks remain unbound. ``--strict-classification`` is the inventory
completeness gate; it fails if a finding has no explicit scope or disposition.

The scanner covers high-signal material-effect patterns in the executable
languages used by the runtime and installer entrypoints. It intentionally
prefers visible audit candidates over silent effect sinks; it is not a proof of
complete language coverage.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SQLITE_EFFECT_ID = "database.write"

DEFAULT_ROOTS = (
    REPO_ROOT / "backend",
    REPO_ROOT / "scripts",
    REPO_ROOT / "electron-viewer",
    REPO_ROOT / "frontend",
    REPO_ROOT / "releases",
    REPO_ROOT / "manager" / "android",
    REPO_ROOT / "ARRANCAR_BAGO.bat",
    REPO_ROOT / "DETENER_BAGO.bat",
    REPO_ROOT / "install-remote.ps1",
    REPO_ROOT / "update-release-v4.8.4.ps1",
    REPO_ROOT / "update-release-v4.8.4.sh",
)
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
}

# The first materialized gateway owns its own authorization ledger. This is an
# authority-internal persistence sink, not a bypass around itself.
INTERNAL_AUTHORITY_PATHS = {
    "backend/.bago/core/authorization_boundary.py",
    # SQLite claim leases and operation receipts are coordination metadata
    # owned by the ExecutionGateway / governed plan pipeline. The claim-store
    # resolver is invoked by the gateway only after its Permit is consumed;
    # the standalone autonomous-loop use is a single-instance coordination
    # lock and does not authorize or materialize the loop's business effects.
    "backend/.bago/core/execution_claims.py",
    "backend/.bago/core/execution_operations.py",
    # The singleton CLI startup lease serializes server startup and teardown;
    # it is process coordination metadata, not application/workspace content.
    "backend/bago_core/instance_lock.py",
}

# These implementations are reached only through registered, server-owned
# ExecutionGateway adapters. They remain inventory findings; their binding is
# evidence of that ownership, not an exclusion from the audit.
GATEWAY_OWNED_PATHS = {
    "backend/.bago/core/filesystem_effects.py",
    # ProjectWriteEffectAdapter owns patch application and recovery through
    # project.write operation-bound Permit requests.
    "backend/.bago/core/workspace_patch_storage.py",
    # Project lifecycle materializers are called by ProjectWriteEffectAdapter;
    # their public CLI/REPL/API entrypoints all dispatch through project.write.
    "backend/.bago/tools/project_memory.py",
    # The project seed serializer is loaded only by project_memory.seed_project,
    # after its consumed project.write authorization check. The adapter path
    # test below proves project_memory lifecycle calls have one gateway caller.
    "backend/.bago/seed.py",
    # Evidence bundle I/O is reachable from the public API only through the
    # strong CLI request; its private materializer is called by the registered
    # EvidenceBundleGenerateEffectAdapter and commits a sibling stage atomically.
    "backend/bago_core/evidence_io.py",
    # A consumed system.update.apply Permit creates a one-use, operation-bound
    # ticket before the detached helper is spawned. The PowerShell helper
    # checks the canonical consumed-Permit ledger record, exact request target
    # and own file hash, then claims the ticket before any other effect;
    # direct invocation and changed-target replay are tested pre-effect denials.
    "backend/.bago/api/apply_release_update.ps1",
    # system.install.apply starts this detached, elevated helper only after it
    # validates the canonical consumed-Permit record, request/proof/decision,
    # helper/source/config digests and exact options. The elevated child claims
    # the one-use ticket before running install materializers; direct invocation
    # is covered by a Windows pre-elevation denial test.
    "backend/install-v4.ps1",
    # system.install.uninstall invokes this active-CLI helper after consuming
    # the strong desktop Permit. The helper checks the canonical consumed
    # request/proof/decision, exact install-tree fingerprint and ticket nonce,
    # then claims the one-use ticket before backup, PATH/registry writes or
    # removal. Direct CLI invocation without that ticket is tested fail-closed.
    "backend/.bago/core/execution_adapters/install_uninstall_lifecycle.py",
    # Database schema helpers are private to DatabaseWriteEffectAdapter; the
    # default gateway registry binds its only canonical effect_id to that
    # adapter. The inventory test checks both the runtime registration and
    # that the schema/materializer helpers have no call sites outside it.
    "backend/.bago/core/execution_adapters/database_write.py",
}
EXECUTION_GATEWAY_PATH = "backend/.bago/core/execution_gateway.py"

SCOPE_RUNTIME_AUTHORITY = "runtime_authority"
SCOPE_RUNTIME_TOOL_PENDING = "runtime_tool_pending"
SCOPE_RUNTIME_CLIENT_TRANSPORT = "runtime_client_transport"
SCOPE_TEST = "test"
SCOPE_BUILD_RELEASE_ADMIN = "build_release_admin"
SCOPE_DERIVED_RELEASE_SNAPSHOT = "derived_release_snapshot"
SCOPE_UNCLASSIFIED = "unclassified"

NON_RUNTIME_SCOPES = frozenset({
    SCOPE_TEST,
    SCOPE_BUILD_RELEASE_ADMIN,
    SCOPE_DERIVED_RELEASE_SNAPSHOT,
    SCOPE_RUNTIME_CLIENT_TRANSPORT,
})

# These backend/scripts files are reachable from runtime launchers or the
# legacy manager UI. The directory is otherwise treated as build/release admin.
RUNTIME_SCRIPT_ENTRYPOINTS = frozenset({
    "backend/scripts/bago_supervisor.py",
    "backend/scripts/bago_supervisor.pyw",
    "backend/scripts/publish_release.py",
    # These scripts are selected by the supported Electron/runtime lifecycle;
    # they are not build-only helpers despite living under scripts/.
    "backend/scripts/runtime-service.ps1",
    "scripts/dev.ps1",
})

# High-signal Python call suffixes. Suffix matching is intentional because Path
# instances are often local variables, not literal pathlib.Path expressions.
PYTHON_SUFFIX_RULES: tuple[tuple[str, str, str], ...] = (
    (".write_text", "filesystem.write", "high"),
    (".write_bytes", "filesystem.write", "high"),
    (".unlink", "filesystem.delete", "high"),
    (".rmdir", "filesystem.delete", "high"),
    (".mkdir", "filesystem.write", "medium"),
    (".rename", "filesystem.write", "medium"),
    ("os.remove", "filesystem.delete", "high"),
    ("os.unlink", "filesystem.delete", "high"),
    ("os.rmdir", "filesystem.delete", "high"),
    ("os.removedirs", "filesystem.delete", "high"),
    ("os.rename", "filesystem.write", "high"),
    ("os.replace", "filesystem.write", "high"),
    ("os.mkdir", "filesystem.write", "high"),
    ("os.makedirs", "filesystem.write", "high"),
    ("shutil.rmtree", "filesystem.delete", "high"),
    ("shutil.move", "filesystem.write", "high"),
    ("shutil.copy", "filesystem.write", "high"),
    ("shutil.copy2", "filesystem.write", "high"),
    ("shutil.copyfile", "filesystem.write", "high"),
    ("shutil.copytree", "filesystem.write", "high"),
    ("py_compile.compile", "filesystem.write", "medium"),
    ("tempfile.NamedTemporaryFile", "filesystem.write", "high"),
    ("tempfile.TemporaryFile", "filesystem.write", "high"),
    ("tempfile.mkstemp", "filesystem.write", "high"),
    ("tempfile.mkdtemp", "filesystem.write", "high"),
    ("subprocess.run", "process.execute", "high"),
    ("subprocess.Popen", "process.execute", "high"),
    ("subprocess.call", "process.execute", "high"),
    ("subprocess.check_call", "process.execute", "high"),
    ("subprocess.check_output", "process.execute", "high"),
    ("os.system", "process.execute", "high"),
    ("urllib.request.urlopen", "network.read", "medium"),
    ("requests.get", "network.read", "high"),
    ("requests.head", "network.read", "high"),
    ("requests.post", "network.external_write", "high"),
    ("requests.put", "network.external_write", "high"),
    ("requests.patch", "network.external_write", "high"),
    ("requests.delete", "network.external_write", "high"),
    ("httpx.get", "network.read", "high"),
    ("httpx.post", "network.external_write", "high"),
    ("httpx.put", "network.external_write", "high"),
    ("httpx.patch", "network.external_write", "high"),
    ("httpx.delete", "network.external_write", "high"),
)

POWERSHELL_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bRemove-Item\b", re.I), "filesystem.delete", "high"),
    (re.compile(r"\bExpand-Archive\b", re.I), "filesystem.write", "high"),
    (re.compile(r"\b(?:New-ItemProperty|Set-Item|Remove-ItemProperty|Clear-ItemProperty)\b", re.I), "system.configuration.write", "high"),
    (re.compile(r"\[\s*(?:System\.IO\.)?File\s*\]\s*::\s*(?:WriteAllText|WriteAllBytes|AppendAllText|AppendAllBytes)\s*\(", re.I), "filesystem.write", "high"),
    (re.compile(r"\[\s*(?:System\.)?Environment\s*\]\s*::\s*SetEnvironmentVariable\s*\(", re.I), "system.configuration.write", "high"),
    (re.compile(r"\b(?:Set-Content|Add-Content|Out-File|Copy-Item|Move-Item|New-Item)\b", re.I), "filesystem.write", "medium"),
    (re.compile(r"\bStop-Process\b", re.I), "process.terminate", "high"),
    (re.compile(r"\b(?:taskkill(?:\.exe)?|tskill(?:\.exe)?)\b", re.I), "process.terminate", "high"),
    (re.compile(r"\bStart-Process\b", re.I), "process.execute", "high"),
    # PowerShell's call operator can invoke external programs via literal or
    # computed command names; dot-sourcing executes another script in-process.
    # Keep both visible as process effects instead of assuming Start-Process
    # is the only process-launch form.
    (re.compile(r"(?m)^\s*&\s*(?:\$[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*|[A-Za-z_][\w.-]*)(?=\s|$)"), "process.execute", "high"),
    (re.compile(r"(?m)^\s*\.\s+(?:\$[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*|'[^']+'|\"[^\"]+\")"), "process.execute", "high"),
    (re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod)\b.*\s-Method\s+(?:POST|PUT|PATCH|DELETE)\b", re.I), "network.external_write", "high"),
    (re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod)\b.*\s-OutFile\b", re.I), "filesystem.write", "high"),
    (re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod)\b", re.I), "network.read", "medium"),
)

JS_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"(?<![\w$.])(?:child_process\.)?(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork)\s*\("), "process.execute", "high"),
    (re.compile(r"\b(?!process\.kill\b)[A-Za-z_$][\w$]*\.kill\s*\("), "process.terminate", "high"),
    (re.compile(r"\bprocess\.kill\s*\([^,]+,\s*(?!0\s*\))[^)]+\)"), "process.terminate", "high"),
    (re.compile(r"\b(?:fs\.)?(?:writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|copyFile|copyFileSync|rename|renameSync)\s*\("), "filesystem.write", "medium"),
    (re.compile(r"\b(?:fs\.)?(?:unlink|unlinkSync|rm|rmSync|rmdir|rmdirSync)\s*\("), "filesystem.delete", "high"),
    (re.compile(r"\b(?:fs\.)?createWriteStream\s*\("), "filesystem.write", "high"),
    (re.compile(r"\b(?:window\.)?(?:localStorage|sessionStorage)\.setItem\s*\("), "state.write", "high"),
    (re.compile(r"\b(?:window\.)?(?:localStorage|sessionStorage)\.(?:removeItem|clear)\s*\("), "state.delete", "high"),
    (re.compile(r"\bnet\.(?:connect|createConnection)\s*\("), "network.read", "medium"),
)

HTML_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"<(?:script|iframe|img|link)\b(?=[^>]*\b(?:src|href)\s*=\s*['\"]https?://)[^>]*>", re.I), "network.read", "high"),
)

VBSCRIPT_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:WScript\.Shell|objShell|shell)\.(?:Run|Exec|ShellExecute)(?:\s*\(|\s+)", re.I), "process.execute", "high"),
    (re.compile(r"\.(?:CreateTextFile|CreateFolder|CopyFile|MoveFile)\s*\(", re.I), "filesystem.write", "high"),
    (re.compile(r"\.(?:DeleteFile|DeleteFolder)\s*\(", re.I), "filesystem.delete", "high"),
    (re.compile(r"\.(?:RegWrite|RegDelete)(?:\s*\(|\s+)", re.I), "system.configuration.write", "high"),
)

NSIS_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"^\s*(?:Exec|ExecWait|ExecShell)\b", re.I), "process.execute", "high"),
    (re.compile(r"^\s*(?:InitPluginsDir|File|SetOutPath|CopyFiles|Rename|CreateDirectory|CreateShortcut|WriteUninstaller)\b", re.I), "filesystem.write", "high"),
    (re.compile(r"^\s*(?:Delete|RMDir)\b", re.I), "filesystem.delete", "high"),
    (re.compile(r"^\s*(?:WriteReg\w*|DeleteRegKey|DeleteRegValue)\b", re.I), "system.configuration.write", "high"),
)

# Shell and cmd are launcher languages in the BAGO runtime/build tree. These
# rules are intentionally high-signal; dynamic command construction still
# requires source review and must not be mistaken for complete static proof.
SHELL_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\b(?:exec|nohup|bash|sh|cmd|powershell|pwsh|pythonw?|python3|node|npm|npx|electron|gh|gpg|curl|wget)\b"), "process.execute", "high"),
    (re.compile(r"\b(?:taskkill(?:\.exe)?|tskill(?:\.exe)?)\b", re.I), "process.terminate", "high"),
    (re.compile(r"\bkill\s+(?!-0\b)"), "process.terminate", "high"),
    (re.compile(r"\b(?:mkdir|mktemp|touch|cp|mv|install)\b"), "filesystem.write", "medium"),
    (re.compile(r"\b(?:rm|rmdir|unlink)\b"), "filesystem.delete", "high"),
    (re.compile(r"(?:^|[^>])>{1,2}\s*(?:\S+)"), "filesystem.write", "medium"),
)

CMD_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"^\s*(?:start|call)\s+|^\s*(?:powershell|pwsh|pythonw?|python3?|node|npm|npx|cmd|wsl|certutil|gh|gpg)\b", re.I), "process.execute", "high"),
    (re.compile(r"\b(?:taskkill|tskill)\b", re.I), "process.terminate", "high"),
    (re.compile(r"^\s*(?:del|erase|rmdir)\b", re.I), "filesystem.delete", "high"),
    (re.compile(r"^\s*(?:mkdir|md|copy|xcopy|move)\b|\bcertutil\b.*>\s*", re.I), "filesystem.write", "medium"),
    (re.compile(r"^\s*reg\s+(?:add|delete)\b|^\s*setx\b", re.I), "system.configuration.write", "high"),
    (re.compile(r">>{1,2}\s*\S+"), "filesystem.write", "medium"),
)


@dataclass(frozen=True, slots=True)
class SinkFinding:
    path: str
    line: int
    column: int
    language: str
    sink: str
    effect_id: str
    confidence: str
    binding: str
    scope: str
    binding_class: str
    binding_reason: str
    excerpt: str


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _scope_for(path: Path) -> str:
    """Assign every scanned path to an explicit audit scope.

    Scope is deliberately separate from gateway binding. Tests, packaging and
    release projections still contain real effect calls, but they are not
    runtime authority. They remain visible in the inventory and are never
    silently treated as gateway adapters.
    """

    rel = _relative(path)
    parts = set(rel.split("/"))
    if rel in {
        "ARRANCAR_BAGO.bat",
        "DETENER_BAGO.bat",
        "install-remote.ps1",
    }:
        return SCOPE_RUNTIME_AUTHORITY
    if rel in {"update-release-v4.8.4.ps1", "update-release-v4.8.4.sh"}:
        return SCOPE_BUILD_RELEASE_ADMIN
    if rel.startswith(("releases/compiled/", "releases/ci-artifact/")):
        return SCOPE_DERIVED_RELEASE_SNAPSHOT
    if rel.startswith("manager/android/"):
        return SCOPE_RUNTIME_AUTHORITY
    if rel.startswith("releases/"):
        if Path(rel).name.startswith(("build-", "resolve-")):
            return SCOPE_BUILD_RELEASE_ADMIN
        return SCOPE_RUNTIME_AUTHORITY
    if rel.startswith("backend/release/"):
        return SCOPE_DERIVED_RELEASE_SNAPSHOT
    if "tests" in parts or rel.startswith("backend/tests_local/"):
        return SCOPE_TEST
    if rel in {"frontend/capture_screenshots.mjs"} or rel.startswith("frontend/scripts/"):
        return SCOPE_BUILD_RELEASE_ADMIN
    if rel.startswith("frontend/"):
        return SCOPE_RUNTIME_CLIENT_TRANSPORT
    if rel in RUNTIME_SCRIPT_ENTRYPOINTS:
        return SCOPE_RUNTIME_AUTHORITY
    if (
        rel.startswith("scripts/")
        or rel.startswith("backend/scripts/")
        or rel.startswith("backend/tools/")
    ):
        return SCOPE_BUILD_RELEASE_ADMIN
    if rel.startswith("backend/.bago/tools/"):
        return SCOPE_RUNTIME_TOOL_PENDING
    if rel.startswith("backend/") or rel.startswith("electron-viewer/"):
        return SCOPE_RUNTIME_AUTHORITY
    return SCOPE_UNCLASSIFIED


def _scope_for_effect(path: Path, effect_id: str | None = None) -> str:
    scope = _scope_for(path)
    if scope == SCOPE_RUNTIME_CLIENT_TRANSPORT and effect_id in {"state.write", "state.delete"}:
        return SCOPE_RUNTIME_AUTHORITY
    return scope


def _ownership_for(
    path: Path,
    *,
    effect_id: str | None = None,
    gateway_owned_adapter: bool = False,
) -> tuple[str, str, str]:
    rel = _relative(path)
    if rel in INTERNAL_AUTHORITY_PATHS:
        return (
            "authority_internal",
            "authority_internal",
            "AuthorizationBoundary owns its persistence ledger",
        )
    if rel in GATEWAY_OWNED_PATHS or gateway_owned_adapter:
        return (
            "gateway_owned",
            "gateway_adapter",
            "server-owned EffectAdapter materializes this sink",
        )
    scope = _scope_for_effect(path, effect_id)
    if scope in NON_RUNTIME_SCOPES:
        return (
            "unbound",
            "nonruntime_effect",
            f"retained for audit; scope={scope} is not runtime authority",
        )
    if scope in {SCOPE_RUNTIME_AUTHORITY, SCOPE_RUNTIME_TOOL_PENDING}:
        return (
            "unbound",
            "runtime_unbound",
            "runtime sink requires a registered gateway owner",
        )
    return (
        "unbound",
        "unclassified",
        "path is outside the declared inventory scopes",
    )


def _binding_for(path: Path, *, gateway_owned_adapter: bool = False) -> str:
    """Compatibility projection for callers that only need the old binding."""

    return _ownership_for(path, gateway_owned_adapter=gateway_owned_adapter)[0]


def _qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _qualified_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return _qualified_name(node.func)
    return ""


def _literal_open_effect(call: ast.Call) -> tuple[str, str] | None:
    name = _qualified_name(call.func)
    if name not in {"open", "io.open", "Path.open", "pathlib.Path.open"} and not name.endswith(".open"):
        return None
    mode: str | None = None
    # Built-in open(file, mode) and io.open(file, mode) carry the mode in
    # position 1. A bound Path.open(mode) carries it in position 0; the
    # unbound Path.open(path, mode) form again carries it in position 1.
    mode_index = 1 if name in {"open", "io.open"} or len(call.args) >= 2 else 0
    if len(call.args) > mode_index and isinstance(call.args[mode_index], ast.Constant):
        value = call.args[mode_index].value
        if isinstance(value, str):
            mode = value
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            mode = keyword.value.value
    if mode and any(flag in mode for flag in ("w", "a", "x", "+")):
        return ("filesystem.write", "medium")
    return None


_SQL_MUTATION = re.compile(
    r"^(?:CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|REPLACE|VACUUM|REINDEX|ATTACH|DETACH)\b",
    re.IGNORECASE,
)
_SQL_CONNECTION_PRAGMA = re.compile(
    r"^PRAGMA\s+(?:busy_timeout|synchronous|foreign_keys|cache_size|temp_store|query_only)\s*=",
    re.IGNORECASE,
)


def _literal_database_write_effect(call: ast.Call) -> tuple[str, str] | None:
    name = _qualified_name(call.func)
    if name == "sqlite3.connect":
        if call.args and isinstance(call.args[0], ast.Constant):
            value = call.args[0].value
            if isinstance(value, str) and (value == ":memory:" or value.startswith("file::memory:")):
                return None
        uri_enabled = any(
            keyword.arg == "uri"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in call.keywords
        )
        if uri_enabled and call.args:
            uri_literals = "".join(
                node.value
                for node in ast.walk(call.args[0])
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            )
            if re.search(r"(?:\?|&)mode=ro(?:&|$)", uri_literals, re.IGNORECASE):
                return None
        return (SQLITE_EFFECT_ID, "medium")
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in {"execute", "executemany", "executescript"}:
        return None
    if not call.args:
        return None
    statement = call.args[0]
    if isinstance(statement, ast.Constant) and isinstance(statement.value, str):
        sql = statement.value.strip()
    elif isinstance(statement, ast.JoinedStr):
        sql = "".join(
            part.value for part in statement.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ).strip()
    elif call.func.attr == "executescript":
        # executescript is an explicitly multi-statement database operation;
        # callers may pass a schema constant or a generated script.
        return (SQLITE_EFFECT_ID, "medium")
    elif isinstance(statement, ast.Name) and any(
        token in statement.id.casefold() for token in ("sql", "query", "statement", "schema")
    ):
        return (SQLITE_EFFECT_ID, "low")
    else:
        return None
    if _SQL_CONNECTION_PRAGMA.match(sql):
        # These PRAGMAs configure the connection, not persistent database
        # contents. Keep persistent journal-mode changes visible below.
        return None
    if _SQL_MUTATION.match(sql) or re.match(r"^PRAGMA\s+[A-Za-z_][A-Za-z0-9_]*\s*=", sql, re.IGNORECASE):
        return (SQLITE_EFFECT_ID, "high")
    return None


def _classify_python_call(call: ast.Call) -> tuple[str, str] | None:
    opened = _literal_open_effect(call)
    if opened is not None:
        return opened
    database_write = _literal_database_write_effect(call)
    if database_write is not None:
        return database_write
    name = _qualified_name(call.func)
    for suffix, effect_id, confidence in PYTHON_SUFFIX_RULES:
        if name == suffix or name.endswith(suffix):
            return (effect_id, confidence)
    return None


def _archive_handle_names(tree: ast.AST) -> set[str]:
    """Find simple local names bound to ZipFile objects for write/extract calls."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            items = node.items
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            items = []
            if isinstance(value, ast.Call) and _qualified_name(value.func).endswith("ZipFile"):
                for target in targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            continue
        else:
            continue
        for item in items:
            context = item.context_expr
            if not isinstance(context, ast.Call) or not _qualified_name(context.func).endswith("ZipFile"):
                continue
            if isinstance(item.optional_vars, ast.Name):
                names.add(item.optional_vars.id)
    return names


def _temporary_file_handle_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            items = node.items
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            items = []
            if isinstance(value, ast.Call) and _qualified_name(value.func).endswith("NamedTemporaryFile"):
                for target in targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
            continue
        else:
            continue
        for item in items:
            context = item.context_expr
            if not isinstance(context, ast.Call) or not _qualified_name(context.func).endswith("NamedTemporaryFile"):
                continue
            if isinstance(item.optional_vars, ast.Name):
                names.add(item.optional_vars.id)
    return names


def _literal_zipfile_write(call: ast.Call) -> tuple[str, str] | None:
    name = _qualified_name(call.func)
    if not name.endswith("ZipFile"):
        return None
    mode: str | None = None
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        mode = call.args[1].value
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            mode = keyword.value.value
    if mode and any(flag in mode for flag in ("w", "x", "a")):
        return ("filesystem.write", "high")
    return None


def _line_excerpt(lines: list[str], line: int) -> str:
    if 1 <= line <= len(lines):
        return " ".join(lines[line - 1].strip().split())[:240]
    return ""


def _gateway_owned_adapter_ranges(path: Path, tree: ast.AST) -> tuple[tuple[int, int], ...]:
    """Return concrete adapter spans in gateway dispatch or implementation modules."""
    relative = _relative(path)
    adapter_module = relative.startswith("backend/.bago/core/execution_adapters/")
    if relative != EXECUTION_GATEWAY_PATH and not adapter_module:
        return ()
    return tuple(
        (
            int(getattr(node, "lineno", 0) or 0),
            int(getattr(node, "end_lineno", 0) or 0),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and node.name != "EffectAdapter"
        and node.name.endswith("EffectAdapter")
    )


def _is_in_ranges(line: int, ranges: Iterable[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in ranges)


def scan_python(path: Path) -> list[SinkFinding]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []
    lines = source.splitlines()
    archive_handles = _archive_handle_names(tree)
    temporary_file_handles = _temporary_file_handle_names(tree)
    gateway_owned_adapter_ranges = _gateway_owned_adapter_ranges(path, tree)
    findings: list[SinkFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        classification = _classify_python_call(node)
        call_name = _qualified_name(node.func)
        if classification is None:
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id in archive_handles and node.func.attr in {"write", "writestr", "extract", "extractall"}:
                    classification = ("filesystem.write", "high")
                elif node.func.value.id in temporary_file_handles and node.func.attr == "write":
                    classification = ("filesystem.write", "high")
            if classification is None:
                classification = _literal_zipfile_write(node)
        if classification is None:
            continue
        effect_id, confidence = classification
        line = int(getattr(node, "lineno", 0) or 0)
        binding, binding_class, binding_reason = _ownership_for(
            path,
            effect_id=effect_id,
            gateway_owned_adapter=_is_in_ranges(line, gateway_owned_adapter_ranges),
        )
        findings.append(
            SinkFinding(
                path=_relative(path),
                line=int(getattr(node, "lineno", 0) or 0),
                column=int(getattr(node, "col_offset", 0) or 0),
                language="python",
                sink=call_name or "<call>",
                effect_id=effect_id,
                confidence=confidence,
                binding=binding,
                scope=_scope_for_effect(path, effect_id),
                binding_class=binding_class,
                binding_reason=binding_reason,
                excerpt=_line_excerpt(lines, line),
            )
        )
    return findings


def _js_call_context(lines: list[str], line_index: int, opening_paren: int) -> str:
    """Collect one bounded JavaScript call across lines with string awareness."""
    depth = 0
    quote = ""
    escaped = False
    pieces: list[str] = []
    for row, current in enumerate(lines[line_index:min(line_index + 40, len(lines))]):
        for offset, char in enumerate(current):
            if row == 0 and offset < opening_paren:
                continue
            pieces.append(char)
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in {"'", '"', "`"}:
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return "".join(pieces)
        pieces.append("\n")
    return "".join(pieces)


def _js_second_argument(call: str) -> str | None:
    """Return a JS call's second argument without splitting nested commas."""
    depth = 0
    quote = ""
    escaped = False
    start = -1
    for index, char in enumerate(call):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            if depth == 1 and start >= 0:
                return call[start:index].strip()
            depth -= 1
        elif char == "," and depth == 1 and start < 0:
            start = index + 1
    return None


def _scan_text(path: Path, language: str, rules: Iterable[tuple[re.Pattern[str], str, str]]) -> list[SinkFinding]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    findings: list[SinkFinding] = []
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        if (language == "vbscript" and stripped.startswith("'")) or (
            language == "nsis" and stripped.startswith(";")
        ) or (language == "cmd" and re.match(r"(?i)^(?:rem\b|::)", stripped)):
            continue
        if language in {"javascript", "html"}:
            network_match = re.search(r"\b(fetch|(?:https?|http)\.request)\s*\(", line)
            if network_match:
                call = _js_call_context(lines, number - 1, network_match.end() - 1)
                second_argument = _js_second_argument(call)
                methods = re.findall(r"\bmethod\s*:\s*([^,}\s]+)", second_argument or "")
                has_spread = bool(re.search(r"\.\.\.\s*[A-Za-z_$][\w$]*", second_argument or ""))
                dynamic_options = bool(second_argument and not second_argument.lstrip().startswith("{"))
                mutating_method = any(
                    value.strip("'\"` ").upper() not in {"GET", "HEAD"}
                    for value in methods
                )
                effect_id = "network.external_write" if mutating_method or has_spread or dynamic_options else "network.read"
                confidence = "high" if any(value.strip("'\"` ").upper() in {"POST", "PUT", "PATCH", "DELETE"} for value in methods) else "medium"
                binding, binding_class, binding_reason = _ownership_for(path, effect_id=effect_id)
                findings.append(SinkFinding(
                    path=_relative(path),
                    line=number,
                    column=network_match.start(),
                    language=language,
                    sink=network_match.group(1),
                    effect_id=effect_id,
                    confidence=confidence,
                    binding=binding,
                    scope=_scope_for_effect(path, effect_id),
                    binding_class=binding_class,
                    binding_reason=binding_reason,
                    excerpt=" ".join(stripped.split())[:240],
                ))
        for pattern, effect_id, confidence in rules:
            match = pattern.search(line)
            if not match:
                continue
            if language in {"javascript", "html"} and effect_id == "process.terminate" and re.search(
                r"\bprocess\.kill\s*\([^,]+,\s*0\s*\)", line
            ):
                continue
            binding, binding_class, binding_reason = _ownership_for(path, effect_id=effect_id)
            findings.append(
                SinkFinding(
                    path=_relative(path),
                    line=number,
                    column=match.start(),
                    language=language,
                    sink=match.group(0)[:120],
                    effect_id=effect_id,
                    confidence=confidence,
                    binding=binding,
                    scope=_scope_for_effect(path, effect_id),
                    binding_class=binding_class,
                    binding_reason=binding_reason,
                    excerpt=" ".join(stripped.split())[:240],
                )
            )
            # One highest-value finding per rule on the line is sufficient.
    return findings


def _iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in {".py", ".pyw", ".ps1", ".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx", ".html", ".htm", ".cmd", ".bat", ".sh", ".vbs", ".nsi"} or path.name == "bago":
                yield path


def scan_paths(roots: Iterable[Path]) -> list[SinkFinding]:
    findings: list[SinkFinding] = []
    for path in _iter_files(roots):
        suffix = path.suffix.lower()
        if suffix in {".py", ".pyw"}:
            findings.extend(scan_python(path))
        elif suffix == ".ps1":
            findings.extend(_scan_text(path, "powershell", POWERSHELL_RULES))
        elif suffix in {".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx"}:
            findings.extend(_scan_text(path, "javascript", JS_RULES))
        elif suffix in {".html", ".htm"}:
            findings.extend(_scan_text(path, "html", (*HTML_RULES, *JS_RULES)))
        elif suffix in {".cmd", ".bat"}:
            findings.extend(_scan_text(path, "cmd", CMD_RULES))
        elif suffix == ".vbs":
            findings.extend(_scan_text(path, "vbscript", VBSCRIPT_RULES))
        elif suffix == ".nsi":
            findings.extend(_scan_text(path, "nsis", NSIS_RULES))
        elif suffix == ".sh" or path.name == "bago":
            findings.extend(_scan_text(path, "shell", SHELL_RULES))
    return sorted(findings, key=lambda item: (item.path, item.line, item.column, item.effect_id))


def build_inventory(roots: Iterable[Path] | None = None) -> dict[str, Any]:
    selected = tuple(roots or DEFAULT_ROOTS)
    findings = scan_paths(selected)
    by_effect = Counter(item.effect_id for item in findings)
    by_binding = Counter(item.binding for item in findings)
    by_scope = Counter(item.scope for item in findings)
    by_binding_class = Counter(item.binding_class for item in findings)
    high_confidence_unbound = [
        item for item in findings
        if item.binding == "unbound" and item.confidence == "high"
    ]
    runtime_unbound = [item for item in findings if item.binding_class == "runtime_unbound"]
    unclassified_scope = [item for item in findings if item.scope == SCOPE_UNCLASSIFIED]
    unclassified_binding = [item for item in findings if item.binding_class == "unclassified"]
    return {
        "schema": "bago.effect-sink-inventory.v1",
        "repo_root": str(REPO_ROOT),
        "roots": [_relative(path) for path in selected],
        "summary": {
            "total_sinks": len(findings),
            "unbound_sinks": sum(1 for item in findings if item.binding == "unbound"),
            "authority_internal_sinks": sum(1 for item in findings if item.binding == "authority_internal"),
            "high_confidence_unbound_sinks": len(high_confidence_unbound),
            "runtime_unbound_sinks": len(runtime_unbound),
            "runtime_high_confidence_unbound_sinks": sum(
                1 for item in runtime_unbound if item.confidence == "high"
            ),
            "unclassified_scope_sinks": len(unclassified_scope),
            "unclassified_binding_sinks": len(unclassified_binding),
            "by_effect": dict(sorted(by_effect.items())),
            "by_binding": dict(sorted(by_binding.items())),
            "by_binding_class": dict(sorted(by_binding_class.items())),
            "by_scope": dict(sorted(by_scope.items())),
        },
        "findings": [asdict(item) for item in findings],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory BAGO material effect sinks")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail while any runtime-authority sink remains unbound",
    )
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help="alias for --strict, kept explicit for CI/readability",
    )
    parser.add_argument(
        "--strict-classification",
        action="store_true",
        help="fail while any sink lacks an explicit scope or binding class",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="override scan roots relative to repository root; may be repeated",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    roots = tuple((REPO_ROOT / raw).resolve() for raw in args.root) if args.root else DEFAULT_ROOTS
    inventory = build_inventory(roots)
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        summary = inventory["summary"]
        print("BAGO effect-sink inventory")
        print(f"  total_sinks: {summary['total_sinks']}")
        print(f"  unbound_sinks: {summary['unbound_sinks']}")
        print(f"  runtime_unbound_sinks: {summary['runtime_unbound_sinks']}")
        print(f"  unclassified_scope_sinks: {summary['unclassified_scope_sinks']}")
        print(f"  unclassified_binding_sinks: {summary['unclassified_binding_sinks']}")
        print(f"  high_confidence_unbound_sinks: {summary['high_confidence_unbound_sinks']}")
        for effect_id, count in summary["by_effect"].items():
            print(f"  {effect_id}: {count}")
    summary = inventory["summary"]
    if (args.strict or args.strict_runtime) and summary["runtime_unbound_sinks"]:
        return 2
    if args.strict_classification and (
        summary["unclassified_scope_sinks"]
        or summary["unclassified_binding_sinks"]
    ):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
