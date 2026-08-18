#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SEV_ERROR = "ERROR"
SEV_WARN = "WARN"
SEV_INFO = "INFO"
DOC_EXTS = {".md", ".txt", ".rst"}
DEFAULT_EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "RELEASE", "cleanversion", "sandbox",
    ".bago", ".bago/state", ".bago/state/sessions", ".bago/state/changes", ".bago/state/evidences",
}

FLATTERY_TERMS = [
    r"espectacular", r"impecable", r"robust[íi]simo", r"excelent[ií]simo",
    r"de\s+primer\s+nivel", r"nivel\s+enterprise", r"world[- ]class",
    r"state[- ]of[- ]the[- ]art", r"perfectamente\s+orquestad[oa]",
    r"sin\s+igual", r"magn[íi]fic[oa]", r"rompedor", r"asombroso",
    r"espectacularmente", r"incre[íi]ble(?:mente)?", r"flawless",
    r"bulletproof", r"legendari[oa]", r"rocket[- ]?ship",
]

UNSUBSTANTIATED_ABSOLUTES = [
    r"\b100\s*%\b", r"\btotalmente\b", r"\bcompletamente\b(?!\s+opcional)",
    r"\bsiempre\s+funciona\b", r"\bnunca\s+falla\b", r"\bsin\s+fallos?\b",
    r"\bgarantizad[oa]s?\b", r"\bsin\s+errores?\b", r"\bcero\s+errores?\b",
    r"\bzero[- ]bug\b", r"\b100%\s+stable\b", r"\bno\s+tiene\s+bugs?\b",
]

SUCCESS_WASHING = [
    r"✅\s*completad[oa]", r"✅\s*listo", r"listo\s+para\s+producci[óo]n",
    r"production[- ]ready", r"ready\s+to\s+ship", r"green\s+across\s+the\s+board",
    r"todo\s+OK", r"todo\s+verde", r"all\s+green", r"no\s+hay\s+nada\s+pendiente",
]

FUTURE_PROMISES = [
    r"\bse\s+va\s+a\b", r"\bpróximamente\b", r"\bproximamente\b",
    r"\bplanned\b", r"\bto\s+be\s+implemented\b", r"\bTBD\b",
    r"\bfuturo\s+pr[óo]ximo\b", r"\ben\s+breve\b",
]

DONE_CONTEXT_HEADERS = [
    r"\bcompletad[oa]s?\b", r"\bterminad[oa]s?\b", r"\bcerrad[oa]s?\b",
    r"\bdone\b", r"\bhecho\b", r"\bimplementad[oa]s?\b",
    r"\bresuelt[oa]s?\b", r"\bfix(?:ed)?\b",
]

STRONG_CLAIMS = [
    r"\bPASSED\b", r"\bSTABLE\b", r"\bPRODUCTION[- ]READY\b",
]

EVIDENCE_HINTS = [
    r"\.json\b", r"\.md\b", r"\.py\b", r"\.ps1\b", r"\.ts\b", r"\.log\b",
    r"\bevidenc", r"\btest", r"\bexit[_ ]?code\b", r"\bsha\b",
    r"\bchecksums?\b", r"\bruntime\b", r"\bcommit\b",
    r"https?://", r"#L\d+", r"\[.+?\]\(.+?\)",
]

EXEMPT_PATTERNS = [
    r"/templates/", r"/prompts/", r"PLANTILLA", r"plantilla",
    r"/canon/", r"GLOSARIO", r"/schema/",
    r"/migration/legacy/", r"/agents/", r"/workflows/",
    r"/docs/governance/", r"/docs/migration/",
]


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    kind: str
    excerpt: str
    why: str

    def fmt(self) -> str:
        return f"[{self.severity}] {self.kind} {self.file}:{self.line}\n  > {self.excerpt.strip()}\n  - {self.why}"


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def is_exempt(path: Path) -> bool:
    sp = str(path).replace("\\", "/")
    return any(re.search(p, sp) for p in EXEMPT_PATTERNS)


def iter_doc_files(base: Path, excludes: set[str]) -> Iterable[Path]:
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in DOC_EXTS:
            continue
        rel = str(path.relative_to(base)).replace("\\", "/")
        rel_parts = Path(rel).parts
        if any(part in excludes for part in rel_parts):
            continue
        if any(rel.startswith(ex.replace("\\", "/")) for ex in excludes if "/" in ex or "\\" in ex):
            continue
        yield path


def find_all(patterns: list[str], text: str, flags: int = re.IGNORECASE) -> list[re.Match[str]]:
    hits: list[re.Match[str]] = []
    for pat in patterns:
        hits.extend(re.finditer(pat, text, flags))
    return hits


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def line_text(text: str, line_no: int) -> str:
    lines = text.splitlines()
    return lines[line_no - 1] if 1 <= line_no <= len(lines) else ""


def _has_evidence(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in EVIDENCE_HINTS)


def scan_flattery(root: Path, path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    for match in find_all(FLATTERY_TERMS, text):
        line_no = line_of(text, match.start())
        excerpt = line_text(text, line_no)
        if _has_evidence(excerpt):
            continue
        out.append(Finding(_display_path(root, path), line_no, SEV_WARN, "FLATTERY", excerpt, "Decorative adjective without evidence."))
    return out


def scan_unsubstantiated(root: Path, path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    for match in find_all(UNSUBSTANTIATED_ABSOLUTES, text):
        line_no = line_of(text, match.start())
        excerpt = line_text(text, line_no)
        if _has_evidence(excerpt):
            continue
        out.append(Finding(_display_path(root, path), line_no, SEV_ERROR, "UNSUBSTANTIATED", excerpt, "Absolute claim without evidence."))
    return out


def scan_success_washing(root: Path, path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    for match in find_all(SUCCESS_WASHING, text):
        line_no = line_of(text, match.start())
        excerpt = line_text(text, line_no)
        if re.search(r"\?|not[_ -]?ready|no\s+listo|conditional|condiciones", excerpt, re.IGNORECASE):
            continue
        if _has_evidence(excerpt):
            continue
        out.append(Finding(_display_path(root, path), line_no, SEV_WARN, "SUCCESS_WASHING", excerpt, "Success wording without artifact or reference."))
    return out


def scan_future_as_done(root: Path, path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    current_header = ""
    header_is_done = False
    header_line = 0
    for idx, raw in enumerate(text.splitlines(), start=1):
        header = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", raw)
        if header:
            current_header = header.group(1).strip()
            header_is_done = any(re.search(p, current_header, re.IGNORECASE) for p in DONE_CONTEXT_HEADERS)
            header_line = idx
            continue
        if not header_is_done or not current_header:
            continue
        for pat in FUTURE_PROMISES:
            if re.search(pat, raw, re.IGNORECASE):
                out.append(Finding(_display_path(root, path), idx, SEV_ERROR, "FUTURE_AS_DONE", raw, f"Future promise under done header '{current_header}' (line {header_line})."))
                break
    return out


def scan_evidence_missing(root: Path, path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    lines = text.splitlines()
    for match in find_all(STRONG_CLAIMS, text, flags=0):
        line_no = line_of(text, match.start())
        excerpt = line_text(text, line_no)
        window = "\n".join(lines[line_no - 1: line_no + 2])
        if _has_evidence(window):
            continue
        out.append(Finding(_display_path(root, path), line_no, SEV_ERROR, "EVIDENCE_MISSING", excerpt, "Strong claim without nearby evidence."))
    return out


def scan_empty_checklist(root: Path, path: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    for idx, raw in enumerate(text.splitlines(), start=1):
        match = re.match(r"^\s*[-*]\s*\[x\]\s*(.+)$", raw, re.IGNORECASE)
        if not match:
            continue
        content = match.group(1).strip()
        if len(content) < 20 and not re.search(r"[./#(]|\b\w+\.\w+\b", content):
            out.append(Finding(_display_path(root, path), idx, SEV_WARN, "EMPTY_CHECKLIST", raw, "Checked item without detail or reference."))
    return out


SCANNERS = [
    scan_flattery,
    scan_unsubstantiated,
    scan_success_washing,
    scan_future_as_done,
    scan_evidence_missing,
    scan_empty_checklist,
]


def scan_file(root: Path, path: Path) -> list[Finding]:
    if is_exempt(path):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings: list[Finding] = []
    for scanner in SCANNERS:
        findings.extend(scanner(root, path, text))
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detects empty marketing patterns in documentation.")
    parser.add_argument("--root", default="", help="Project root to scan. Default: cwd")
    parser.add_argument("--path", default="", help="Specific file or directory to scan")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--strict", action="store_true", help="Return exit 1 on WARN too")
    parser.add_argument("--test", action="store_true", help="Run self tests")
    return parser


def _resolve_target(root: Path, path_arg: str) -> Path:
    if not path_arg:
        return root
    candidate = Path(path_arg)
    if candidate.is_absolute():
        return candidate
    return root / candidate


def run_scan(root: Path, target: Path) -> tuple[list[Path], list[Finding]]:
    if target.is_file():
        files = [target] if target.suffix.lower() in DOC_EXTS else []
    else:
        files = list(iter_doc_files(target, DEFAULT_EXCLUDE_DIRS))
    findings: list[Finding] = []
    for path in files:
        findings.extend(scan_file(root, path))
    sev_rank = {SEV_ERROR: 0, SEV_WARN: 1, SEV_INFO: 2}
    findings.sort(key=lambda item: (sev_rank.get(item.severity, 9), item.file, item.line))
    return files, findings


def _print_report(root: Path, target: Path, files: list[Path], findings: list[Finding], as_json: bool) -> None:
    totals = {
        SEV_ERROR: sum(1 for item in findings if item.severity == SEV_ERROR),
        SEV_WARN: sum(1 for item in findings if item.severity == SEV_WARN),
        SEV_INFO: sum(1 for item in findings if item.severity == SEV_INFO),
    }
    if as_json:
        payload = {
            "root": str(root),
            "target": str(target),
            "scanned_files": len(files),
            "findings": [asdict(item) for item in findings],
            "totals": totals,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return
    print("SINCERITY DETECTOR")
    print(f"Root: {root}")
    print(f"Target: {target}")
    print(f"Files: {len(files)}")
    print(f"Findings: {len(findings)}")
    for item in findings:
        print(item.fmt())
    print("Summary:")
    print(f"  ERROR={totals[SEV_ERROR]}")
    print(f"  WARN={totals[SEV_WARN]}")


def _selftest_dir() -> Path:
    return Path(__file__).resolve().parent / ".selftest_sincerity_detector"


def run_self_tests() -> int:
    base = _selftest_dir()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    try:
        t1 = base / "flat.md"
        t1.write_text("Sistema espectacular\n", encoding="utf-8")
        _, findings = run_scan(base, t1)
        ok1 = any(item.kind == "FLATTERY" for item in findings)

        t2 = base / "evidence.md"
        t2.write_text("Siempre funciona segun test_result.json\n", encoding="utf-8")
        _, findings = run_scan(base, t2)
        ok2 = not any(item.kind == "UNSUBSTANTIATED" for item in findings)

        t3 = base / "future.rst"
        t3.write_text("# Done\nse va a implementar luego\n", encoding="utf-8")
        _, findings = run_scan(base, t3)
        ok3 = any(item.kind == "FUTURE_AS_DONE" for item in findings)

        t4 = base / "check.txt"
        t4.write_text("- [x] ok\n", encoding="utf-8")
        _, findings = run_scan(base, t4)
        ok4 = any(item.kind == "EMPTY_CHECKLIST" for item in findings)

        docs = base / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("PASSED\n", encoding="utf-8")
        (docs / "b.txt").write_text("todo OK\n", encoding="utf-8")
        files, findings = run_scan(base, docs)
        ok5 = len(files) == 2 and any(item.kind == "EVIDENCE_MISSING" for item in findings)

        results = [ok1, ok2, ok3, ok4, ok5]
        passed = sum(1 for item in results if item)
        print(f"{passed}/{len(results)} tests passed")
        return 0 if passed == len(results) else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test:
        return run_self_tests()
    root = Path(args.root or Path.cwd()).resolve()
    target = _resolve_target(root, args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: invalid root {root}", file=sys.stderr)
        return 2
    if not target.exists():
        print(f"Error: target not found {target}", file=sys.stderr)
        return 2
    files, findings = run_scan(root, target)
    _print_report(root, target, files, findings, args.json)
    has_error = any(item.severity == SEV_ERROR for item in findings)
    has_warn = any(item.severity == SEV_WARN for item in findings)
    if has_error or (args.strict and has_warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
