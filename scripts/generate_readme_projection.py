#!/usr/bin/env python3
"""Generate the machine-owned truth projection embedded in README.md.

Sources:
- release_version.txt
- package.json engines.node
- backend/docs/contracts/execution_gateway_unification_plan.v1.md

Only the marked README block is generated. The rest of README.md remains
human-authored product/release documentation.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
from pathlib import Path


CANONICAL_GENERATOR = (
    Path(__file__).resolve().parents[1]
    / "backend/scripts/generate_readme_projection.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "bago_readme_projection", CANONICAL_GENERATOR
)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Cannot load canonical README projection: {CANONICAL_GENERATOR}")
_CANONICAL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CANONICAL)

BEGIN = _CANONICAL.START
END = _CANONICAL.END


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render(root: Path) -> str:
    del root  # The canonical generator owns the README markers and projection.
    return _CANONICAL.render_block(_CANONICAL.build_projection())


def _replace_projection(readme: str, projection: str) -> str:
    try:
        return _CANONICAL._replace_block(readme, projection)
    except _CANONICAL.ProjectionError as exc:
        raise ValueError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    path = root / "README.md"

    try:
        current = _read(path)
        expected_projection = render(root)
        expected = _replace_projection(current, expected_projection)
    except (OSError, ValueError, _CANONICAL.ProjectionError) as exc:
        print(f"error: {exc}")
        return 2

    if args.check:
        if current != expected:
            print(
                "error: README generated truth projection drifted. "
                "Run: python scripts/generate_readme_projection.py"
            )
            diff = difflib.unified_diff(
                current.splitlines(),
                expected.splitlines(),
                fromfile="README.md",
                tofile="README.md (generated)",
                lineterm="",
            )
            for line in diff:
                print(line)
            return 2
        print("README generated truth projection PASS")
        return 0

    path.write_text(expected, encoding="utf-8")
    print("README generated truth projection updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
