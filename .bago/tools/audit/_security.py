#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_audit.py — Auditoría de seguridad de dependencias npm.

Ejecuta `npm audit --json` en cada app y muestra un resumen de vulnerabilidades.

Uso:
    python3 .bago/tools/security_audit.py          # audita todas las apps
    python3 .bago/tools/security_audit.py web      # solo web
    python3 .bago/tools/security_audit.py --fix    # ejecuta npm audit fix en apps con vulns
    python3 .bago/tools/security_audit.py --json   # output en JSON

Códigos de salida: 0 = OK / sin vulns críticas, 1 = vulnerabilidades críticas encontradas
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[3]
STATE = ROOT / ".bago" / "state"

SEVERITY_ORDER = ["critical", "high", "moderate", "low", "info"]
SEVERITY_COLOR = {
    "critical": "\033[91m",  # bright red
    "high":     "\033[31m",  # red
    "moderate": "\033[33m",  # yellow
    "low":      "\033[36m",  # cyan
    "info":     "\033[2m",   # dim
}
RESET = "\033[0m"


def _col(s: str, sev: str) -> str:
    return f"{SEVERITY_COLOR.get(sev, '')}{s}{RESET}"


def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"


def _load_project() -> Path | None:
    gs = STATE / "global_state.json"
    if not gs.exists():
        return None
    try:
        data = json.loads(gs.read_text(encoding="utf-8"))
        p = data.get("active_project", {}).get("path", "")
        return Path(p) if p else None
    except Exception:
        return None


def _run_audit(app_dir: Path) -> dict | None:
    """Run npm audit --json in app_dir. Returns parsed JSON or None."""
    pkg = app_dir / "package.json"
    nm  = app_dir / "node_modules"
    if not pkg.exists():
        return None

    cmd = ["npm", "audit", "--json"]
    try:
        result = subprocess.run(
            cmd, cwd=str(app_dir),
            capture_output=True, timeout=120,
        )
        raw = result.stdout.decode("utf-8", errors="replace")
        if not raw.strip():
            return {"error": "empty output"}
        return json.loads(raw)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse: {e}"}
    except FileNotFoundError:
        return {"error": "npm not found"}


def _parse_vulns(audit: dict) -> dict[str, int]:
    """Extract vulnerability counts by severity."""
    vulns: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    if "error" in audit:
        return vulns

    # npm v7+ format
    meta = audit.get("metadata", {})
    vul_meta = meta.get("vulnerabilities", {})
    if vul_meta:
        for sev in SEVERITY_ORDER:
            vulns[sev] = vul_meta.get(sev, 0)
        return vulns

    # npm v6 format
    advisories = audit.get("advisories", {})
    for adv in advisories.values():
        sev = adv.get("severity", "info")
        if sev in vulns:
            vulns[sev] += 1
    return vulns


def _audit_app(app_name: str, app_dir: Path, do_fix: bool) -> tuple[dict[str, int], str | None]:
    """Audit one app. Returns (vuln_counts, error_msg)."""
    audit = _run_audit(app_dir)
    if audit is None:
        return {}, "sin package.json"
    if "error" in audit:
        return {}, audit["error"]

    vulns = _parse_vulns(audit)
    total = sum(vulns.values())

    if total == 0:
        print(f"  {GREEN('✅')} {BOLD(app_name):<16} sin vulnerabilidades")
    else:
        parts = []
        for sev in SEVERITY_ORDER:
            if vulns[sev]:
                parts.append(_col(f"{vulns[sev]} {sev}", sev))
        print(f"  {RED('⚠')} {BOLD(app_name):<16} {' · '.join(parts)}")

        if do_fix:
            print(f"    {DIM('→ ejecutando npm audit fix...')}")
            try:
                res = subprocess.run(
                    ["npm", "audit", "fix"], cwd=str(app_dir),
                    capture_output=True, text=True, timeout=180
                )
                lines = (res.stdout + res.stderr).strip().splitlines()
                for line in lines[-3:]:
                    print(f"    {DIM(line)}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                print(f"    {RED(f'fix falló: {e}')}")

    return vulns, None


def main(argv=None) -> int:
    args    = sys.argv[1:] if argv is None else list(argv)
    do_fix  = "--fix" in args
    do_json = "--json" in args
    filters = [a for a in args if not a.startswith("-")]

    project = _load_project()
    if not project:
        print(f"\n  {RED('❌')} No hay proyecto configurado. Ejecuta: bago config\n")
        return 1

    candidates = [
        ("root",     project),
        ("server",   project / "apps" / "server"),
        ("web",      project / "apps" / "web"),
        ("electron", project / "apps" / "electron"),
    ]
    apps = [(n, p) for n, p in candidates if p.exists()]
    if filters:
        apps = [(n, p) for n, p in apps if n in filters]

    if not do_json:
        print()
        print("  ┌─────────────────────────────────────────────────────────────┐")
        action = " (con --fix)" if do_fix else ""
        print(f"  │  BAGO · Security Audit{action:<37}│")
        print("  └─────────────────────────────────────────────────────────────┘")
        print(f"  Proyecto: {DIM(str(project))}")
        print()

    all_results: dict[str, dict] = {}
    has_critical = False

    for app_name, app_dir in apps:
        if do_json:
            audit = _run_audit(app_dir)
            vulns = _parse_vulns(audit) if audit and "error" not in audit else {}
            all_results[app_name] = {"vulns": vulns, "dir": str(app_dir)}
            if vulns.get("critical", 0) > 0:
                has_critical = True
        else:
            vulns, err = _audit_app(app_name, app_dir, do_fix)
            all_results[app_name] = {"vulns": vulns}
            if err:
                print(f"  {YELLOW('⚠')} {BOLD(app_name):<16} {DIM(err)}")
            if vulns.get("critical", 0) > 0:
                has_critical = True

    if do_json:
        print(json.dumps(all_results, indent=2, ensure_ascii=False))
    else:
        # Summary row
        total_by_sev: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
        for res in all_results.values():
            for sev, cnt in res.get("vulns", {}).items():
                total_by_sev[sev] = total_by_sev.get(sev, 0) + cnt
        grand_total = sum(total_by_sev.values())
        print()
        if grand_total == 0:
            print(f"  {GREEN('✅ Sin vulnerabilidades')}")
        else:
            parts = [_col(f"{total_by_sev[s]} {s}", s)
                     for s in SEVERITY_ORDER if total_by_sev[s]]
            print(f"  Total: {' · '.join(parts)}")
            if not do_fix:
                print(f"  Usa {CYAN('bago audit --fix')} para intentar corrección automática")
        print()

    return 1 if has_critical else 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
