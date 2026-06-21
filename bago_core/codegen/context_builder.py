"""BAGO Code Forge 3B — minimal context builder.

Step 3 of the BAGO Code Forge 3B pipeline. Turns a
:class:`CodeTaskContract` into a ``CodeContext`` object containing only
the information the model is allowed to see:

- the target file contents
- direct imports
- top-level symbols (functions, classes, constants)
- related tests
- 1-2 similar files (heuristic: same stem, neighbouring modules)
- the original error traceback, if any
- a copy of the contract itself

The builder is intentionally read-only. It never writes to the
workspace, never calls the model, and never shells out. Anything more
than AST analysis would betray the principle *"El modelo propone; BAGO
determina"*.

Design rules (R0-R10):

- R0: <200 lines.
- R1: pure data; ``CodeContext`` is a ``dataclass(frozen=True)``.
- R3: tolerant of missing files (returns empty lists, never raises).
- R4: deterministic — same contract + workspace ⇒ same context.
- R8: no ``print``, no ``subprocess``.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .task_compiler import CodeTaskContract

# Hard cap on the size of any single file dumped into the context. The
# pipeline must never feed an unbounded source blob to a 3B model.
MAX_FILE_BYTES = 64 * 1024

# Hard cap on number of similar files included. 1-2 is the spec; 2 is
# the absolute upper bound.
MAX_SIMILAR_FILES = 2


@dataclass(frozen=True)
class CodeSymbol:
    """One top-level symbol extracted from a Python source file."""

    name: str
    kind: str  # "function" | "class" | "constant" | "import"
    line: int


@dataclass(frozen=True)
class CodeFileSummary:
    """File metadata + a bounded body, ready to ship to the model."""

    path: str
    language: str
    exists: bool
    body: str = ""
    symbols: tuple[CodeSymbol, ...] = ()
    imports: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "language": self.language,
            "exists": self.exists,
            "body": self.body,
            "symbols": [
                {"name": s.name, "kind": s.kind, "line": s.line}
                for s in self.symbols
            ],
            "imports": list(self.imports),
        }


@dataclass(frozen=True)
class CodeContext:
    """The minimal, read-only context the model is permitted to see."""

    contract: CodeTaskContract
    target_summaries: tuple[CodeFileSummary, ...]
    related_tests: tuple[CodeFileSummary, ...]
    similar_files: tuple[CodeFileSummary, ...]
    error_excerpt: str = ""
    extra: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract.to_dict(),
            "target_summaries": [s.to_dict() for s in self.target_summaries],
            "related_tests": [s.to_dict() for s in self.related_tests],
            "similar_files": [s.to_dict() for s in self.similar_files],
            "error_excerpt": self.error_excerpt,
            "extra": dict(self.extra),
        }


def _read_bounded(path: Path) -> str:
    """Read up to ``MAX_FILE_BYTES`` of ``path``. Returns "" if missing."""
    if not path.is_file():
        return ""
    try:
        data = path.read_bytes()[:MAX_FILE_BYTES]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _extract_python_symbols(source: str) -> tuple[CodeSymbol, ...]:
    """Return top-level function/class/constant symbols of a Python file."""
    if not source.strip():
        return ()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # The validation pipeline will surface the error; the context
        # builder does not refuse — it just yields no symbols.
        return ()
    symbols: list[CodeSymbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(CodeSymbol(node.name, "function", node.lineno))
        elif isinstance(node, ast.ClassDef):
            symbols.append(CodeSymbol(node.name, "class", node.lineno))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                name = getattr(target, "id", None)
                if name:
                    symbols.append(CodeSymbol(name, "constant", node.lineno))
    return tuple(symbols)


def _extract_python_imports(source: str) -> tuple[str, ...]:
    if not source.strip():
        return ()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
    # dedupe, preserve order
    seen: dict[str, None] = {}
    for name in imports:
        seen.setdefault(name, None)
    return tuple(seen.keys())


def _summarise(path: Path, *, language: str | None = None) -> CodeFileSummary:
    body = _read_bounded(path)
    ext = path.suffix.lower()
    lang = language or {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".json": "data",
        ".yaml": "data",
        ".yml": "data",
        ".toml": "data",
    }.get(ext, "unknown")
    symbols = _extract_python_symbols(body) if lang == "python" else ()
    imports = _extract_python_imports(body) if lang == "python" else ()
    return CodeFileSummary(
        path=str(path),
        language=lang,
        exists=bool(body),
        body=body,
        symbols=symbols,
        imports=imports,
    )


def _candidate_test_paths(workspace: Path, target: Path) -> list[Path]:
    """Return likely test paths for ``target`` inside ``workspace``."""
    candidates: list[Path] = []
    stem = target.stem
    if not stem:
        return candidates
    tests_dir = workspace / "tests"
    for name in (f"test_{stem}.py", f"test_{stem}.js", f"test_{stem}.ts"):
        candidate = tests_dir / name
        if candidate.is_file():
            candidates.append(candidate)
    # Co-located test pattern: <stem>_test.py next to target.
    sibling = target.with_name(f"{stem}_test.py")
    if sibling.is_file():
        candidates.append(sibling)
    # Dedup, preserve order
    seen: dict[Path, None] = {}
    for path in candidates:
        seen.setdefault(path, None)
    return list(seen.keys())


def _candidate_similar_paths(workspace: Path, target: Path) -> list[Path]:
    """Return up to MAX_SIMILAR_FILES files that look similar to ``target``.

    Heuristic: same directory, same extension, different stem. Used only
    as a style reference for the model; never as ground truth.
    """
    if not target.parent.is_dir():
        return []
    siblings = [
        p
        for p in target.parent.iterdir()
        if p.is_file() and p.suffix == target.suffix and p != target
    ]
    siblings.sort(key=lambda p: p.name)
    return siblings[:MAX_SIMILAR_FILES]


def build_code_context(
    contract: CodeTaskContract,
    *,
    workspace_root: str | Path,
    error_excerpt: str = "",
) -> CodeContext:
    """Build the read-only context for a Code Forge task.

    The contract is preserved untouched; the builder never edits it.
    Missing files are surfaced as ``exists=False`` summaries so the
    model and the validation pipeline can react explicitly.
    """
    root = Path(workspace_root).resolve()
    target_summaries: list[CodeFileSummary] = []
    seen: dict[str, None] = {}
    for raw in contract.target_files:
        seen.setdefault(raw, None)
    for raw in seen:
        target = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw)
        try:
            in_workspace = target.is_relative_to(root) if target.exists() else True
        except ValueError:
            in_workspace = False
        if not in_workspace:
            target_summaries.append(
                CodeFileSummary(path=raw, language=contract.language, exists=False)
            )
            continue
        target_summaries.append(_summarise(target))

    related_tests: list[CodeFileSummary] = []
    tests_seen: dict[str, None] = {}
    for target_summary in target_summaries:
        target_path = (root / target_summary.path).resolve()
        for test_path in _candidate_test_paths(root, target_path):
            key = str(test_path)
            if key in tests_seen:
                continue
            tests_seen.setdefault(key, None)
            related_tests.append(_summarise(test_path))
    if not related_tests:
        # Fallback: at least scan tests/ for files mentioning the target
        # stem, so the model has a hint of how the project tests things.
        tests_dir = root / "tests"
        if tests_dir.is_dir():
            for candidate in sorted(tests_dir.glob("test_*.py"))[:3]:
                related_tests.append(_summarise(candidate))

    similar_files: list[CodeFileSummary] = []
    for target_summary in target_summaries:
        target_path = (root / target_summary.path).resolve()
        for sim in _candidate_similar_paths(root, target_path):
            similar_files.append(_summarise(sim))

    return CodeContext(
        contract=contract,
        target_summaries=tuple(target_summaries),
        related_tests=tuple(related_tests),
        similar_files=tuple(similar_files),
        error_excerpt=error_excerpt[:2048],
    )
