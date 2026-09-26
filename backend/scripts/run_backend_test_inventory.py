"""Run the full backend test inventory in deterministic shards.

GitHub-hosted Windows runners intermittently interrupt a single monolithic
``pytest backend/tests -q`` invocation before collection completes. This helper
keeps coverage equivalent while splitting the suite into reproducible chunks
that finish within the runner limits observed in CI.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
TEST_ROOT = BACKEND_ROOT / "tests"
INTEGRATION_ROOT = TEST_ROOT / "integrations"


def _top_level_test_files() -> list[Path]:
    return sorted(TEST_ROOT.glob("test_*.py"))


def _shard_test_files(paths: list[Path], shard_count: int) -> list[list[Path]]:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    shards: list[list[Path]] = [[] for _ in range(shard_count)]
    for index, path in enumerate(paths):
        shards[index % shard_count].append(path)
    return [shard for shard in shards if shard]


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _run_pytest(args: list[str], label: str) -> int:
    print(f"[backend-test-inventory] {label}: {' '.join(args)}", flush=True)
    completed = subprocess.run([sys.executable, "-m", "pytest", "-q", *args], cwd=REPO_ROOT)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--flat-shards",
        type=int,
        default=4,
        help="Number of shards for backend/tests/test_*.py (default: 4).",
    )
    args = parser.parse_args(argv)

    top_level_files = _top_level_test_files()
    if not top_level_files:
        print("[backend-test-inventory] no backend/tests/test_*.py files found", file=sys.stderr)
        return 1

    shard_args = [[_repo_relative(path) for path in shard] for shard in _shard_test_files(top_level_files, args.flat_shards)]
    runs: list[tuple[str, list[str]]] = [("integrations", [_repo_relative(INTEGRATION_ROOT)])]
    runs.extend((f"flat-shard-{index}", shard) for index, shard in enumerate(shard_args, start=1))

    for label, run_args in runs:
        exit_code = _run_pytest(run_args, label)
        if exit_code != 0:
            return exit_code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
