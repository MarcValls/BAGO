"""Gate compacto para cerrar una release de BAGO con evidencia local."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[2]


def _run(label: str, command: list[str], cwd: Path, checks: list[dict]) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=900)
        checks.append({"check": label, "status": "PASS" if result.returncode == 0 else "FAIL", "detail": (result.stdout + result.stderr)[-500:]})
    except Exception as exc:
        checks.append({"check": label, "status": "FAIL", "detail": str(exc)})


def cmd_release_check(args: argparse.Namespace) -> int:
    checks: list[dict] = []
    if not getattr(args, "skip_tests", False):
        _run("backend tests", [sys.executable, "-m", "pytest", "-q"], BAGO_ROOT, checks)
        frontend = BAGO_ROOT.parent / "frontend"
        if (frontend / "package.json").exists():
            _run("frontend tests", ["npm", "test", "--", "--run"], frontend, checks)
            _run("frontend typecheck", ["npm", "run", "typecheck"], frontend, checks)
    release = (BAGO_ROOT / "release_version.txt").read_text(encoding="utf-8").strip()
    version = release.lstrip("vV")
    installer_candidates = [
        BAGO_ROOT / "dist" / f"BAGO-Installation-Manager-{version}-win-x64.exe",
        BAGO_ROOT.parent / "backend" / "dist" / f"BAGO-Installation-Manager-{version}-win-x64.exe",
    ]
    installer = next((path for path in installer_candidates if path.is_file()), None)
    checks.append({"check": "release version", "status": "PASS" if release else "FAIL", "detail": release})
    checks.append({"check": "installer", "status": "PASS" if installer and installer.stat().st_size > 0 else "WARN", "detail": str(installer or installer_candidates[0]) + (" (no incluido en runtime)" if not installer else "")})
    ui_candidates = [BAGO_ROOT.parent / "frontend" / "dist" / "index.html", BAGO_ROOT / "ui-react" / "dist" / "index.html"]
    ui = next((path for path in ui_candidates if path.is_file()), ui_candidates[0])
    checks.append({"check": "frontend artifact", "status": "PASS" if ui.is_file() else "FAIL", "detail": str(ui)})
    if not getattr(args, "skip_tests", False):
        _run("doctor", [sys.executable, "bago_core/cli.py", "doctor", "--json"], BAGO_ROOT, checks)
        _run("validate", [sys.executable, "bago_core/cli.py", "validate"], BAGO_ROOT, checks)
    failed = [item for item in checks if item["status"] == "FAIL"]
    if getattr(args, "json", False):
        print(json.dumps({"ok": not failed, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print("\nBAGO RELEASE CHECK")
        for item in checks:
            print(f"  [{'✓' if item['status'] == 'PASS' else '✗'}] {item['check']} — {item['detail']}")
        print(f"Resultado: {'PASS' if not failed else 'FAIL'}")
    return 0 if not failed else 1
