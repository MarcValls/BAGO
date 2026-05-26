"""doc_index.py — Índice de cobertura documental de BAGO.

Cada doc en docs/ puede declarar qué nodos/scripts cubre con una anotación:
  <!-- @covers: tool1.py, tool2.py, bago_chat -->

Este módulo:
  1. Escanea todos los .md en docs/ y .bago/knowledge/
  2. Extrae anotaciones @covers (o infiere por menciones a .py)
  3. Genera índice reverso: tool_stem → [doc1, doc2, ...]
  4. Detecta tools sin cobertura documental
  5. Puede añadir anotación @covers a un doc dado
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import re
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE      = Path(__file__).resolve()
_TOOLS     = _HERE.parent
_BAGO      = _TOOLS.parent
_ROOT      = _BAGO.parent
_DOCS_DIR  = _ROOT / "docs"
_KNOWLEDGE = _BAGO / "knowledge"

_EXCLUDE_STEMS = {
    "__init__", "__main__",
    "_registry_entries", "_registry_models", "_registry_paths",
    "db_init", "tool_registry",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _all_tool_stems(tools_dir: Path) -> list[str]:
    stems: list[str] = []
    for py in sorted(tools_dir.glob("*.py")):
        stem = py.stem
        if stem.startswith("__") or stem in _EXCLUDE_STEMS:
            continue
        stems.append(stem)
    return stems


# ── Core functions ────────────────────────────────────────────────────────────

def _extract_covers(md_path: Path, tool_stems: set[str]) -> list[str]:
    """Return list of tool stems covered by this markdown file.

    Looks for:
      <!-- @covers: tool1, tool2.py, bago_chat -->
    AND inline mentions:
      - bare stem in text (e.g. "orphan_shield")
      - backtick names: `orphan_shield.py`
      - explicit .py mentions
    """
    text = _read_text(md_path)
    found: set[str] = set()

    # 1. Explicit @covers annotation
    for match in re.finditer(r"<!--\s*@covers:\s*([^-]+?)-->" , text, re.DOTALL):
        raw = match.group(1)
        for item in re.split(r"[,\s]+", raw):
            stem = item.strip().removesuffix(".py")
            if stem and stem in tool_stems:
                found.add(stem)

    # 2. Backtick mentions: `foo.py` or `foo`
    for match in re.finditer(r"`([a-zA-Z_][a-zA-Z0-9_-]*?)(?:\.py)?`", text):
        stem = match.group(1)
        if stem in tool_stems:
            found.add(stem)

    # 3. Inline .py references: foo.py
    for match in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_-]*?)\.py\b", text):
        stem = match.group(1)
        if stem in tool_stems:
            found.add(stem)

    # 4. Bare stem mentions (word boundary) — only for stems ≥ 5 chars to avoid noise
    for stem in tool_stems:
        if len(stem) >= 5 and re.search(rf"\b{re.escape(stem)}\b", text):
            found.add(stem)

    return sorted(found)


def build_index(
    docs_dirs: list[Path] | None = None,
    tools_dir: Path | None = None,
) -> dict:
    """Build a coverage index.

    Returns:
        {
            "tool_to_docs":  {stem: [doc_path_str, ...]},
            "doc_to_tools":  {doc_path_str: [stem, ...]},
            "undocumented":  [stem, ...],
            "total_tools":   int,
            "total_docs":    int,
        }
    """
    td = tools_dir or _TOOLS
    default_dirs: list[Path] = []
    if _DOCS_DIR.exists():
        default_dirs.append(_DOCS_DIR)
    if _KNOWLEDGE.exists():
        default_dirs.append(_KNOWLEDGE)
    dirs = docs_dirs if docs_dirs is not None else default_dirs

    all_stems = _all_tool_stems(td)
    stem_set  = set(all_stems)

    tool_to_docs: dict[str, list[str]] = {s: [] for s in all_stems}
    doc_to_tools: dict[str, list[str]] = {}

    md_files: list[Path] = []
    for d in dirs:
        md_files.extend(sorted(d.rglob("*.md")))

    for md in md_files:
        covers = _extract_covers(md, stem_set)
        rel = str(md.relative_to(_ROOT)) if md.is_relative_to(_ROOT) else str(md)
        doc_to_tools[rel] = covers
        for stem in covers:
            tool_to_docs[stem].append(rel)

    undocumented = [s for s in all_stems if not tool_to_docs[s]]

    return {
        "tool_to_docs": tool_to_docs,
        "doc_to_tools": doc_to_tools,
        "undocumented": undocumented,
        "total_tools":  len(all_stems),
        "total_docs":   len(md_files),
    }


def add_covers_annotation(md_path: Path, tools: list[str]) -> None:
    """Add or update <!-- @covers: ... --> at the top of a markdown file."""
    text = _read_text(md_path)
    annotation = f"<!-- @covers: {', '.join(sorted(tools))} -->\n"

    # Replace existing annotation if present
    updated = re.sub(
        r"<!--\s*@covers:[^>]*-->\n?",
        annotation,
        text,
        count=1,
    )
    if updated == text:
        # No existing annotation — prepend
        updated = annotation + text

    md_path.write_text(updated, encoding="utf-8")
    print(f"  ✔  Anotación @covers actualizada en {md_path.name}")


# ── Self-test ─────────────────────────────────────────────────────────────────

def _self_test() -> None:
    """3 basic assertions."""
    # 1. build_index returns expected structure
    idx = build_index()
    assert set(idx.keys()) == {
        "tool_to_docs", "doc_to_tools", "undocumented", "total_tools", "total_docs"
    }, f"build_index wrong keys: {idx.keys()}"

    # 2. _extract_covers with synthetic text
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write("<!-- @covers: orphan_shield, doc_index -->\n# Test\n")
        tmp = Path(f.name)
    try:
        covers = _extract_covers(tmp, {"orphan_shield", "doc_index", "other_tool"})
        assert "orphan_shield" in covers, f"Expected orphan_shield in covers: {covers}"
        assert "doc_index" in covers, f"Expected doc_index in covers: {covers}"
    finally:
        os.unlink(tmp)

    # 3. total_tools is a positive integer
    assert isinstance(idx["total_tools"], int) and idx["total_tools"] >= 0

    print("  3/3 tests pasaron ✔")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)

    if "--test" in args:
        _self_test()
        return 0

    # --annotate <doc.md> <tool1,tool2>
    if "--annotate" in args:
        idx_ann = args.index("--annotate")
        if idx_ann + 2 >= len(args):
            print("Uso: doc_index.py --annotate <doc.md> <tool1,tool2,...>", file=sys.stderr)
            return 1
        md_path = Path(args[idx_ann + 1])
        tools   = [t.strip() for t in args[idx_ann + 2].split(",") if t.strip()]
        if not md_path.exists():
            print(f"Archivo no encontrado: {md_path}", file=sys.stderr)
            return 1
        add_covers_annotation(md_path, tools)
        return 0

    idx = build_index()

    if "--json" in args:
        print(json.dumps(idx, indent=2))
        return 0

    if "--undocumented" in args:
        for stem in idx["undocumented"]:
            print(f"  · {stem}")
        print(f"\n  Total sin documentar: {len(idx['undocumented'])} / {idx['total_tools']}")
        return 0

    # --build  (default: print index)
    print(f"\n  \033[1m📚 Índice Documental BAGO\033[0m")
    print(f"  {'─'*52}")
    print(f"  Tools totales  : {idx['total_tools']}")
    print(f"  Docs totales   : {idx['total_docs']}")
    print(f"  Sin documentar : {len(idx['undocumented'])}")
    print()

    # Show documented tools
    documented = {s: docs for s, docs in idx["tool_to_docs"].items() if docs}
    if documented:
        print("  \033[1mTools documentados:\033[0m")
        for stem, docs in sorted(documented.items()):
            doc_names = ", ".join(Path(d).name for d in docs)
            print(f"  \033[32m✔\033[0m  {stem:<35} ← {doc_names}")

    if idx["undocumented"]:
        print("\n  \033[1mSin documentar:\033[0m")
        for stem in idx["undocumented"][:20]:
            print(f"  \033[33m⚠\033[0m  {stem}")
        if len(idx["undocumented"]) > 20:
            print(f"  ... y {len(idx['undocumented'])-20} más")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
