from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from _healer_memory import BAGO_ROOT, REPO_ROOT, TOOLS_DIR, Memory


_PATH_VAR_DEF = re.compile(
    r"^([A-Z_][A-Z0-9_]*)\s*=\s*"
    r"(Path\s*\([^)]+\)|os\.path\.[^\n]+)"
    r"(?:[^\n]*)",
    re.MULTILINE,
)

_FILE_EXPR_PARTS = re.compile(
    r"Path\s*\(\s*__file__\s*\)"
    r"((?:\s*\.\s*(?:resolve|parent|stem|name)\s*\(\s*\)|\s*\.\s*parent)*)"
)

_WRAPPERS = [
    (
        r'str\s*\(\s*{var}\s*/\s*["\']({stem_pat})\.py["\'](?:\s*/\s*["\'][^"\']*["\'])*\s*\)',
        "str_div",
    ),
    (
        r'({var}\s*/\s*["\']({stem_pat})\.py["\'](?:\s*/\s*["\'][^"\']*["\'])*)',
        "div",
    ),
    (r'Path\s*\(\s*["\']([^"\']*[/\\\\]({stem_pat})\.py)["\'])', "abs_path"),
    (
        r'spec_from_file_location\s*\([^,]+,\s*str\s*\(\s*{var}\s*/\s*["\']({stem_pat})\.py["\']',
        "spec",
    ),
]


@dataclass
class PathRef:
    file: Path
    line_no: int
    col: int
    fragment: str
    stem: str
    var_name: str
    var_dir: Optional[Path]
    kind: str
    broken: bool = False
    found_at: Optional[Path] = None
    fixed: bool = False


@dataclass
class ScanReport:
    files_scanned: int = 0
    refs_found: int = 0
    broken: int = 0
    fixed: int = 0
    missing: int = 0
    refs: list[PathRef] = field(default_factory=list)


def _resolve_path_expr(expr_rhs: str, file_path: Path) -> Optional[Path]:
    match = _FILE_EXPR_PARTS.search(expr_rhs)
    if not match:
        return None

    modifiers = match.group(1)
    parent_count = modifiers.count(".parent")
    has_resolve = ".resolve()" in modifiers

    result = file_path.resolve() if has_resolve else file_path
    for _ in range(parent_count):
        result = result.parent

    return result if result.exists() else None


def discover_path_vars(source: str, file_path: Path) -> dict[str, Path]:
    path_vars: dict[str, Path] = {}
    for match in _PATH_VAR_DEF.finditer(source):
        var_name = match.group(1)
        resolved = _resolve_path_expr(match.group(0), file_path)
        if resolved is not None:
            path_vars[var_name] = resolved
    return path_vars


def build_patterns_for_file(path_vars: dict[str, Path]) -> list[tuple[re.Pattern, str, str]]:
    patterns: list[tuple[re.Pattern, str, str]] = []
    stem_pat = r"[a-zA-Z0-9_\-]+"

    for var_name in path_vars:
        esc_var = re.escape(var_name)
        for wrapper_tmpl, kind in _WRAPPERS:
            if "{var}" not in wrapper_tmpl:
                continue
            try:
                patterns.append((re.compile(wrapper_tmpl.format(var=esc_var, stem_pat=stem_pat)), kind, var_name))
            except re.error:
                continue

    try:
        patterns.append((re.compile(_WRAPPERS[2][0].format(var="", stem_pat=stem_pat)), "abs_path", ""))
    except re.error:
        pass

    return patterns


def build_stem_index(mem: Memory) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for root in [BAGO_ROOT]:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if py_file.name.startswith(".") or ".healer.bak" in py_file.name:
                continue
            stem = py_file.stem
            if stem not in index:
                index[stem] = py_file
            elif py_file.parent == TOOLS_DIR and index[stem].parent != TOOLS_DIR:
                index[stem] = py_file

    for stem, path in index.items():
        mem.update_stem(stem, path)
    return index


def scan_file(py_file: Path, stem_index: dict[str, Path], mem: Memory) -> list[PathRef]:
    try:
        source = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    path_vars = discover_path_vars(source, py_file)
    patterns = build_patterns_for_file(path_vars)
    if not patterns:
        return []

    refs: list[PathRef] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        for compiled_pat, kind, var_name in patterns:
            for match in compiled_pat.finditer(line):
                suffix = line[match.end(): match.end() + 32]
                if re.match(r"\s*\)*\s*\.\s*(exists|is_file|is_dir)\s*\(", suffix):
                    continue

                groups = [group for group in match.groups() if group and re.match(r"^[a-zA-Z0-9_\-]+$", group)]
                if not groups:
                    continue
                stem = groups[-1]

                var_dir = path_vars.get(var_name)
                if var_dir and kind in {"str_div", "div", "spec"}:
                    resolved_now = var_dir / f"{stem}.py"
                    is_broken = not resolved_now.exists()
                elif kind == "abs_path":
                    literal = match.group(1) if match.lastindex and match.lastindex >= 1 else ""
                    resolved_now = Path(literal)
                    is_broken = not resolved_now.exists()
                else:
                    continue

                if not is_broken:
                    continue

                found = mem.resolve_stem(stem) or stem_index.get(stem)
                if any(ref.line_no == line_no and ref.stem == stem for ref in refs):
                    continue

                refs.append(
                    PathRef(
                        file=py_file,
                        line_no=line_no,
                        col=match.start(),
                        fragment=match.group(0),
                        stem=stem,
                        var_name=var_name,
                        var_dir=var_dir,
                        kind=kind,
                        broken=True,
                        found_at=found,
                    )
                )
    return refs


def scan_all(mem: Memory, extra_roots: Optional[list[Path]] = None) -> ScanReport:
    stem_index = build_stem_index(mem)
    search_roots: list[Path] = [BAGO_ROOT]
    if extra_roots:
        search_roots.extend(extra_roots)

    visited: set[Path] = set()
    all_refs: list[PathRef] = []
    for root in search_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if py_file in visited or ".healer.bak" in py_file.name or py_file.name.startswith("."):
                continue
            visited.add(py_file)
            all_refs.extend(scan_file(py_file, stem_index, mem))

    broken = [ref for ref in all_refs if ref.broken]
    missing = [ref for ref in broken if ref.found_at is None]
    return ScanReport(
        files_scanned=len(visited),
        refs_found=len(all_refs),
        broken=len(broken),
        missing=len(missing),
        refs=all_refs,
    )


def build_replacement(ref: PathRef) -> str:
    assert ref.found_at is not None
    found = ref.found_at.resolve()

    if ref.kind == "abs_path":
        if ref.var_name and ref.var_dir:
            try:
                rel_parts = found.relative_to(ref.var_dir).parts
            except ValueError:
                return f'Path(r"{found}")'
            chain = " / ".join(f'"{part}"' for part in rel_parts)
            return f'Path(str({ref.var_name} / {chain}))'
        return f'Path(r"{found}")'

    if not ref.var_name or ref.var_dir is None:
        return ref.fragment

    try:
        rel_parts = found.relative_to(ref.var_dir).parts
    except ValueError:
        return f'Path(r"{found}")'

    chain = " / ".join(f'"{part}"' for part in rel_parts)
    path_expr = f"{ref.var_name} / {chain}"
    if ref.kind == "str_div":
        return f"str({path_expr})"
    if ref.kind == "spec":
        name_match = re.search(r'spec_from_file_location\s*\(([^,]+),', ref.fragment)
        name_part = name_match.group(1).strip() if name_match else '"_module"'
        return f"spec_from_file_location({name_part}, str({path_expr}))"
    return path_expr
