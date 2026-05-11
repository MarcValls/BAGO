#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from session._close import *  # noqa: F401,F403
from session._close import _self_test, _test_enrich_last_completed, main  # noqa: F401

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        _test_enrich_last_completed()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv[1:]))
