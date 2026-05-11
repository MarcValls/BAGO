#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from session._logger import *  # noqa: F401,F403

__all__ = ["SessionLogger"]

if __name__ == "__main__":
    main()
