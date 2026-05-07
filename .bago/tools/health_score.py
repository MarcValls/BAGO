#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
health_score.py — Score único de salud y valor del pack BAGO.

Calcula un score 0-100 compuesto de 5 dimensiones:
  Integridad          (25 pts): validate_pack GO = 25, KO = 0
  Disciplina workflow (20 pts): roles_medios_últimas_10 ≤ 2.0 → 20, hasta 5.0 → proporcional
  Captura decisiones  (20 pts): decisiones/sesión últimas 10 ≥ 2.0 → 20, proporcional
  Estado stale        (15 pts): stale_detector sin ERRORs = 15, cada ERROR = -5
  Consistencia inv.   (20 pts): reconcile_state sin diff = 20, diff = 0

Uso:
  python3 .bago/tools/health_score.py            # output completo
  python3 .bago/tools/health_score.py --score-only   # solo número (para otros scripts)
"""

from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
TOOLS = ROOT / "tools"


def run_script(script: str, args: list = None) -> tuple[int, str]:
    cmd = [sys.executable, str(TOOLS / script)] + (args or [])
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30, cwd=ROOT.parent,
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f"ERROR: {e}"


def score_integridad() -> tuple[int, int, str]:
    """validate_pack GO = 25, KO = 0."""
    rc, out = run_script("validate_pack.py")
    if rc == 0 and "GO pack" in out:
        return 25, 25, "GO pack ✅"
    # Extraer mensaje de error
    lines = out.splitlines()
    detail = lines[-1] if lines else "KO"
    return 0, 25, f"KO — {detail}"


def _detect_w10_desync() -> tuple[bool, str]:
    """W10 sincerity check: detecta desync task-done vs flow-activo.

    Si pending_w2_task.json marca status='done' Y hay active_workflow != null
    en global_state.sprint_status, es indisciplina de workflow:
    la task quedó cerrada pero el flow no se cerró / no se limpió la task pending.

    # COSECHA_W10_DESYNC_DETECTOR

    Retorna: (desync_present: bool, detail: str)
    """
    pending_path = STATE / "pending_w2_task.json"
    state_path   = STATE / "global_state.json"
    if not pending_path.exists() or not state_path.exists():
        return False, ""
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        gstate  = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return False, ""
    task_status = (pending.get("status") or "").lower()
    sprint_status = gstate.get("sprint_status") or {}
    active = sprint_status.get("active_workflow")
    # active puede ser None, string "none…" o dict {code,title,started}
    has_active = bool(active) and isinstance(active, dict) and active.get("code")
    if task_status == "done" and has_active:
        title = pending.get("idea_title", "?")[:30]
        wf_code = active.get("code", "?")
        return True, f"⚠  desync W10: task done='{title}' ↔ flow activo {wf_code}"
    return False, ""


def score_disciplina_workflow() -> tuple[int, int, str]:
    """roles_medios_últimas_10 ≤ 2.0 → 20, hasta 5.0 → proporcional, >5.0 → 0.
    Penalización -5 si W10 detecta desync task-done ↔ flow-activo.
    # COSECHA_W10_DESYNC_DETECTOR
    """
    sessions_dir = STATE / "sessions"
    if not sessions_dir.exists():
        return 10, 20, "Sin datos (asumido 10/20)"

    sessions = []
    for f in sessions_dir.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("status") == "closed":
                sessions.append(s)
        except Exception:
            pass

    if not sessions:
        return 10, 20, "Sin sesiones cerradas (asumido 10/20)"

    def sort_key(s):
        return s.get("closed_at") or s.get("created_at") or ""
    sessions.sort(key=sort_key)
    recent = sessions[-10:]

    role_counts = []
    for s in recent:
        roles = s.get("roles_activated", s.get("roles", []))
        if isinstance(roles, list):
            role_counts.append(len(roles))
        else:
            role_counts.append(1)

    avg = sum(role_counts) / len(role_counts) if role_counts else 3.0

    if avg <= 2.0:
        pts = 20
    elif avg >= 5.0:
        pts = 0
    else:
        # Lineal entre 2.0 y 5.0
        pts = int(20 * (5.0 - avg) / 3.0)

    detail = f"roles_medios={avg:.1f} (últimas {len(recent)} ses)"

    # W10 desync penalty
    desync, desync_detail = _detect_w10_desync()
    if desync:
        pts = max(0, pts - 5)
        detail = f"{detail}  —  {desync_detail}"

    return pts, 20, detail


def score_captura_decisiones() -> tuple[int, int, str]:
    """decisiones/sesión últimas 10 ≥ 2.0 → 20, proporcional, 0 decisiones → 0."""
    sessions_dir = STATE / "sessions"
    if not sessions_dir.exists():
        return 10, 20, "Sin datos (asumido 10/20)"

    sessions = []
    for f in sessions_dir.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("status") == "closed":
                sessions.append(s)
        except Exception:
            pass

    if not sessions:
        return 10, 20, "Sin sesiones cerradas (asumido 10/20)"

    def sort_key(s):
        return s.get("closed_at") or s.get("created_at") or ""
    sessions.sort(key=sort_key)
    recent = sessions[-10:]

    dec_counts = []
    for s in recent:
        decs = s.get("decisions", [])
        if isinstance(decs, list):
            dec_counts.append(len(decs))
        else:
            dec_counts.append(0)

    avg = sum(dec_counts) / len(dec_counts) if dec_counts else 0

    if avg >= 2.0:
        pts = 20
    elif avg <= 0:
        pts = 0
    else:
        pts = int(20 * avg / 2.0)

    return pts, 20, f"decisiones_medias={avg:.1f} (últimas {len(recent)} ses)"


def score_estado_stale() -> tuple[int, int, str]:
    """stale_detector sin ERRORs = 15, cada ERROR = -5."""
    rc, out = run_script("stale_detector.py")
    if rc == 0 and "✅ Reporting limpio" in out:
        return 15, 15, "Reporting limpio ✅"

    # Contar ERRORs
    error_count = out.count("[ERROR]")
    warn_count = out.count("[WARN]")
    pts = max(0, 15 - error_count * 5)

    if error_count > 0:
        detail = f"{error_count} ERROR(s), {warn_count} WARN(s)"
    else:
        detail = f"{warn_count} WARN(s) (sin ERRORs)"
    return pts, 15, detail


def score_consistencia_inventario() -> tuple[int, int, str]:
    """reconcile_state sin diff = 20, con diff = 0."""
    rc, out = run_script("reconcile_state.py")
    if rc == 0:
        return 20, 20, "Inventario reconciliado ✅"
    # Hay diffs
    first = out.split("\n")[0] if out else "diff detectado"
    return 0, 20, f"Diff detectado — {first}"


def _count_session_closes() -> int:
    """Número de sesiones cerradas registradas en global_state (session_close_*.md)."""
    # # HEALTH_SCORE_REAL_IMPLEMENTED — sentinel para feature detector (session_closes)
    try:
        gs = json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
        return int(gs.get("inventory", {}).get("session_closes", 0))
    except Exception:
        return 0


def _has_closed_json_sessions() -> bool:
    """True solo si existen sesiones JSON cerradas en state/sessions/."""
    sessions_dir = STATE / "sessions"
    if not sessions_dir.exists():
        return False
    for f in sessions_dir.glob("*.json"):
        try:
            if f.stat().st_size > 0 and json.loads(f.read_text(encoding="utf-8")).get("status") == "closed":
                return True
        except Exception:
            pass
    return False


def _has_closed_sessions() -> bool:
    """True si hay historial real de uso: sesiones JSON cerradas o session_closes > 0."""
    return _has_closed_json_sessions() or _count_session_closes() > 0


def main():
    score_only = "--score-only" in sys.argv

    # Clean install: no closed sessions yet — report initializing state
    if not _has_closed_sessions() and not score_only:
        rc, _ = run_script("validate_pack.py")
        pack_ok = rc == 0
        print()
        print("BAGO Health: initializing  ⚪")
        print()
        print("  No closed sessions yet — score dimensions require real usage history.")
        print(f"  Pack integrity:  {'✅ GO' if pack_ok else '❌ KO'}")
        print()
        print("  Run a session and close it with `python3 bago cosecha`")
        print("  to start building a meaningful health score.")
        print()
        return 0

    # Sin sesiones pero --score-only: calcular parcialmente sin salir antes
    if not _has_closed_sessions() and score_only:
        rc, _ = run_script("validate_pack.py")
        pack_ok = rc == 0
        partial = 25 if pack_ok else 0
        color = "green" if partial >= 80 else ("yellow" if partial >= 50 else "red")
        print(f"{partial} {color}")
        return 0

    has_json_sessions = _has_closed_json_sessions()
    session_closes = _count_session_closes()

    dimensions = [
        ("Integridad",          score_integridad),
        ("Disciplina workflow", score_disciplina_workflow),
        ("Captura decisiones",  score_captura_decisiones),
        ("Estado stale",        score_estado_stale),
        ("Consistencia inv.",   score_consistencia_inventario),
    ]

    results = []
    for name, fn in dimensions:
        pts, max_pts, detail = fn()
        results.append((name, pts, max_pts, detail))

    total = sum(r[1] for r in results)
    max_total = sum(r[2] for r in results)

    if score_only:
        color = "green" if total >= 80 else ("yellow" if total >= 50 else "red")
        print(f"{total} {color}")
        return 0

    # Semáforo
    if total >= 80:
        semaforo = "🟢"
    elif total >= 50:
        semaforo = "🟡"
    else:
        semaforo = "🔴"

    print()
    print(f"BAGO Health Score: {total}/{max_total}  {semaforo}")
    print()
    if not has_json_sessions and session_closes > 0:
        print(f"  ℹ️  Score parcial: {session_closes} sesión(es) en historial (sin JSON detallado)")
        print(f"     Disciplina y Decisiones son valores asumidos — cierra sesiones con `bago cosecha`")
        print()
    for name, pts, max_pts, detail in results:
        pct = pts / max_pts if max_pts else 0
        icon = "✅" if pct >= 0.8 else ("⚠️ " if pct >= 0.4 else "❌")
        print(f"  {icon}  {name:<22} {pts:>3}/{max_pts:<3}  {detail}")
    print()

    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    # — W10 desync detector tests (puros, sin disco) —
    import tempfile
    fails: list[str] = []
    global STATE
    saved_STATE = STATE
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = _P(td)
            STATE = tmp  # monkeypatch módulo-local
            # Caso 1: sin ficheros → no desync
            d, _ = _detect_w10_desync()
            if d is not False:
                fails.append("sin ficheros: debería ser False")
            # Caso 2: task done + active_workflow dict → desync True
            (tmp / "pending_w2_task.json").write_text(json.dumps({
                "status": "done", "idea_title": "X"}))
            (tmp / "global_state.json").write_text(json.dumps({
                "sprint_status": {"active_workflow": {"code": "W2", "title": "t"}}}))
            d, msg = _detect_w10_desync()
            if not d:
                fails.append("task=done + active=W2: debería ser True")
            if "desync W10" not in msg:
                fails.append(f"mensaje sin marcador 'desync W10': {msg!r}")
            # Caso 3: task done pero active_workflow null → NO desync
            (tmp / "global_state.json").write_text(json.dumps({
                "sprint_status": {"active_workflow": None}}))
            d, _ = _detect_w10_desync()
            if d is not False:
                fails.append("task=done + active=None: debería ser False")
            # Caso 4: active_workflow es string (legado) → NO desync (no es dict válido)
            (tmp / "global_state.json").write_text(json.dumps({
                "sprint_status": {"active_workflow": "none — nada activo"}}))
            d, _ = _detect_w10_desync()
            if d is not False:
                fails.append("active=string: debería ser False")
            # Caso 5: task pending (status != done) + active dict → NO desync
            (tmp / "pending_w2_task.json").write_text(json.dumps({
                "status": "pending", "idea_title": "X"}))
            (tmp / "global_state.json").write_text(json.dumps({
                "sprint_status": {"active_workflow": {"code": "W2"}}}))
            d, _ = _detect_w10_desync()
            if d is not False:
                fails.append("task=pending + active=W2: debería ser False")
    finally:
        STATE = saved_STATE
    if fails:
        for f in fails:
            print("  FAIL:", f)
        print(f"FAIL: {len(fails)}/5 W10 desync tests")
        raise SystemExit(1)
    print("  1/1 base + 5/5 W10 desync detector tests pasaron")
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())
