from pathlib import Path
import sys

PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))
