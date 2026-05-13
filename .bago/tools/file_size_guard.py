from __future__ import annotations

"""file_size_guard.py — Detecta monolitos candidatos a dividir en .bago/tools/."""

import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
LINE_LIMIT = 400


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def _scan(limit: int = LINE_LIMIT) -> list[tuple[str, int]]:
    offenders: list[tuple[str, int]] = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        lines = _count_lines(path)
        if lines > limit:
            offenders.append((path.name, lines))
    return offenders


def _print_text(offenders: list[tuple[str, int]], limit: int) -> None:
    print(f"  .bago/tools/ — monolito candidates (> {limit} líneas)")
    if not offenders:
        print("  GO — no se detectaron monolitos candidatos a dividir")
        return
    for name, lines in offenders:
        print(f"  - {name}: {lines} líneas")


def _self_test() -> None:
    offenders = _scan()
    assert isinstance(offenders, list)
    assert LINE_LIMIT == 400
    assert all(name.endswith('.py') and lines > LINE_LIMIT for name, lines in offenders)
    print(f"  3/3 tests pasaron  ({len(offenders)} candidatos detectados)")


def main() -> int:
    args = sys.argv[1:]
    if '--test' in args:
        _self_test()
        return 0

    offenders = _scan()
    if '--json' in args:
        print(json.dumps({
            'limit': LINE_LIMIT,
            'count': len(offenders),
            'offenders': [{'file': name, 'lines': lines} for name, lines in offenders],
        }, indent=2, ensure_ascii=False))
        return 0

    _print_text(offenders, LINE_LIMIT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
