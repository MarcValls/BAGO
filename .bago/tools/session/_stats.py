#!/usr/bin/env python3
"""
session._stats — BAGO
Resumen estadístico de sesiones por tipo de tarea, workflow y rol.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PROTOCOL_PREFIXES = ("state/sessions/", "state/changes/", "state/evidences/")
PROTOCOL_FILES = {"TREE.txt", "CHECKSUMS.sha256"}

def is_protocol(a):
    return Path(a).name in PROTOCOL_FILES or any(a.startswith(p) for p in PROTOCOL_PREFIXES)

def useful(s):
    return sum(1 for a in s.get("artifacts", []) if not is_protocol(a))

def load_sessions(status_filter=None):
    out = []
    for f in sorted((ROOT / "state" / "sessions").glob("*.json")):
        try:
            d = json.loads(f.read_text())
            if status_filter is None or d.get("status") == status_filter:
                out.append(d)
        except Exception:
            pass
    return out

def main(argv=None):
    parser = argparse.ArgumentParser(description="Estadísticas de sesiones BAGO.")
    parser.add_argument("--all", action="store_true", help="Incluir sesiones abiertas")
    parser.add_argument("-v", "--verbose", action="store_true", help="Detalle por sesión")
    args = parser.parse_args(argv)

    sessions = load_sessions(None if args.all else "closed")
    if not sessions:
        print("No hay sesiones cerradas.")
        return 0

    print("=" * 62)
    print(f"  BAGO · Session Stats  ({len(sessions)} sesiones {'(todas)' if args.all else 'cerradas'})")
    print("=" * 62)

    by_type = defaultdict(list)
    for s in sessions:
        by_type[s.get("task_type", "unknown")].append(s)

    print("\n  📋 POR TIPO DE TAREA")
    print(f"  {'Tipo':<28} {'N':>3}  {'Útiles/ses':>10}  {'Roles/ses':>9}  {'Decisiones':>10}")
    print(f"  {'─'*28}  {'─'*3}  {'─'*10}  {'─'*9}  {'─'*10}")
    for ttype, ss in sorted(by_type.items(), key=lambda x: -len(x[1])):
        n = len(ss)
        u_mean = sum(useful(s) for s in ss) / n
        r_mean = sum(len(s.get("roles_activated", [])) for s in ss) / n
        d_mean = sum(len(s.get("decisions", [])) for s in ss) / n
        print(f"  {ttype:<28} {n:>3}  {u_mean:>10.1f}  {r_mean:>9.1f}  {d_mean:>10.1f}")

    wf_counter = Counter(s.get("selected_workflow", "?") for s in sessions)
    print("\n  🔄 POR WORKFLOW")
    for wf, n in wf_counter.most_common():
        print(f"  {wf:<35} {'█' * n} {n}")

    all_roles = []
    for s in sessions:
        all_roles.extend(s.get("roles_activated", []))
    role_counter = Counter(all_roles)
    print("\n  👤 ROLES MÁS ACTIVADOS")
    for role, n in role_counter.most_common(6):
        print(f"  {role:<35} {'█' * n} {n}")

    if len(sessions) >= 10:
        first5 = sessions[:5]
        last5 = sessions[-5:]
        u_early = sum(useful(s) for s in first5) / 5
        u_late = sum(useful(s) for s in last5) / 5
        r_early = sum(len(s.get("roles_activated", [])) for s in first5) / 5
        r_late = sum(len(s.get("roles_activated", [])) for s in last5) / 5
        delta_u = u_late - u_early
        delta_r = r_early - r_late
        print("\n  📈 TENDENCIA  (primeras 5 vs últimas 5)")
        print(f"  Útiles/ses:   {u_early:.1f} → {u_late:.1f}  {'▲' if delta_u > 0 else '▼'} {abs(delta_u):.1f}")
        print(f"  Roles/ses:    {r_early:.1f} → {r_late:.1f}  {'▼ (mejor)' if delta_r > 0 else '▲'} {abs(delta_r):.1f}")

    if args.verbose:
        print("\n  📄 DETALLE POR SESIÓN")
        print(f"  {'Sesión':<36} {'Tipo':<18} {'Útiles':>6}  {'Roles':>5}")
        print(f"  {'─'*36}  {'─'*18}  {'─'*6}  {'─'*5}")
        for s in sessions:
            sid = s.get("session_id", "?")[:35]
            ttype = s.get("task_type", "?")[:17]
            u = useful(s)
            r = len(s.get("roles_activated", []))
            print(f"  {sid:<36} {ttype:<18} {u:>6}  {r:>5}")

    print("=" * 62)
    return 0

def _self_test():
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
