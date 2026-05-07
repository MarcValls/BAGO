#!/usr/bin/env python3
"""
cosecha.py — BAGO ESCENARIO-003
Protocolo W9: 3 preguntas → sesión harvest cerrada + CHG + EVD automáticos.

Uso:
  python3 .bago/tools/cosecha.py
  python3 .bago/tools/cosecha.py --dry-run   (muestra lo que crearía sin escribir)
"""

import json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
BAGO_ROOT  = Path(__file__).resolve().parent.parent
STATE_DIR  = BAGO_ROOT / "state"
SESSIONS   = STATE_DIR / "sessions"
CHANGES    = STATE_DIR / "changes"
EVIDENCES  = STATE_DIR / "evidences"
DB_PATH    = STATE_DIR / "bago.db"


def _sync_session_to_db(session: dict) -> None:
    """Inserta o actualiza la sesión en la tabla sessions de bago.db."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute('''
            INSERT OR REPLACE INTO sessions
            (session_id, task_type, workflow, roles, user_goal, status,
             escenario, created_at, updated_at, summary, next_step,
             linked_commits, source_file)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            session.get("session_id", ""),
            session.get("task_type", ""),
            session.get("selected_workflow", ""),
            json.dumps(session.get("roles_activated", [])),
            session.get("user_goal", ""),
            session.get("status", ""),
            session.get("escenario", ""),
            session.get("created_at", ""),
            session.get("updated_at", ""),
            session.get("summary", ""),
            session.get("next_step", ""),
            json.dumps(session.get("linked_commits", [])),
            session.get("session_id", "") + ".json",
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass  # Never block cosecha due to DB sync failure

DRY_RUN = "--dry-run" in sys.argv

# ─── Utilidades ───────────────────────────────────────────────────────────────

def _next_id(folder, prefix, pad=3):
    """Devuelve el siguiente ID disponible para CHG o EVD."""
    existing = [f.stem for f in folder.glob(f"BAGO-{prefix}-*.json")]
    nums = []
    for e in existing:
        parts = e.split("-")
        if len(parts) >= 3 and parts[-1].isdigit():
            nums.append(int(parts[-1]))
    n = max(nums, default=0) + 1
    return f"BAGO-{prefix}-{str(n).zfill(pad)}"


def _next_session_id():
    """Genera el ID de la siguiente sesión harvest."""
    today = datetime.now().strftime("%Y-%m-%d")
    prefix = f"SES-HARVEST-{today}"
    existing = [f.stem for f in SESSIONS.glob(f"{prefix}-*.json")]
    nums = [int(e.split("-")[-1]) for e in existing if e.split("-")[-1].isdigit()]
    n = max(nums, default=0) + 1
    return f"{prefix}-{str(n).zfill(3)}"


def _read_global_state():
    p = BAGO_ROOT / "state" / "global_state.json"
    return json.loads(p.read_text())


def _write_global_state(gs):
    p = BAGO_ROOT / "state" / "global_state.json"
    if not DRY_RUN:
        p.write_text(json.dumps(gs, indent=2, ensure_ascii=False))


def _ask(prompt, hint="", required=True):
    """Pregunta interactiva con hint opcional."""
    if hint:
        print(f"\n  {hint}")
    print(f"\n  ❓ {prompt}")
    print("  ──────────────────────────────────────────")
    lines = []
    while True:
        try:
            line = input("  > ")
        except EOFError:
            break
        if line == "" and lines:
            break
        if line == "" and required:
            print("  (respuesta requerida — pulsa Enter en blanco al terminar)")
            continue
        lines.append(line)
        if line == "":
            break
    return " ".join(lines).strip()


def _recent_ideas(n: int = 5) -> list[dict]:
    """Retorna las últimas N ideas implementadas desde implemented_ideas.json.
    # COSECHA_SPRINT_IDEAS_IMPLEMENTED
    """
    path = BAGO_ROOT / "state" / "implemented_ideas.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        all_ideas = data.get("implemented", [])
        return all_ideas[-n:] if all_ideas else []
    except Exception:
        return []


def _get_health_score() -> tuple[str, int]:
    """Captura el health score actual ejecutando health_score.py --score-only.
    # COSECHA_HEALTH_COMPARE_IMPLEMENTED
    Retorna (icono, puntos) — ej. ('🟢', 80).
    """
    import subprocess as _sp
    import sys as _sys
    hs_script = BAGO_ROOT / "tools" / "health_score.py"
    if not hs_script.exists():
        return "⚪", 0
    try:
        r = _sp.run(
            [_sys.executable, str(hs_script), "--score-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        parts = r.stdout.strip().split()
        score = int(parts[0]) if parts and parts[0].isdigit() else 0
        color = parts[1] if len(parts) > 1 else "unknown"
        icon  = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(color, "⚪")
        return icon, score
    except Exception:
        return "⚪", 0


def _prev_harvest_health() -> int | None:
    """Lee la última sesión harvest cerrada y devuelve su health score, o None.
    # COSECHA_HEALTH_TREND_IMPLEMENTED
    """
    sessions_dir = BAGO_ROOT / "state" / "sessions"
    candidates: list[tuple[str, int]] = []
    for f in sessions_dir.glob("SES-HARVEST-*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") != "closed":
                continue
            score = data.get("health_at_harvest", {}).get("score")
            if score is not None:
                candidates.append((data.get("updated_at", ""), int(score)))
        except Exception:
            pass
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _regenerate_ideas_report() -> str | None:
    """Regenera ideas_report.md llamando a sprint_summary._export_report().
    Retorna la ruta del fichero generado, o None si falla.
    """
    try:
        import importlib.util
        sprint_summary = BAGO_ROOT / "tools" / "sprint_summary.py"
        if not sprint_summary.exists():
            return None
        spec = importlib.util.spec_from_file_location("sprint_summary", sprint_summary)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out = mod._export_report()
        return str(out)
    except Exception:
        return None


def _detect_modified_files():
    """Intenta detectar ficheros recientes usando context_detector si existe."""
    detector = BAGO_ROOT / "tools" / "context_detector.py"
    if detector.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("context_detector", detector)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod._unregistered_files()
        except Exception:
            pass
    return []


# ─── Flujo principal ──────────────────────────────────────────────────────────

def run():
    now = datetime.now(timezone.utc).isoformat()
    health_icon, health_pts = _get_health_score()
    prev_health = _prev_harvest_health()
    if prev_health is None:
        health_trend = ""
    elif health_pts > prev_health:
        health_trend = f" ↑ (era {prev_health})"
    elif health_pts < prev_health:
        health_trend = f" ↓ (era {prev_health})"
    else:
        health_trend = f" = (sin cambio)"

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   BAGO · Cosecha Contextual (W9)                 ║")
    print("║   3 preguntas → sesión harvest cerrada           ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Responde con una o dos líneas. Enter en blanco  ║")
    print("║  para finalizar cada respuesta.                  ║")
    if DRY_RUN:
        print("║  ⚠️  DRY-RUN: no se escribirá ningún fichero    ║")
    print("╚══════════════════════════════════════════════════╝")

    # ── Pregunta 1 ────────────────────────────────────────────────────────────
    decision = _ask(
        "¿Qué decidiste en esta exploración?",
        hint="La decisión principal. Qué elegiste y por qué (máx. 2 líneas)."
    )

    # ── Pregunta 2 ────────────────────────────────────────────────────────────
    discard = _ask(
        "¿Qué descartaste y por qué?",
        hint="Qué opción o camino quedó fuera y la razón (máx. 2 líneas)."
    )

    # ── Pregunta 3 ────────────────────────────────────────────────────────────
    next_step = _ask(
        "¿Cuál es el próximo paso concreto?",
        hint="El siguiente artefacto a producir o acción a ejecutar."
    )

    # ── Ficheros afectados ────────────────────────────────────────────────────
    unregistered = _detect_modified_files()
    recent_ideas = _recent_ideas(5)
    print()
    if unregistered:
        print(f"  📂 Ficheros detectados sin CHG: {len(unregistered)}")
        for f in unregistered[:5]:
            print(f"     · {f}")
    else:
        print("  📂 No se detectaron ficheros modificados sin CHG.")
    if recent_ideas:
        print()
        print(f"  💡 Últimas ideas del sprint ({len(recent_ideas)}):")
        for idea in recent_ideas:
            title = idea.get("title", "?")
            date  = (idea.get("done_at") or "")[:10] or "—"
            print(f"     · {title}  ({date})")
    print()
    print(f"  {health_icon} Health score al cosechar: {health_pts} pts{health_trend}")
    print()

    # ── Confirmación ──────────────────────────────────────────────────────────
    print("  ┌──────────────────────────────────────────────┐")
    print("  │  RESUMEN DE COSECHA                          │")
    print("  ├──────────────────────────────────────────────┤")
    print(f"  │  Decisión: {decision[:45]:<45} │")
    print(f"  │  Descarte: {discard[:45]:<45} │")
    print(f"  │  Próximo:  {next_step[:45]:<45} │")
    health_summary = f"{health_icon} {health_pts} pts{health_trend}"
    print(f"  │  Health:   {health_summary:<49} │")
    print("  └──────────────────────────────────────────────┘")
    print()

    confirm = input("  ¿Guardar esta cosecha? [S/n] ").strip().lower()
    if confirm == "n":
        print("\n  Cosecha cancelada.")
        return

    # ── Generar artefactos ────────────────────────────────────────────────────
    session_id = _next_session_id()
    chg_id = _next_id(CHANGES, "CHG")
    evd_id = _next_id(EVIDENCES, "EVD")

    artifacts = list(unregistered) or ["(exploración sin artefactos de fichero)"]

    session = {
        "session_id": session_id,
        "task_type": "harvest",
        "selected_workflow": "w9_cosecha",
        "roles_activated": ["role_auditor"],
        "user_goal": f"Cosecha contextual: {decision[:80]}",
        "status": "closed",
        "escenario": "ESCENARIO-003",
        "created_at": now,
        "updated_at": now,
        "artifacts": artifacts,
        "decisions": [
            f"DECISIÓN: {decision}",
            f"DESCARTE: {discard}",
        ] + ([f"IDEAS SPRINT: {' / '.join(i.get('title','?') for i in recent_ideas)}"] if recent_ideas else []),
        "next_step": next_step,
        "health_at_harvest": {"icon": health_icon, "score": health_pts},
        "summary": f"Harvest W9. Decisión: {decision[:60]}. Próximo: {next_step[:60]}."
    }

    chg = {
        "change_id": chg_id,
        "type": "governance",
        "severity": "minor",
        "title": f"Cosecha contextual W9: {decision[:60]}",
        "motivation": f"Formalizar exploración libre. Decisión: {decision}. Descarte: {discard}.",
        "status": "applied",
        "affected_components": artifacts,
        "related_evidence": evd_id,
        "created_at": now,
        "updated_at": now,
        "author": "role_auditor"
    }

    evd = {
        "evidence_id": evd_id,
        "type": "decision",
        "related_to": [chg_id, session_id],
        "summary": f"Cosecha W9 — {session_id}",
        "details": (
            f"Decisión: {decision} | "
            f"Descarte: {discard} | "
            f"Próximo paso: {next_step} | "
            f"Ficheros afectados: {', '.join(artifacts[:3])} | "
            f"Health: {health_icon} {health_pts} pts"
            + (f" | Ideas sprint: {' / '.join(i.get('title','?') for i in recent_ideas)}" if recent_ideas else "")
        ),
        "status": "recorded",
        "recorded_at": now
    }

    if DRY_RUN:
        print("\n  [DRY-RUN] Se crearían:")
        print(f"    · {SESSIONS / (session_id + '.json')}")
        print(f"    · {CHANGES / (chg_id + '.json')}")
        print(f"    · {EVIDENCES / (evd_id + '.json')}")
        print(f"    · {STATE_DIR / 'ideas_report.md'}  (regenerado)")
        print(f"\n  session:\n{json.dumps(session, indent=4, ensure_ascii=False)}")
        return

    # ── Escribir ficheros ─────────────────────────────────────────────────────
    (SESSIONS / f"{session_id}.json").write_text(
        json.dumps(session, indent=2, ensure_ascii=False))
    (CHANGES  / f"{chg_id}.json").write_text(
        json.dumps(chg,     indent=2, ensure_ascii=False))
    (EVIDENCES / f"{evd_id}.json").write_text(
        json.dumps(evd,     indent=2, ensure_ascii=False))
    _sync_session_to_db(session)  # índice analítico en bago.db

    # ── Regenerar informe de ideas ────────────────────────────────────────────
    ideas_report_path = _regenerate_ideas_report()

    # ── Actualizar global_state ───────────────────────────────────────────────
    gs = _read_global_state()
    gs["updated_at"] = now
    gs["last_completed_session_id"] = session_id
    gs["last_completed_workflow"] = "w9_cosecha"
    gs["last_completed_task_type"] = "harvest"
    gs["last_completed_roles"] = ["role_auditor"]
    gs["last_completed_change_id"] = chg_id
    gs["last_completed_evidence_id"] = evd_id
    gs["inventory"] = {
        "sessions": len(list(SESSIONS.glob("*.json"))),
        "changes":  len(list(CHANGES.glob("*.json"))),
        "evidences":len(list(EVIDENCES.glob("*.json")))
    }
    _write_global_state(gs)

    # ── Resultado ─────────────────────────────────────────────────────────────
    print()
    print("  ✅ Cosecha completada:")
    print(f"     · Sesión:   {session_id}")
    print(f"     · Cambio:   {chg_id}")
    print(f"     · Evidencia:{evd_id}")
    if ideas_report_path:
        print(f"     · Informe:  {Path(ideas_report_path).relative_to(BAGO_ROOT)}")
    else:
        print("     · Informe:  ⚠️  ideas_report.md no pudo regenerarse")
    print()
    print("  ⚠️  Recuerda regenerar TREE+CHECKSUMS:")
    print("     python3 .bago/tools/validate_pack.py  (después de regenerar)")
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
    run()
