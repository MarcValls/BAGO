#!/usr/bin/env python3
"""context_detector.py - Detect when a context block is ready for harvest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bago_utils import get_scan_root, load_json  # noqa: E402


DECISION_RE = re.compile(
    r"\b(decision|decisions|decisiones|decisi[oó]n|decid(?:ed|ido|ida|idos|idas)?|"
    r"we decided|i decided|ya decid(?:i|í)|ya defini(?:mos|do))\b",
    re.IGNORECASE,
)
DISCARD_RE = re.compile(
    r"\b(descart(?:e|o|ado|ada|ados|adas)|discard(?:ed|s)?|rule(?:d)? out|ruled out|"
    r"no se descart(?:o|ó)|no descart(?:e|o))\b",
    re.IGNORECASE,
)
NEXT_STEP_RE = re.compile(
    r"\b(next[_ -]?step|next step|siguiente paso|proximo paso|pr[oó]ximo paso)\b",
    re.IGNORECASE,
)
EVIDENCE_RE = re.compile(
    r"\b(evidence|evidencia|verified|verificado|tests?|pruebas?|sha256|fingerprint|"
    r"commit|check(s)?|exit code|resultado)\b",
    re.IGNORECASE,
)
STRUCTURE_RE = re.compile(r"(?m)^\s*[-*]\s+|^\s*\d+\.\s+|^\s*#{1,6}\s+")
AMBIGUITY_RE = re.compile(
    r"\b(pendiente|todav[ií]a|unclear|maybe|quiz[aá]|seguimos explorando|still exploring|"
    r"no estoy seguro|no estoy segura|no queda claro|follow up)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceAnalysis:
    source: str
    line_count: int
    decision_hits: int
    discard_hits: int
    next_step_hits: int
    evidence_hits: int
    structured_lines: int
    ambiguity_hits: int


@dataclass(frozen=True)
class DetectionResult:
    verdict: str
    score: int
    reasons: tuple[str, ...]
    sources: tuple[str, ...]
    source_analysis: tuple[SourceAnalysis, ...]
    threshold: int

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "reasons": list(self.reasons),
            "sources": list(self.sources),
            "threshold": self.threshold,
            "source_analysis": [asdict(item) for item in self.source_analysis],
        }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _json_text(path: Path) -> str:
    payload = load_json(path, {})
    if not payload:
        return ""
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _load_sources(root: Path) -> list[tuple[str, str]]:
    candidates = [
        (".bago/runtime/ACTIVE_HANDOFF.md", root / ".bago" / "runtime" / "ACTIVE_HANDOFF.md"),
        (".bago/state/PROJECT_STATE.json", root / ".bago" / "state" / "PROJECT_STATE.json"),
        (".bago/state/global_state.json", root / ".bago" / "state" / "global_state.json"),
        (".bago/state/context.json", root / ".bago" / "state" / "context.json"),
    ]
    out: list[tuple[str, str]] = []
    for rel, path in candidates:
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            text = _json_text(path)
        else:
            text = _read_text(path)
        if text.strip():
            out.append((rel, text))
    return out


def _count_matches(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text))


def _analyze_source(source: str, text: str) -> SourceAnalysis:
    return SourceAnalysis(
        source=source,
        line_count=sum(1 for line in text.splitlines() if line.strip()),
        decision_hits=_count_matches(DECISION_RE, text),
        discard_hits=_count_matches(DISCARD_RE, text),
        next_step_hits=_count_matches(NEXT_STEP_RE, text),
        evidence_hits=_count_matches(EVIDENCE_RE, text),
        structured_lines=len(STRUCTURE_RE.findall(text)),
        ambiguity_hits=_count_matches(AMBIGUITY_RE, text),
    )


def detect_context(
    texts: Iterable[tuple[str, str]],
    *,
    threshold: int = 4,
) -> DetectionResult:
    analyses = tuple(_analyze_source(source, text) for source, text in texts if text.strip())
    sources = tuple(analysis.source for analysis in analyses)
    decision_hits = sum(item.decision_hits for item in analyses)
    discard_hits = sum(item.discard_hits for item in analyses)
    next_step_hits = sum(item.next_step_hits for item in analyses)
    evidence_hits = sum(item.evidence_hits for item in analyses)
    structured_hits = sum(1 for item in analyses if item.structured_lines > 0)
    ambiguity_hits = sum(item.ambiguity_hits for item in analyses)

    score = 0
    reasons: list[str] = []

    if decision_hits:
        score += 1
        reasons.append("decision_signal")
    if discard_hits:
        score += 1
        reasons.append("discard_signal")
    if next_step_hits:
        score += 1
        reasons.append("next_step_signal")
    if evidence_hits:
        score += 1
        reasons.append("evidence_signal")
    if structured_hits:
        score += 1
        reasons.append("structured_context")
    if ambiguity_hits:
        score -= 1
        reasons.append("ambiguity_signal")

    harvest_ready = (
        decision_hits > 0
        and discard_hits > 0
        and next_step_hits > 0
        and (evidence_hits > 0 or structured_hits > 0)
    )
    verdict = "HARVEST" if harvest_ready and score >= threshold else "CONTINUE"
    if verdict == "HARVEST":
        reasons.append("harvest_threshold_met")
    else:
        reasons.append("harvest_threshold_not_met")
    return DetectionResult(
        verdict=verdict,
        score=score,
        reasons=tuple(dict.fromkeys(reasons)),
        sources=sources,
        source_analysis=analyses,
        threshold=threshold,
    )


def format_result(result: DetectionResult) -> str:
    sources = ", ".join(result.sources) if result.sources else "none"
    reasons = ", ".join(result.reasons) if result.reasons else "none"
    return (
        f"{result.verdict}\n"
        f"score={result.score} threshold={result.threshold}\n"
        f"sources={sources}\n"
        f"reasons={reasons}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect when a context block is ready for W9 harvest.")
    parser.add_argument("--root", default="", help="Project root to inspect")
    parser.add_argument("--text", default="", help="Direct text to inspect instead of workspace state")
    parser.add_argument("--threshold", type=int, default=4, help="Score threshold for HARVEST")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    return parser


def run_detection(root: Path, text: str = "", *, threshold: int = 4) -> DetectionResult:
    if text.strip():
        sources = [("text", text)]
    else:
        sources = _load_sources(root)
    return detect_context(sources, threshold=threshold)


def run_self_tests() -> int:
    import shutil
    import tempfile

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".bago" / "runtime").mkdir(parents=True)
        (root / ".bago" / "state").mkdir(parents=True)

        (root / ".bago" / "runtime" / "ACTIVE_HANDOFF.md").write_text(
            "Decision: use a semantic trigger.\n"
            "Discard: 30-minute timer.\n"
            "Next step: implement context_detector.py.\n"
            "Evidence: tests, hash checks, and runtime sync.\n",
            encoding="utf-8",
        )
        result = run_detection(root)
        record("context:harvest", result.verdict == "HARVEST", result.verdict)
        record("context:score", result.score >= 4, f"score={result.score}")

        (root / ".bago" / "runtime" / "ACTIVE_HANDOFF.md").write_text(
            "Still exploring ideas; nothing decided yet.\n",
            encoding="utf-8",
        )
        result = run_detection(root)
        record("context:continue", result.verdict == "CONTINUE", result.verdict)

        text_result = run_detection(root, text="decision discard next step evidence")
        record("context:text_override", text_result.verdict == "HARVEST", text_result.verdict)

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"{'OK' if ok else 'FAIL'}: {name} - {detail}")
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.test:
        return run_self_tests()

    root = get_scan_root(args.root)
    if not root.exists() or not root.is_dir():
        print(f"Error: invalid root {root}", file=sys.stderr)
        return 2

    result = run_detection(root, args.text, threshold=max(1, int(args.threshold)))
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
