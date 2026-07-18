"""Roundtrip smoke test for the translator layer."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from any cwd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bago_core.translators import list_translators, smoke_test_piece, smoke_test_all  # noqa: E402


def main() -> int:
    pieces = list_translators()
    print("=== Translator pieces discovered ===")
    for p in pieces:
        print(f"  - {p['piece_id']:50s} {p['model_family']}/{p['model_id']}")
    print()
    print("=== Smoke test (encode -> decode roundtrip) ===")
    results = smoke_test_all()
    failed = 0
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        print(f"  [{status}] {r['piece_id']}")
        if not r["ok"]:
            failed += 1
            mismatches = r.get("mismatches", [])
            error      = r.get("error", "")
            if mismatches:
                print(f"        mismatches: {mismatches}")
            if error:
                print(f"        error:      {error}")

    total = len(results)
    passed = total - failed
    print()
    print(f"{passed}/{total} translator pieces pass roundtrip smoke test")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
