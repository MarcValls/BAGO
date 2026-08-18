#!/usr/bin/env python3
"""directory_context.py - deterministic directory context engine for BAGO.

This module provides the first operational slice of the Directory Context
Engine: scan, repository map, symbol index, dependency graph, hybrid retrieval,
working-set assembly, and incremental single-file refresh.
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".bago",
    ".gabo",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
}

TEXT_SUFFIXES = {
    ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini",
    ".css", ".html", ".csv",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, limit_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    read = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 128)
            if not chunk:
                break
            if limit_bytes is not None and read + len(chunk) > limit_bytes:
                chunk = chunk[: max(0, limit_bytes - read)]
            h.update(chunk)
            read += len(chunk)
            if limit_bytes is not None and read >= limit_bytes:
                break
    return h.hexdigest()


def read_text_limited(path: Path, max_bytes: int = 96_000) -> str:
    data = path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")


def line_slice(path: Path, start: int, end: int, max_chars: int = 12_000) -> str:
    lines = read_text_limited(path, max_bytes=max(max_chars * 2, 16_000)).splitlines()
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), max(start_idx, end))
    text = "\n".join(lines[start_idx:end_idx])
    return text[:max_chars]


def safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def is_binary_sample(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\x00" in sample


def _simple_gitignore_patterns(root: Path) -> list[str]:
    path = root / ".gitignore"
    if not path.exists():
        return []
    patterns: list[str] = []
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            patterns.append(line.rstrip("/"))
    except OSError:
        return []
    return patterns


def _ignored_by_patterns(rel: str, patterns: Iterable[str]) -> bool:
    rel_norm = rel.replace("\\", "/")
    for pattern in patterns:
        pat = pattern.replace("\\", "/").strip("/")
        if not pat:
            continue
        if fnmatch.fnmatch(rel_norm, pat) or fnmatch.fnmatch(Path(rel_norm).name, pat):
            return True
        if rel_norm.startswith(pat + "/"):
            return True
    return False


@dataclass(slots=True)
class FileRecord:
    path: str
    absolute_path: str
    kind: str
    suffix: str
    language: str
    size: int
    mtime: float
    sha256: str
    binary: bool
    generated: bool


@dataclass(slots=True)
class SymbolRecord:
    id: str
    path: str
    name: str
    qualified_name: str
    kind: str
    language: str
    start_line: int
    end_line: int
    sha256: str
    imports: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    related_symbols: list[str] = field(default_factory=list)
    summary: str = ""
    indexed_at: str = field(default_factory=utc_now)


class DirectoryScanner:
    """Scans workspace metadata without indiscriminately reading file bodies."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        exclude_dirs: Iterable[str] | None = None,
        max_file_bytes: int = 2_000_000,
    ) -> None:
        self.root = Path(workspace_root).resolve()
        self.exclude_dirs = set(exclude_dirs or DEFAULT_EXCLUDED_DIRS)
        if (self.root / ".bago" / "core").exists():
            self.exclude_dirs.discard(".bago")
        self.max_file_bytes = max_file_bytes
        self.gitignore_patterns = _simple_gitignore_patterns(self.root)

    def scan(self) -> list[FileRecord]:
        records: list[FileRecord] = []
        if not self.root.exists():
            return records
        # FIX v0.3: usar os.walk en lugar de Path.rglob para excluir
        # directorios (node_modules, .git, etc.) DURANTE el recorrido.
        # rglob enumera TODOS los paths antes de filtrar, lo que con
        # node_modules de cientos de MB tarda minutos. os.walk permite
        # filtrar dirs[:] antes de descender.
        import os
        all_paths: list[Path] = []
        for current_root, dirs, files in os.walk(self.root):
            # Filtrar subdirs excluidos in-place (afecta la recursión).
            dirs[:] = [
                d for d in sorted(dirs)
                if d not in self.exclude_dirs
                and not _ignored_by_patterns(
                    str(Path(current_root, d).relative_to(self.root)).replace("\\", "/"),
                    self.gitignore_patterns,
                )
            ]
            for name in dirs:
                all_paths.append(Path(current_root) / name)
            for name in files:
                all_paths.append(Path(current_root) / name)
        for path in sorted(all_paths, key=lambda p: safe_relative(p, self.root).lower()):
            rel = safe_relative(path, self.root)
            if self._is_excluded(path, rel):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if path.is_dir():
                records.append(FileRecord(
                    path=rel,
                    absolute_path=str(path),
                    kind="directory",
                    suffix="",
                    language="",
                    size=0,
                    mtime=stat.st_mtime,
                    sha256="",
                    binary=False,
                    generated=self._is_generated(path, rel),
                ))
                continue
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            binary = suffix not in TEXT_SUFFIXES or is_binary_sample(path)
            generated = self._is_generated(path, rel)
            digest = sha256_file(path)
            records.append(FileRecord(
                path=rel,
                absolute_path=str(path),
                kind="file",
                suffix=suffix,
                language=LANGUAGE_BY_SUFFIX.get(suffix, ""),
                size=stat.st_size,
                mtime=stat.st_mtime,
                sha256=digest,
                binary=binary,
                generated=generated,
            ))
        return records

    def _is_excluded(self, path: Path, rel: str) -> bool:
        parts = set(Path(rel).parts)
        if any(part in self.exclude_dirs for part in parts):
            return True
        if any(rel == item or rel.startswith(item + "/") for item in self.exclude_dirs):
            return True
        if _ignored_by_patterns(rel, self.gitignore_patterns):
            return True
        return False

    def _is_generated(self, path: Path, rel: str) -> bool:
        low = rel.lower().replace("\\", "/")
        return any(part in low.split("/") for part in ("dist", "build", "coverage")) or low.endswith(".min.js")


class RepositoryMapBuilder:
    """Builds compact repository maps from scan metadata."""

    def __init__(self, workspace_root: str | Path, context_root: str | Path) -> None:
        self.root = Path(workspace_root).resolve()
        self.context_root = Path(context_root).resolve()

    def build(self, files: list[FileRecord], symbols: list[SymbolRecord] | None = None) -> dict[str, Any]:
        file_paths = [f.path for f in files if f.kind == "file"]
        dirs = sorted({p.split("/")[0] for p in file_paths if "/" in p})
        suffix_counts: dict[str, int] = {}
        for record in files:
            if record.kind == "file":
                suffix_counts[record.suffix or "<none>"] = suffix_counts.get(record.suffix or "<none>", 0) + 1
        map_data = {
            "schema": "bago.repository_map.v1",
            "project_root": str(self.root),
            "captured_at": utc_now(),
            "purpose": self._purpose(),
            "directories": dirs[:80],
            "entry_points": self._entry_points(file_paths),
            "modules": self._modules(file_paths, symbols or []),
            "configuration_files": [p for p in file_paths if Path(p).name in {"package.json", "pyproject.toml", "vite.config.js", "vite.config.ts", "tsconfig.json", "pytest.ini"}],
            "tests": [p for p in file_paths if "/test" in p.lower() or Path(p).name.startswith("test_") or Path(p).name.endswith((".test.js", ".test.jsx", ".test.ts", ".test.tsx"))],
            "scripts": [p for p in file_paths if p.startswith("scripts/") or p.endswith((".ps1", ".cmd", ".bat", ".sh"))],
            "generated": [f.path for f in files if f.generated][:120],
            "protected_zones": [".git", ".gabo", ".bago", "node_modules", ".venv"],
            "backend_shared": [p for p in file_paths if p.startswith(".bago/core/") or p.startswith("bago_core/")],
            "consumer_surfaces": [p for p in file_paths if p.startswith(".bago/chat/") or p.startswith("ui-react/") or p.startswith("electron/") or p.startswith("manager/")],
            "suffix_counts": suffix_counts,
            "file_count": len(file_paths),
            "symbol_count": len(symbols or []),
        }
        return map_data

    def save(self, map_data: dict[str, Any]) -> None:
        self.context_root.mkdir(parents=True, exist_ok=True)
        (self.context_root / "repository_map.json").write_text(
            json.dumps(map_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        lines = [
            f"# Repository Map",
            "",
            f"- project_root: `{map_data.get('project_root', '')}`",
            f"- purpose: {map_data.get('purpose', '')}",
            f"- files: {map_data.get('file_count', 0)}",
            f"- symbols: {map_data.get('symbol_count', 0)}",
            "",
            "## Entry Points",
        ]
        for item in map_data.get("entry_points", []):
            lines.append(f"- `{item}`")
        lines.extend(["", "## Main Directories"])
        for item in map_data.get("directories", [])[:40]:
            lines.append(f"- `{item}`")
        (self.context_root / "repository_map.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _purpose(self) -> str:
        readme = self.root / "README.md"
        if readme.exists():
            try:
                for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
                    clean = line.strip(" #\t")
                    if clean:
                        return clean[:180]
            except OSError:
                pass
        return self.root.name

    def _entry_points(self, file_paths: list[str]) -> list[str]:
        candidates = {
            "package.json", "pyproject.toml", "bago.cmd", "bago.ps1",
            "src/main.jsx", "src/main.tsx", "src/index.jsx", "src/index.tsx",
            "index.html", ".bago/chat/repl.py", "bago_core/launcher.py",
        }
        return [p for p in file_paths if p in candidates or Path(p).name in {"main.py", "app.py", "cli.py"}][:60]

    def _modules(self, file_paths: list[str], symbols: list[SymbolRecord]) -> list[dict[str, Any]]:
        by_dir: dict[str, int] = {}
        for path in file_paths:
            top = path.split("/")[0] if "/" in path else "."
            by_dir[top] = by_dir.get(top, 0) + 1
        symbol_by_dir: dict[str, int] = {}
        for symbol in symbols:
            top = symbol.path.split("/")[0] if "/" in symbol.path else "."
            symbol_by_dir[top] = symbol_by_dir.get(top, 0) + 1
        return [
            {"path": name, "files": count, "symbols": symbol_by_dir.get(name, 0), "responsibility": self._responsibility(name)}
            for name, count in sorted(by_dir.items(), key=lambda item: (-item[1], item[0]))[:80]
        ]

    def _responsibility(self, dirname: str) -> str:
        mapping = {
            ".bago": "BAGO runtime framework",
            "bago_core": "BAGO framework services and CLI",
            "tests": "automated tests",
            "ui-react": "React manager surface",
            "electron": "Electron backend surface",
            "docs": "documentation and contracts",
            "scripts": "maintenance and release scripts",
        }
        return mapping.get(dirname, "project module")


class SymbolIndexer:
    """Indexes semantic units for Python and JS/TS-like files."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.root = Path(workspace_root).resolve()

    def index(self, files: list[FileRecord]) -> list[SymbolRecord]:
        symbols: list[SymbolRecord] = []
        for record in files:
            if record.kind != "file" or record.binary or record.generated:
                continue
            path = self.root / record.path
            try:
                if record.language == "python":
                    symbols.extend(self._python_symbols(path, record))
                elif record.language in {"javascript", "javascriptreact", "typescript", "typescriptreact"}:
                    symbols.extend(self._js_symbols(path, record))
            except Exception:
                continue
        return symbols

    def index_file(self, file_record: FileRecord) -> list[SymbolRecord]:
        return self.index([file_record])

    def _python_symbols(self, path: Path, record: FileRecord) -> list[SymbolRecord]:
        text = read_text_limited(path, max_bytes=400_000)
        tree = ast.parse(text)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = "." * int(node.level or 0) + (node.module or "")
                imports.append(module)
        symbols: list[SymbolRecord] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                parent = self._python_parent_name(tree, node)
                qualified = f"{parent}.{node.name}" if parent else node.name
                end_line = int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))
                summary = ast.get_docstring(node) or ""
                symbols.append(SymbolRecord(
                    id=f"python:{record.path}:{qualified}:{node.lineno}",
                    path=record.path,
                    name=node.name,
                    qualified_name=qualified,
                    kind=kind if not parent or kind == "class" else "method",
                    language="python",
                    start_line=int(node.lineno),
                    end_line=end_line,
                    sha256=hashlib.sha256(line_slice(path, int(node.lineno), end_line).encode("utf-8", errors="replace")).hexdigest(),
                    imports=imports,
                    references=self._python_references(node),
                    summary=summary.splitlines()[0][:220] if summary else "",
                ))
        return symbols

    def _python_parent_name(self, tree: ast.AST, target: ast.AST) -> str:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in ast.walk(node):
                    if child is target and child is not node:
                        return node.name
        return ""

    def _python_references(self, node: ast.AST) -> list[str]:
        refs: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                refs.add(child.id)
            elif isinstance(child, ast.Attribute):
                refs.add(child.attr)
        return sorted(refs)[:120]

    def _js_symbols(self, path: Path, record: FileRecord) -> list[SymbolRecord]:
        text = read_text_limited(path, max_bytes=400_000)
        imports = self._js_imports(text)
        lines = text.splitlines()
        symbols: list[SymbolRecord] = []
        for idx, line in enumerate(lines, start=1):
            decl = self._js_declaration(line)
            if decl is None:
                continue
            name, kind = decl
            end_line = self._find_js_block_end(lines, idx)
            if kind == "function" and name[:1].isupper() and record.language.endswith("react"):
                kind = "react_component"
            elif kind == "function" and name.startswith("use"):
                kind = "hook"
            summary = line.strip()[:220]
            symbols.append(SymbolRecord(
                id=f"{record.language}:{record.path}:{name}:{idx}",
                path=record.path,
                name=name,
                qualified_name=name,
                kind=kind,
                language=record.language,
                start_line=idx,
                end_line=end_line,
                sha256=hashlib.sha256(line_slice(path, idx, end_line).encode("utf-8", errors="replace")).hexdigest(),
                imports=imports,
                references=self._js_references("\n".join(lines[idx - 1:end_line])),
                summary=summary,
            ))
        return symbols

    def _js_imports(self, text: str) -> list[str]:
        imports: list[str] = []
        for match in re.finditer(r"\bimport\s+(?:[^'\"]+\s+from\s+)?['\"]([^'\"]+)['\"]", text):
            imports.append(match.group(1))
        for match in re.finditer(r"\brequire\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
            imports.append(match.group(1))
        return sorted(dict.fromkeys(imports))

    def _js_declaration(self, line: str) -> tuple[str, str] | None:
        stripped = line.strip()
        patterns = [
            (r"^(?:export\s+default\s+)?(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", "class"),
            (r"^(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", "function"),
            (r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", "function"),
            (r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\b", "function"),
            (r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", "variable"),
            (r"^(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)\b", "interface"),
            (r"^(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\b", "type"),
        ]
        for pattern, kind in patterns:
            match = re.match(pattern, stripped)
            if match:
                return match.group(1), kind
        return None

    def _find_js_block_end(self, lines: list[str], start_line: int) -> int:
        depth = 0
        seen_open = False
        for idx in range(start_line, len(lines) + 1):
            line = lines[idx - 1]
            for char in line:
                if char == "{":
                    depth += 1
                    seen_open = True
                elif char == "}":
                    depth -= 1
                    if seen_open and depth <= 0:
                        return idx
            if not seen_open and line.rstrip().endswith(";"):
                return idx
        return start_line

    def _js_references(self, text: str) -> list[str]:
        refs = {
            item
            for item in re.findall(r"\b[A-Za-z_$][\w$]*\b", text)
            if item not in {"const", "let", "var", "function", "return", "import", "from", "export", "class", "if", "else"}
        }
        return sorted(refs)[:120]


class DependencyGraph:
    """Builds import and symbol relationship indexes."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.root = Path(workspace_root).resolve()

    def build(self, files: list[FileRecord], symbols: list[SymbolRecord]) -> dict[str, Any]:
        file_paths = {f.path for f in files if f.kind == "file"}
        imports: dict[str, list[str]] = {}
        dependents: dict[str, list[str]] = {}
        for symbol in symbols:
            imports.setdefault(symbol.path, [])
            for item in symbol.imports:
                target = self._resolve_import(symbol.path, item, file_paths)
                if target:
                    imports[symbol.path].append(target)
                    dependents.setdefault(target, []).append(symbol.path)
        tests_by_file = self._tests_by_file(file_paths)
        return {
            "schema": "bago.dependency_graph.v1",
            "built_at": utc_now(),
            "imports": {k: sorted(dict.fromkeys(v)) for k, v in imports.items()},
            "dependents": {k: sorted(dict.fromkeys(v)) for k, v in dependents.items()},
            "tests_by_file": tests_by_file,
        }

    def _resolve_import(self, source_path: str, imported: str, file_paths: set[str]) -> str:
        if imported.startswith("."):
            base = Path(source_path).parent
            cleaned = imported.lstrip("./")
            candidates = [base / cleaned]
        else:
            candidates = [Path(imported.replace(".", "/"))]
        suffixes = ["", ".py", ".js", ".jsx", ".ts", ".tsx", "/__init__.py", "/index.js", "/index.jsx", "/index.ts", "/index.tsx"]
        for base in candidates:
            for suffix in suffixes:
                candidate = (base.as_posix() + suffix).strip("/")
                if candidate in file_paths:
                    return candidate
        return ""

    def _tests_by_file(self, file_paths: set[str]) -> dict[str, list[str]]:
        tests = [p for p in file_paths if "/test" in p.lower() or Path(p).name.startswith("test_") or ".test." in Path(p).name]
        mapping: dict[str, list[str]] = {}
        for path in file_paths:
            stem = Path(path).stem.replace("test_", "")
            related = [t for t in tests if stem and stem in Path(t).stem]
            if related:
                mapping[path] = sorted(related)
        return mapping


class HybridRetriever:
    """Retrieves candidate files first, then concrete symbols and definitions."""

    def __init__(self, workspace_root: str | Path, context_root: str | Path) -> None:
        self.root = Path(workspace_root).resolve()
        self.context_root = Path(context_root).resolve()

    def retrieve(
        self,
        query: str,
        files: list[FileRecord],
        symbols: list[SymbolRecord],
        graph: dict[str, Any],
        *,
        limit_files: int = 6,
        limit_symbols: int = 8,
    ) -> list[dict[str, Any]]:
        query_tokens = self._tokens(query)
        exact_terms = {token.lower() for token in query_tokens if len(token) >= 3}
        file_scores: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}
        file_by_path = {f.path: f for f in files if f.kind == "file"}

        def add(path: str, score: float, reason: str) -> None:
            if path not in file_by_path:
                return
            file_scores[path] = file_scores.get(path, 0.0) + score
            reasons.setdefault(path, []).append(reason)

        for record in file_by_path.values():
            low_path = record.path.lower()
            for term in exact_terms:
                if term in low_path:
                    add(record.path, 8.0, f"path_match:{term}")

        for symbol in symbols:
            low_name = symbol.name.lower()
            low_qualified = symbol.qualified_name.lower()
            for term in exact_terms:
                if term == low_name or term == low_qualified:
                    add(symbol.path, 12.0, f"exact_symbol:{symbol.qualified_name}")
                elif term in low_name or term in low_qualified:
                    add(symbol.path, 5.0, f"symbol_match:{symbol.qualified_name}")

        for path, score, reason in self._text_matches(file_by_path.values(), exact_terms):
            add(path, score, reason)

        for path in self._git_diff_paths():
            add(path, 3.0, "git_diff")

        for path in list(file_scores):
            record = file_by_path.get(path)
            if record and time.time() - record.mtime < 86400 * 7:
                add(path, 0.3, "recent_file")

        ranked_files = [
            path for path, _ in sorted(file_scores.items(), key=lambda item: (-item[1], item[0]))[:limit_files]
        ]
        if not ranked_files:
            return []

        selected_symbols = [
            symbol for symbol in symbols if symbol.path in ranked_files
        ]
        selected_symbols.sort(key=lambda s: self._symbol_score(s, exact_terms), reverse=True)
        selected_symbols = selected_symbols[:limit_symbols]

        fragments: list[dict[str, Any]] = []
        for symbol in selected_symbols:
            path = self.root / symbol.path
            if not path.exists():
                continue
            content = line_slice(path, symbol.start_line, symbol.end_line)
            fragments.append({
                "source": "directory_context",
                "source_type": "source file",
                "source_uri": symbol.path,
                "path": symbol.path,
                "symbol": symbol.qualified_name,
                "symbol_kind": symbol.kind,
                "language": symbol.language,
                "start_line": symbol.start_line,
                "end_line": symbol.end_line,
                "score": round(file_scores.get(symbol.path, 0.0) + self._symbol_score(symbol, exact_terms), 3),
                "reason": list(dict.fromkeys(reasons.get(symbol.path, []) + [f"selected_symbol:{symbol.qualified_name}"])),
                "content": content,
                "summary": content[:240],
                "imports": symbol.imports,
                "dependents": graph.get("dependents", {}).get(symbol.path, []),
                "tests": graph.get("tests_by_file", {}).get(symbol.path, []),
                "scope": "Project",
                "authority_level": "project",
                "created_at": "",
                "retrieved_at": utc_now(),
                "expires_at": "",
                "content_hash": hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest(),
                "revision": symbol.sha256,
                "token_count": max(len(content) // 4, 1),
                "sensitivity_level": "low",
                "cache_policy": "hash+mtime",
                "invalidation_causes": ["content_hash", "mtime", "git_diff"],
                "relevance_score": round(file_scores.get(symbol.path, 0.0) + self._symbol_score(symbol, exact_terms), 3),
                "authority_score": 0.9,
                "freshness_score": 0.8,
                "estimated_cost": round(max(len(content) // 4, 1) * 0.00001, 6),
                "evidence_refs": [{"type": "symbol", "qualified_name": symbol.qualified_name, "path": symbol.path}],
                "reason_for_inclusion": "selected symbol from directory context",
                "status": "selected",
                "metadata": {"imports": symbol.imports, "references": symbol.references},
            })

        represented = {frag["path"] for frag in fragments}
        for path in ranked_files:
            if path in represented:
                continue
            target = self.root / path
            if target.exists() and not file_by_path[path].binary:
                content = read_text_limited(target, max_bytes=4000)
                fragments.append({
                    "source": "workspace_file",
                    "source_type": "source file",
                    "source_uri": path,
                    "path": path,
                    "score": round(file_scores.get(path, 0.0), 3),
                    "reason": list(dict.fromkeys(reasons.get(path, []))),
                    "content": content,
                    "summary": content[:240],
                    "dependents": graph.get("dependents", {}).get(path, []),
                    "tests": graph.get("tests_by_file", {}).get(path, []),
                    "scope": "Project",
                    "authority_level": "project",
                    "created_at": "",
                    "retrieved_at": utc_now(),
                    "expires_at": "",
                    "content_hash": hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest(),
                    "revision": file_by_path[path].sha256,
                    "token_count": max(len(content) // 4, 1),
                    "sensitivity_level": "low",
                    "cache_policy": "hash+mtime",
                    "invalidation_causes": ["content_hash", "mtime", "git_diff"],
                    "relevance_score": round(file_scores.get(path, 0.0), 3),
                    "authority_score": 0.75,
                    "freshness_score": 0.75,
                    "estimated_cost": round(max(len(content) // 4, 1) * 0.00001, 6),
                    "evidence_refs": [{"type": "file", "path": path}],
                    "reason_for_inclusion": "workspace file selected by hybrid retriever",
                    "status": "selected",
                    "metadata": {"kind": file_by_path[path].kind, "language": file_by_path[path].language},
                })
        return fragments[: max(limit_symbols, limit_files)]

    def _tokens(self, query: str) -> list[str]:
        return re.findall(r"[A-Za-z_][\w.$/-]*", query or "")

    def _symbol_score(self, symbol: SymbolRecord, terms: set[str]) -> float:
        score = 0.0
        low = symbol.name.lower()
        qualified = symbol.qualified_name.lower()
        for term in terms:
            if term == low or term == qualified:
                score += 10.0
            elif term in low or term in qualified:
                score += 4.0
        return score

    def _text_matches(self, records: Iterable[FileRecord], terms: set[str]) -> list[tuple[str, float, str]]:
        if not terms:
            return []
        matches: list[tuple[str, float, str]] = []
        for record in records:
            if record.binary or record.size > 500_000:
                continue
            path = self.root / record.path
            try:
                text = read_text_limited(path, max_bytes=80_000).lower()
            except OSError:
                continue
            hits = [term for term in terms if term in text]
            if hits:
                matches.append((record.path, min(4.0, len(hits) * 1.2), "text_match:" + ",".join(hits[:5])))
        return matches

    def _git_diff_paths(self) -> list[str]:
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            return []
        if proc.returncode != 0:
            return []
        return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


class ContextAssembler:
    """Builds working-set metadata from retrieved fragments."""

    def assemble(self, objective: str, fragments: list[dict[str, Any]], map_data: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
        files = list(dict.fromkeys(str(f.get("path", "")) for f in fragments if f.get("path")))
        symbols = [
            {"path": f.get("path"), "symbol": f.get("symbol"), "kind": f.get("symbol_kind")}
            for f in fragments
            if f.get("symbol")
        ]
        dependencies = {
            path: {
                "imports": graph.get("imports", {}).get(path, []),
                "dependents": graph.get("dependents", {}).get(path, []),
                "tests": graph.get("tests_by_file", {}).get(path, []),
            }
            for path in files
        }
        return {
            "schema": "bago.working_set.v1",
            "objective": objective,
            "created_at": utc_now(),
            "project_root": map_data.get("project_root", ""),
            "files": files,
            "symbols": symbols,
            "dependencies": dependencies,
            "evidence": [
                {
                    "path": f.get("path"),
                    "symbol": f.get("symbol", ""),
                    "reason": f.get("reason", []),
                    "score": f.get("score", 0.0),
                    "lines": [f.get("start_line"), f.get("end_line")] if f.get("start_line") else [],
                }
                for f in fragments
            ],
            "repository_map_digest": hashlib.sha256(json.dumps(map_data, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
        }


class DirectoryWatcher:
    """Incremental one-file refresh helper. This is not a background daemon."""

    def __init__(self, engine: "DirectoryContextEngine") -> None:
        self.engine = engine

    def refresh_changed_file(self, path: str | Path) -> dict[str, Any]:
        target = Path(path)
        if not target.is_absolute():
            target = self.engine.root / target
        target = target.resolve()
        try:
            rel = target.relative_to(self.engine.root).as_posix()
        except ValueError:
            return {"ok": False, "error": "path_outside_workspace", "path": str(target)}
        previous = self.engine.load_snapshot()
        previous_files = {item["path"]: item for item in previous.get("files", [])}
        previous_hash = previous_files.get(rel, {}).get("sha256", "")
        self.engine.refresh_file(rel)
        current = self.engine.load_snapshot()
        current_files = {item["path"]: item for item in current.get("files", [])}
        current_hash = current_files.get(rel, {}).get("sha256", "")
        event = {
            "ok": True,
            "path": rel,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "changed": previous_hash != current_hash,
            "refreshed_at": utc_now(),
        }
        self.engine.append_event(event)
        return event


class DirectoryContextEngine:
    """Facade used by SessionManager and future UI adapters."""

    def __init__(self, workspace_root: str | Path, context_root: str | Path | None = None) -> None:
        self.root = Path(workspace_root).resolve()
        self.context_root = Path(context_root).resolve() if context_root else self.root / ".gabo" / "context"
        self.scanner = DirectoryScanner(self.root)
        self.indexer = SymbolIndexer(self.root)
        self.graph_builder = DependencyGraph(self.root)
        self.map_builder = RepositoryMapBuilder(self.root, self.context_root)
        self.retriever = HybridRetriever(self.root, self.context_root)
        self.assembler = ContextAssembler()
        self.watcher = DirectoryWatcher(self)
        self._snapshot_cache: dict[str, Any] | None = None
        self._snapshot_checked_at: float = 0.0
        self._snapshot_ttl_s: float = 10.0

    def build(self) -> dict[str, Any]:
        files = self.scanner.scan()
        symbols = self.indexer.index(files)
        graph = self.graph_builder.build(files, symbols)
        map_data = self.map_builder.build(files, symbols)
        self.context_root.mkdir(parents=True, exist_ok=True)
        self.map_builder.save(map_data)
        snapshot = {
            "schema": "bago.directory_context.v1",
            "built_at": utc_now(),
            "workspace_root": str(self.root),
            "context_root": str(self.context_root),
            "files": [asdict(item) for item in files],
            "symbols": [asdict(item) for item in symbols],
            "graph": graph,
            "repository_map": map_data,
        }
        self._write_json("index.json", snapshot)
        self._write_json("symbols.json", snapshot["symbols"])
        self._write_json("dependency_graph.json", graph)
        return snapshot

    def ensure_snapshot(self) -> dict[str, Any]:
        if self._snapshot_cache and (time.time() - self._snapshot_checked_at) < self._snapshot_ttl_s:
            return self._snapshot_cache
        snapshot = self.load_snapshot()
        if snapshot:
            snapshot = self._refresh_stale_snapshot(snapshot)
        else:
            snapshot = self.build()
        self._snapshot_cache = snapshot
        self._snapshot_checked_at = time.time()
        return snapshot

    def load_snapshot(self) -> dict[str, Any]:
        path = self.context_root / "index.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def retrieve(self, query: str, *, limit_files: int = 6, limit_symbols: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        snapshot = self.ensure_snapshot()
        files = [FileRecord(**item) for item in snapshot.get("files", [])]
        symbols = [SymbolRecord(**item) for item in snapshot.get("symbols", [])]
        graph = snapshot.get("graph", {})
        fragments = self.retriever.retrieve(query, files, symbols, graph, limit_files=limit_files, limit_symbols=limit_symbols)
        working_set = self.assembler.assemble(query, fragments, snapshot.get("repository_map", {}), graph)
        self._write_json("working_set.json", working_set)
        return fragments, working_set

    def refresh_file(self, rel_path: str) -> dict[str, Any]:
        snapshot = self.ensure_snapshot()
        records = [FileRecord(**item) for item in snapshot.get("files", [])]
        records = [item for item in records if item.path != rel_path]
        target = self.root / rel_path
        if target.exists():
            scanner = DirectoryScanner(self.root)
            scanned = [item for item in scanner.scan() if item.path == rel_path]
            records.extend(scanned)
        symbols = [SymbolRecord(**item) for item in snapshot.get("symbols", []) if item.get("path") != rel_path]
        for record in records:
            if record.path == rel_path:
                symbols.extend(self.indexer.index_file(record))
        graph = self.graph_builder.build(records, symbols)
        map_data = self.map_builder.build(records, symbols)
        self.map_builder.save(map_data)
        refreshed = {
            "schema": "bago.directory_context.v1",
            "built_at": utc_now(),
            "workspace_root": str(self.root),
            "context_root": str(self.context_root),
            "files": [asdict(item) for item in sorted(records, key=lambda item: item.path)],
            "symbols": [asdict(item) for item in sorted(symbols, key=lambda item: item.id)],
            "graph": graph,
            "repository_map": map_data,
        }
        self._write_json("index.json", refreshed)
        self._write_json("symbols.json", refreshed["symbols"])
        self._write_json("dependency_graph.json", graph)
        return refreshed

    def _refresh_stale_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        old_files = {
            item.get("path"): item
            for item in snapshot.get("files", [])
            if isinstance(item, dict) and item.get("kind") == "file"
        }
        current_records = self.scanner.scan()
        current_files = {item.path: item for item in current_records if item.kind == "file"}
        changed = [
            path for path, record in current_files.items()
            if old_files.get(path, {}).get("sha256") != record.sha256
        ]
        deleted = [path for path in old_files if path not in current_files]
        if not changed and not deleted:
            return snapshot
        records = current_records
        old_symbols = [
            SymbolRecord(**item)
            for item in snapshot.get("symbols", [])
            if isinstance(item, dict) and item.get("path") not in set(changed + deleted)
        ]
        symbols = list(old_symbols)
        for record in records:
            if record.path in changed:
                symbols.extend(self.indexer.index_file(record))
        graph = self.graph_builder.build(records, symbols)
        map_data = self.map_builder.build(records, symbols)
        self.map_builder.save(map_data)
        refreshed = {
            "schema": "bago.directory_context.v1",
            "built_at": utc_now(),
            "workspace_root": str(self.root),
            "context_root": str(self.context_root),
            "files": [asdict(item) for item in records],
            "symbols": [asdict(item) for item in sorted(symbols, key=lambda item: item.id)],
            "graph": graph,
            "repository_map": map_data,
        }
        self._write_json("index.json", refreshed)
        self._write_json("symbols.json", refreshed["symbols"])
        self._write_json("dependency_graph.json", graph)
        self.append_event({
            "ok": True,
            "event": "snapshot_incremental_refresh",
            "changed": changed,
            "deleted": deleted,
            "refreshed_at": utc_now(),
        })
        return refreshed

    def append_event(self, event: dict[str, Any]) -> None:
        self.context_root.mkdir(parents=True, exist_ok=True)
        with (self.context_root / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def _write_json(self, name: str, payload: Any) -> None:
        self.context_root.mkdir(parents=True, exist_ok=True)
        target = self.context_root / name
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(target)
