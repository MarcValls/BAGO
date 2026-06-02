"""Verifies that `bago node validate` includes the `modular_guard` check
and that the guard reports zero errors."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
result = subprocess.run(
    ["python", "-m", "bago_core.node_control", "validate", "--json"],
    cwd=str(REPO_ROOT),
    capture_output=True,
    text=True,
    timeout=60,
)
try:
    data = json.loads(result.stdout)
except json.JSONDecodeError as exc:
    print("FAIL: validate did not emit JSON:", exc)
    print(result.stdout[:400])
    sys.exit(1)
checks = {c["name"]: c for c in data.get("checks", [])}
guard = checks.get("modular_guard")
if not guard:
    print("FAIL: modular_guard check missing from validate output")
    print("found checks:", list(checks))
    sys.exit(1)
if not guard.get("ok"):
    print("FAIL: modular_guard reported errors:", guard.get("detail"))
    sys.exit(1)
print("OK:", guard)
sys.exit(0)
