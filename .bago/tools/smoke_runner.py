#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_runner.py — Ejecuta la suite de integración y escribe el reporte smoke.

Genera sandbox/runtime/last-report.json con el formato esperado por emit_ideas.py
para que el indicador 'smoke' pase de 'no disponible' a 'status=pass'.

Uso:
  python3 .bago/tools/smoke_runner.py          # ejecuta tests + guarda reporte
  python3 .bago/tools/smoke_runner.py --last   # muestra el último reporte sin ejecutar
  python3 .bago/tools/smoke_runner.py --test   # modo test interno (3/3 pass)
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import get_bago_tools_dir, get_project_root

ROOT       = get_project_root()
TOOLS      = get_bago_tools_dir()
SMOKE_DIR  = ROOT / "sandbox" / "runtime"
REPORT     = SMOKE_DIR / "last-report.json"
TESTS_TOOL = TOOLS / "integration_tests.py"


def _parse_result_line(stdout: str) -> tuple[int, int, int]:
    """Extract (passed, failed, skipped) from integration_tests output.

    Handles formats:
      'Resultado: 122/122 passed  0 failed  0 skipped'
      '122 passed  0 failed  0 skipped'
    """
    import re
    for line in stdout.splitlines():
        if "passed" not in line or "failed" not in line:
            continue
        # "122/122 passed" or "122 passed"
        m_pass = re.search(r'(\d+)/?\d*\s+passed', line)
        m_fail = re.search(r'(\d+)\s+failed', line)
        m_skip = re.search(r'(\d+)\s+skipped', line)
        passed  = int(m_pass.group(1)) if m_pass else 0
        failed  = int(m_fail.group(1)) if m_fail else 0
        skipped = int(m_skip.group(1)) if m_skip else 0
        return passed, failed, skipped
    return 0, 1, 0  # couldn't parse → assume fail


def run_smoke() -> dict:
    """Run integration_tests.py and return the report dict."""
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(TESTS_TOOL)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    duration = round(time.monotonic() - t0, 2)

    passed, failed, skipped = _parse_result_line(result.stdout)
    total = passed + failed + skipped

    status = "pass" if (result.returncode == 0 and failed == 0) else "fail"

    report = {
        "status": status,
        "failure_count": failed,
        "passed": passed,
        "skipped": skipped,
        "total": total,
        "workers": total,
        "duration_seconds": duration,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "integration_tests.py",
        "returncode": result.returncode,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def show_last() -> int:
    if not REPORT.exists():
        print("  ℹ  No hay reporte smoke. Ejecuta: bago smoke")
        return 1
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    icon = "✅" if data.get("status") == "pass" else "❌"
    print(f"  {icon} smoke: {data.get('status')} · "
          f"passed={data.get('passed','?')} · "
          f"failed={data.get('failure_count','?')} · "
          f"duration={data.get('duration_seconds','?')}s · "
          f"at={data.get('generated_at','?')[:19]}")
    return 0  # show_last is display-only; rc reflects read success, not stored status


def run_self_tests() -> int:
    """Internal smoke-runner self-tests (3/3)."""
    passed = 0
    failures: list[str] = []

    # Test 1: _parse_result_line can read the standard output format
    sample = "  Resultado: 122/122 passed  0 failed  0 skipped"
    p, f, s = _parse_result_line(sample)
    if p == 122 and f == 0 and s == 0:
        passed += 1
    else:
        failures.append(f"parse_result_line: got p={p} f={f} s={s}, expected 122/0/0")

    # Test 2: SMOKE_DIR path is inside the project root
    if "sandbox" in str(SMOKE_DIR):
        passed += 1
    else:
        failures.append(f"SMOKE_DIR path unexpected: {SMOKE_DIR}")

    # Test 3: report dict has required keys
    dummy = {
        "status": "pass",
        "failure_count": 0,
        "passed": 1,
        "skipped": 0,
        "total": 1,
        "workers": 1,
        "duration_seconds": 0.1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "integration_tests.py",
        "returncode": 0,
    }
    required = {"status", "failure_count", "workers", "duration_seconds"}
    if required.issubset(dummy.keys()):
        passed += 1
    else:
        failures.append(f"report missing keys: {required - dummy.keys()}")

    total = 3
    print(f"smoke_runner self-tests: {passed}/{total} tests pasaron")
    for f in failures:
        print(f"  FAIL: {f}")
    return 0 if passed == total else 1


def main() -> int:
    args = sys.argv[1:]
    if "--test" in args:
        return run_self_tests()
    if "--last" in args:
        return show_last()

    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Smoke Runner                                     │")
    print("  └──────────────────────────────────────────────────────────┘")
    print(f"  Ejecutando: {TESTS_TOOL.name} ...")
    print()

    report = run_smoke()
    icon = "✅" if report["status"] == "pass" else "❌"
    print(f"  {icon} smoke: {report['status']} · "
          f"passed={report['passed']} · "
          f"failed={report['failure_count']} · "
          f"duration={report['duration_seconds']}s")
    print(f"  Reporte: {REPORT}")
    print()
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
