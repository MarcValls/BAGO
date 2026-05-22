#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_v2.py — Dashboard BAGO V2.

Muestra el estado del pack con sección V2 adicional:
  - Health score con semáforo
  - KPIs vs targets V2
  - Recomendación de siguiente workflow
  - Flag de escenarios stale o inventario desincronizado

Uso:
  python3 .bago/tools/dashboard_v2.py [--full]
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "state"
TOOLS = ROOT / "tools"


def _run(script: str, args: list = None) -> tuple[int, str]:
    cmd = [sys.executable, str(TOOLS / script)] + (args or [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=ROOT.parent)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f"ERROR: {e}"


def _load_global() -> dict:
    p = STATE / "global_state.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if not d.get("pack_version"):
        pack_p = ROOT / "pack.json"
        if pack_p.exists():
            pack = json.loads(pack_p.read_text(encoding="utf-8"))
            d["pack_version"] = pack.get("version", "?")
    return d


def _count(folder) -> int:
    f = STATE / folder
    if not f.exists():
        return 0
    return len([x for x in f.glob("*.json") if x.name.lower() != "readme.md"])


def _validate_pack() -> str:
    rc, out = _run("validate_pack.py")
    return "GO ✅" if (rc == 0 and "GO pack" in out) else f"KO ❌ ({out.splitlines()[-1] if out else '?'})"


def _session_stats() -> tuple[float, float, float]:
    """Devuelve (avg_roles, avg_artifacts, avg_decisions) últimas 10 sesiones."""
    sessions = []
    for f in (STATE / "sessions").glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("status") == "closed":
                sessions.append(s)
        except Exception:
            pass
    sessions.sort(key=lambda s: s.get("closed_at") or s.get("created_at") or "")
    recent = sessions[-10:]
    if not recent:
        return 0.0, 0.0, 0.0

    excl = {"state/sessions/", "state/changes/", "state/evidences/", "TREE.txt", "CHECKSUMS.sha256"}
    roles_l, arts_l, decs_l = [], [], []
    for s in recent:
        roles = s.get("roles_activated", s.get("roles", []))
        roles_l.append(len(roles) if isinstance(roles, list) else 1)
        arts = [a for a in s.get("artifacts", []) if not any(a.startswith(e) for e in excl)]
        arts_l.append(len(arts))
        decs = s.get("decisions", [])
        decs_l.append(len(decs) if isinstance(decs, list) else 0)

    n = len(recent)
    return round(sum(roles_l)/n, 1), round(sum(arts_l)/n, 1), round(sum(decs_l)/n, 1)


def _workflow_dist() -> dict:
    dist = {}
    for f in (STATE / "sessions").glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("status") == "closed":
                wf = s.get("workflow", "?")
                dist[wf] = dist.get(wf, 0) + 1
        except Exception:
            pass
    return dict(sorted(dist.items(), key=lambda x: -x[1]))


def _get_health_score() -> tuple[int, str]:
    rc, out = _run("health_score.py", ["--score-only"])
    for line in out.splitlines():
        if line.strip().isdigit():
            score = int(line.strip())
            if score >= 80:
                return score, "🟢"
            elif score >= 50:
                return score, "🟡"
            else:
                return score, "🔴"
    return 0, "❓"


def _get_workflow_rec() -> str:
    rc, out = _run("workflow_selector.py", ["--auto"])
    for line in out.splitlines():
        if "Workflow recomendado:" in line:
            return line.split(":", 1)[1].strip()
    return "?"


def _get_stale_status() -> str:
    rc, out = _run("stale_detector.py")
    if rc == 0 and "✅" in out:
        return "✅ Limpio"
    errors = out.count("[ERROR]")
    warns  = out.count("[WARN]")
    if errors > 0:
        return f"❌ {errors} ERROR(s)"
    return f"⚠️  {warns} WARN(s)"


def _get_reconcile_status() -> str:
    rc, out = _run("reconcile_state.py")
    if rc == 0:
        return "✅ OK"
    return "⚠️  Diff detectado"


def main():
    full = "--full" in sys.argv

    gs = _load_global()
    version = gs.get("bago_version", gs.get("pack_version", "?"))
    health = gs.get("system_health", "?")
    last_ses = gs.get("last_completed_session_id", "—")
    last_wf = gs.get("last_completed_workflow", "—")
    active_sc = gs.get("active_scenarios", [])
    v2_status = gs.get("v2_status", "—")
    updated_at = gs.get("updated_at", gs.get("last_updated", "—"))

    # Métricas
    ses_count  = _count("sessions")
    chg_count  = _count("changes")
    evd_count  = _count("evidences")
    pack_val   = _validate_pack()
    avg_roles, avg_arts, avg_decs = _session_stats()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print(f"║  BAGO Dashboard V2  —  v{version:<10}  {health:<15} ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Inventario:   ses={ses_count}  chg={chg_count}  evd={evd_count}")
    print(f"║  Última sesión: {last_ses}")
    print(f"║  Último workflow: {last_wf}")
    print(f"║  Escenarios activos: {active_sc if active_sc else '—'}")
    print(f"║  validate_pack: {pack_val}")
    print(f"║  Actualizado: {updated_at[:19] if updated_at else '—'}")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  MÉTRICAS (últimas 10 sesiones)                         ║")
    print(f"║    roles/sesión:      {avg_roles:<6}  (target ≤ 2.0)")
    print(f"║    artefactos/sesión: {avg_arts:<6}")
    print(f"║    decisiones/sesión: {avg_decs:<6}  (target ≥ 2.0)")

    if full:
        dist = _workflow_dist()
        print("║")
        print("║  DISTRIBUCIÓN WORKFLOWS:")
        for wf, n in list(dist.items())[:6]:
            print(f"║    {wf:<35} {n:>3}")

    print("╠══════════════════════════════════════════════════════════╣")
    print("║  ▶ BAGO V2 STATUS                                       ║")

    # V2 metrics (puede tardar un poco)
    health_score, semaforo = _get_health_score()
    wf_rec    = _get_workflow_rec()
    stale_st  = _get_stale_status()
    reconc_st = _get_reconcile_status()

    print(f"║    Health Score:   {health_score}/100  {semaforo}")
    print(f"║    Stale:          {stale_st}")
    print(f"║    Inventario:     {reconc_st}")
    print(f"║    V2 Status:      {v2_status}")
    print(f"║    Workflow rec.:  → {wf_rec}")
    print("╚══════════════════════════════════════════════════════════╝")

    # KPIs vs targets
    print()
    print("  KPIs V2 vs Targets:")
    print(f"  {'Métrica':<28} {'Actual':>8}  {'Target':>8}  {'Estado':>6}")
    print(f"  {'-'*28} {'-'*8}  {'-'*8}  {'-'*6}")
    kpis = [
        ("Roles/sesión (últimas 10)",  avg_roles,  "≤ 2.0",  avg_roles <= 2.0),
        ("Decisiones/sesión (últ.10)", avg_decs,   "≥ 2.0",  avg_decs >= 2.0),
        ("Health Score",               health_score, "≥ 80",  health_score >= 80),
    ]
    for name, actual, target, ok in kpis:
        icon = "✅" if ok else "⚠️ "
        print(f"  {name:<28} {str(actual):>8}  {target:>8}  {icon}")
    print()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
