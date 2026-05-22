#!/usr/bin/env python3
"""bago — thin entry point. All logic lives in bago_core.launcher package."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.launcher import main

if __name__ == "__main__":
    main()
