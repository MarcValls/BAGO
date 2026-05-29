"""python -m creation_mode"""
from __future__ import annotations
import sys
from .engine import main

if __name__ == "__main__":
    sys.exit(main())



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
