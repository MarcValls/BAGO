#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_runner.py — Smoke pack por defecto + suite de integración opcional.

Por defecto valida:
  - validate_pack.py
  - health_score.py --score-only
  - coherencia de la última cosecha cerrada, si existe

Opciones:
  python3 .bago/tools/smoke_runner.py              # smoke del pack
  python3 .bago/tools/smoke_runner.py --integration # suite de integración anterior
  python3 .bago/tools/smoke_runner.py --last       # muestra el último reporte
  python3 .bago/tools/smoke_runner.py --test       # autotest interno
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_PARENT = ROOT.parent
TOOLS = ROOT / "tools"
SMOKE_DIR = ROOT / "sandbox" / "runtime"
REPORT = SMOKE_DIR / "last-report.json"
TESTS_TOOL = TOOLS / "integration_tests.py"


def _run_tool(tool: str, args: list[str] | None = None) -> tuple[int, str]:
    cmd = [sys.executable, str(TOOLS / tool)] + (args or [])
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(PACK_PARENT),
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f"ERROR: {e}"


def _parse_result_line(stdout: str) -> tuple[int, int, int]:
    for line in stdout.splitlines():
        if "passed" not in line or "failed" not in line:
            continue
        m_pass = re.search(r"(\d+)/?\d*\s+passed", line)
        m_fail = re.search(r"(\d+)\s+failed", line)
        m_skip = re.search(r"(\d+)\s+skipped", line)
        passed = int(m_pass.group(1)) if m_pass else 0
        failed = int(m_fail.group(1)) if m_fail else 0
        skipped = int(m_skip.group(1)) if m_skip else 0
        return passed, failed, skipped
    return 0, 1, 0


def _parse_health_score(stdout: str) -> tuple[int, str] | None:
    m = re.search(r"(\d+)\s+(green|yellow|red|grey)\b", stdout.lower())
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def _load_global_state() -> dict:
    path = ROOT / "state" / "global_state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _check_last_harvest() -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    gs = _load_global_state()
    session_id = gs.get("last_completed_session_id")
    if not session_id:
        warnings.append("no hay última cosecha cerrada registrada")
        return warnings, failures

    sessions_dir = ROOT / "state" / "sessions"
    changes_dir = ROOT / "state" / "changes"
    evidences_dir = ROOT / "state" / "evidences"
    session_path = sessions_dir / f"{session_id}.json"
    if not session_path.exists():
        failures.append(f"last_completed_session_id apunta a un fichero ausente: {session_id}")
        return warnings, failures

    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(f"no se pudo leer la sesión {session_id}: {exc}")
        return warnings, failures

    if session.get("status") != "closed":
        failures.append(f"la última sesión no está cerrada: {session_id}")

    change_id = gs.get("last_completed_change_id")
    evidence_id = gs.get("last_completed_evidence_id")
    if change_id and not (changes_dir / f"{change_id}.json").exists():
        failures.append(f"last_completed_change_id apunta a un fichero ausente: {change_id}")
    if evidence_id and not (evidences_dir / f"{evidence_id}.json").exists():
        failures.append(f"last_completed_evidence_id apunta a un fichero ausente: {evidence_id}")

    if not change_id or not evidence_id:
        warnings.append("la última cosecha no expone CHG/EVD completos")

    return warnings, failures


def run_pack_smoke() -> dict:
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    warnings: list[str] = []
    failures: list[str] = []

    v_rc, v_out = _run_tool("validate_pack.py")
    pack_ok = v_rc == 0 and "GO pack" in v_out
    if not pack_ok:
        failures.append((v_out.splitlines() or ["validate_pack falló"])[-1])

    h_rc, h_out = _run_tool("health_score.py", ["--score-only"])
    health = _parse_health_score(h_out)
    if h_rc != 0 or health is None:
        failures.append("health_score no devolvió un score legible")
        health_score = None
        health_color = None
    else:
        health_score, health_color = health
        if health_score < 80:
            warnings.append(f"health score bajo: {health_score} {health_color}")

    harvest_warnings, harvest_failures = _check_last_harvest()
    warnings.extend(harvest_warnings)
    failures.extend(harvest_failures)

    status = "pass" if not failures else "fail"
    duration = round(time.monotonic() - t0, 2)
    report = {
        "kind": "pack",
        "status": status,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "passed": 1 if status == "pass" else 0,
        "skipped": 0,
        "total": 1,
        "workers": 1,
        "duration_seconds": duration,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "smoke_runner.py",
        "returncode": 0 if status == "pass" else 1,
        "pack_validation": "GO" if pack_ok else "KO",
        "health_score": health_score,
        "health_color": health_color,
        "warnings": warnings,
        "failures": failures,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def run_integration_smoke(extra_args: list[str] | None = None) -> dict:
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(TESTS_TOOL)] + (extra_args or []),
        capture_output=True,
        text=True,
        cwd=str(PACK_PARENT),
    )
    duration = round(time.monotonic() - t0, 2)
    passed, failed, skipped = _parse_result_line(result.stdout)
    total = passed + failed + skipped
    status = "pass" if (result.returncode == 0 and failed == 0) else "fail"
    report = {
        "kind": "integration",
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
    kind = data.get("kind", "pack")
    print(f"  {icon} smoke[{kind}]: {data.get('status')} · "
          f"passed={data.get('passed','?')} · "
          f"failed={data.get('failure_count','?')} · "
          f"warnings={data.get('warning_count','?')} · "
          f"duration={data.get('duration_seconds','?')}s · "
          f"at={data.get('generated_at','?')[:19]}")
    return 0


def run_self_tests() -> int:
    passed = 0
    failures: list[str] = []

    sample = "  Resultado: 122/122 passed  0 failed  0 skipped"
    p, f, s = _parse_result_line(sample)
    if p == 122 and f == 0 and s == 0:
        passed += 1
    else:
        failures.append(f"parse_result_line: got p={p} f={f} s={s}, expected 122/0/0")

    sample_health = _parse_health_score("100 green")
    if sample_health == (100, "green"):
        passed += 1
    else:
        failures.append(f"parse_health_score: got {sample_health!r}")

    dummy = {
        "kind": "pack",
        "status": "pass",
        "failure_count": 0,
        "warning_count": 0,
        "passed": 1,
        "skipped": 0,
        "total": 1,
        "workers": 1,
        "duration_seconds": 0.1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "smoke_runner.py",
        "returncode": 0,
    }
    if {"kind", "status", "failure_count", "warning_count"}.issubset(dummy):
        passed += 1
    else:
        failures.append("report missing required keys")

    total = 3
    print(f"smoke_runner self-tests: {passed}/{total} tests pasaron")
    for item in failures:
        print(f"  FAIL: {item}")
    return 0 if passed == total else 1


def main() -> int:
    args = sys.argv[1:]
    if "--test" in args:
        return run_self_tests()
    if "--last" in args:
        return show_last()
    if "--integration" in args:
        extra_args = [a for a in args if a not in {"--integration"}]
        report = run_integration_smoke(extra_args)
    else:
        report = run_pack_smoke()

    icon = "✅" if report["status"] == "pass" else "❌"
    kind = report.get("kind", "pack")
    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Smoke Runner                                     │")
    print("  └──────────────────────────────────────────────────────────┘")
    print(f"  {icon} smoke[{kind}]: {report['status']} · "
          f"passed={report.get('passed', 0)} · "
          f"failed={report['failure_count']} · "
          f"warnings={report.get('warning_count', 0)} · "
          f"duration={report['duration_seconds']}s")
    if kind == "pack":
        print(f"  Pack: {report.get('pack_validation', '?')} · "
              f"health={report.get('health_score', '?')} {report.get('health_color', '')}".rstrip())
        if report.get("warnings"):
            print(f"  Avisos: {len(report['warnings'])}")
    print(f"  Reporte: {REPORT}")
    print()
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
