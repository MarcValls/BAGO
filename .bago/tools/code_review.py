#!/usr/bin/env python3
from __future__ import annotations

"""code_review.py — canonical `bago review` report generator."""

import argparse
import json
import sys
from pathlib import Path

from _review_collectors import CI_MIN_SCORE, DEFAULT_MIN_SCORE, REVIEW_COMMAND, run_reviews
from _review_renderers import generate_markdown, generate_text, verdict_id


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog=REVIEW_COMMAND)
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--branch", default="")
    parser.add_argument("--format", choices=("text", "md", "json"), default="text")
    parser.add_argument("--out", default="")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--base", default="")
    parser.add_argument("--sarif", action="append", default=[])
    parser.add_argument("--test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    if args.test:
        return 0

    scope_root = Path(args.directory).resolve()
    if not scope_root.exists():
        print(f"No existe: {args.directory}", file=sys.stderr)
        return 1

    min_score = max(args.min_score, CI_MIN_SCORE) if args.ci else args.min_score
    print(f"Analizando {scope_root} con {REVIEW_COMMAND}…", file=sys.stderr)
    report = run_reviews(
        str(scope_root),
        args.branch,
        min_score=min_score,
        changed_only=args.changed_only,
        base_ref=args.base,
        ci=args.ci,
        sarif_paths=args.sarif,
    )

    if args.format == "json":
        content = json.dumps(report, indent=2, sort_keys=True)
    elif args.format == "md":
        content = generate_markdown(report)
    else:
        content = generate_text(report)

    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"Guardado: {args.out}", file=sys.stderr)
    else:
        print(content)

    if report.get("blocker_count", 0) > 0 or report["score"] < min_score:
        return 1
    if args.ci and verdict_id(report["verdict"]) != "mergeable":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
