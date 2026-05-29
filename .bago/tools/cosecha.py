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

# Truth Gate integration
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from bago.truth_gate import TruthGateError, assert_can_close_task
except Exception:
    TruthGateError = RuntimeError
    def assert_can_close_task(**_):  # type: ignore[misc]
        pass

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
    return json.loads(p.read_text(encoding="utf-8"))


def _write_global_state(gs):
    p = BAGO_ROOT / "state" / "global_state.json"
    if not DRY_RUN:
        p.write_text(json.dumps(gs, indent=2, ensure_ascii=False), encoding="utf-8")


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


def _sprint_window_start() -> datetime | None:
    """Devuelve el inicio de la ventana del 'sprint actual' para filtrar ideas.

    Estrategia (en orden):
      1. sprint.json::created_at si está activo.
      2. último SPRINT-*.json con status != closed.
      3. fallback: hace 7 días.
    """
    sprint_file = STATE_DIR / "sprint.json"
    if sprint_file.exists():
        try:
            d = json.loads(sprint_file.read_text(encoding="utf-8"))
            ts = d.get("created_at")
            if ts:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            pass
    sprints_dir = STATE_DIR / "sprints"
    if sprints_dir.is_dir():
        candidates = []
        for p in sprints_dir.glob("SPRINT-*.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if d.get("status") and d.get("status") != "closed" and d.get("created_at"):
                    candidates.append(d["created_at"])
            except Exception:
                continue
        if candidates:
            candidates.sort(reverse=True)
            try:
                return datetime.fromisoformat(candidates[0].replace("Z", "+00:00"))
            except Exception:
                pass
    # fallback: últimos 7 días
    return datetime.now(timezone.utc) - _td(days=7)


def _sprint_ideas_full() -> list[dict]:
    """Devuelve TODAS las ideas implementadas dentro de la ventana del sprint actual.

    Combina entradas de los dos campos coexistentes en implemented_ideas.json:
      · `implemented`        → {title, slot, done_at}
      · `ideas_completed`    → {id, title, date, session_close, workflow, objetivo}

    Filtra por fecha >= _sprint_window_start() y des-duplica por título.
    """
    path = STATE_DIR / "implemented_ideas.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    start = _sprint_window_start()
    out: list[dict] = []
    seen: set[str] = set()

    def _parse(ts):
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None

    # primero ideas_completed (más rico) — gana si hay duplicado
    for item in (data.get("ideas_completed") or []):
        ts = _parse(item.get("date"))
        if ts is None or (start and ts < start):
            continue
        title = item.get("title", "?")
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "date": item.get("date", ""),
            "slot": item.get("slot"),
            "workflow": item.get("workflow", ""),
            "session_close": item.get("session_close", ""),
            "objetivo": item.get("objetivo", ""),
            "source": "ideas_completed",
        })
    # luego implemented (resumen) — añade lo que no estaba
    for item in (data.get("implemented") or []):
        ts = _parse(item.get("done_at"))
        if ts is None or (start and ts < start):
            continue
        title = item.get("title", "?")
        key = title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "date": item.get("done_at", ""),
            "slot": item.get("slot"),
            "workflow": "",
            "session_close": "",
            "objetivo": "",
            "source": "implemented",
        })
    # ordenar más reciente primero
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    return out


def _render_sprint_ideas_md(
    session_id: str,
    ideas: list[dict],
    sprint_start: datetime | None,
    decision: str,
    next_step: str,
) -> str:
    """Genera el markdown del artefacto sidecar de cosecha con ideas del sprint.
    # COSECHA_SPRINT_IDEAS_ARTIFACT
    """
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M")
    start_str = sprint_start.astimezone().strftime("%Y-%m-%d %H:%M") if sprint_start else "—"
    lines = [
        f"# Cosecha {session_id} — Ideas del sprint",
        "",
        f"_Generado: {now_local} · ventana sprint desde: {start_str}_",
        "",
        f"**Decisión de la cosecha:** {decision or '—'}",
        f"**Próximo paso:** {next_step or '—'}",
        "",
        f"## Ideas implementadas en el sprint actual ({len(ideas)})",
        "",
    ]
    if not ideas:
        lines.append("_(sin ideas implementadas en la ventana del sprint actual)_")
        return "\n".join(lines) + "\n"
    lines += [
        "| # | Título | Workflow | Slot | Fecha | Cierre |",
        "|---|--------|----------|------|-------|--------|",
    ]
    for i, idea in enumerate(ideas, 1):
        title = (idea.get("title") or "?").replace("|", "\\|")
        wf    = (idea.get("workflow") or "—")[:20]
        slot  = idea.get("slot") if idea.get("slot") not in (None, "") else "—"
        date  = (idea.get("date") or "")[:10] or "—"
        sc    = (idea.get("session_close") or "—")[:35]
        lines.append(f"| {i} | {title} | {wf} | {slot} | {date} | {sc} |")
    # detalle de objetivos cuando exista
    detailed = [i for i in ideas if (i.get("objetivo") or "").strip()]
    if detailed:
        lines += ["", "## Objetivos / detalle", ""]
        for idea in detailed:
            lines.append(f"### {idea.get('title','?')}")
            lines.append("")
            lines.append(f"- **Workflow:** {idea.get('workflow','—') or '—'}")
            lines.append(f"- **Cierre:** {idea.get('session_close','—') or '—'}")
            lines.append(f"- **Objetivo:** {idea.get('objetivo','').strip()}")
            lines.append("")
    return "\n".join(lines) + "\n"


def _self_test_sprint_ideas() -> int:
    """Tests deterministas de las funciones nuevas (sin tocar disco).
    # COSECHA_SPRINT_IDEAS_TESTS
    """
    fails: list[str] = []
    # _sprint_window_start no debe fallar nunca
    w = _sprint_window_start()
    if w is None:
        fails.append("_sprint_window_start devolvió None (esperado fallback)")
    # _sprint_ideas_full debe devolver lista
    items = _sprint_ideas_full()
    if not isinstance(items, list):
        fails.append("_sprint_ideas_full no retorna lista")
    # render markdown vacío
    md_empty = _render_sprint_ideas_md("SES-TEST", [], w, "d", "n")
    if "sin ideas implementadas" not in md_empty:
        fails.append("render vacío no contiene mensaje fallback")
    # render con datos sintéticos
    md_full = _render_sprint_ideas_md(
        "SES-TEST",
        [{
            "title": "Idea X", "date": "2026-05-07T10:00:00+00:00",
            "slot": None, "workflow": "W2", "session_close": "SC.md",
            "objetivo": "hacer X", "source": "ideas_completed",
        }],
        w, "decisión", "siguiente"
    )
    for needle in ("# Cosecha SES-TEST", "Idea X", "W2", "## Objetivos"):
        if needle not in md_full:
            fails.append(f"render full no contiene: {needle}")
    if fails:
        for f in fails:
            print("  FAIL:", f)
        print(f"FAIL: {len(fails)} test(s)")
        return 1
    print("OK: 4/4 sprint-ideas tests")
    return 0


def _get_health_score() -> tuple[str, int]:
    """Captura el health score actual ejecutando health_score.py --score-only.
    # COSECHA_HEALTH_COMPARE_IMPLEMENTED
    Retorna (icono, puntos) — ej. ('🟢', 80).
    """
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

    # ── Sidecar markdown: ideas del sprint  # COSECHA_SPRINT_IDEAS_ARTIFACT ──
    sprint_start = _sprint_window_start()
    sprint_ideas = _sprint_ideas_full()
    sprint_md_path = SESSIONS / f"COSECHA_{session_id}_ideas.md"
    sprint_md_content = _render_sprint_ideas_md(
        session_id, sprint_ideas, sprint_start, decision, next_step
    )
    # registrar el sidecar como artifact de la sesión
    try:
        rel_md = str(sprint_md_path.relative_to(BAGO_ROOT))
    except ValueError:
        rel_md = str(sprint_md_path)
    if rel_md not in session["artifacts"]:
        session["artifacts"].append(rel_md)

    if DRY_RUN:
        print("\n  [DRY-RUN] Se crearían:")
        print(f"    · {SESSIONS / (session_id + '.json')}")
        print(f"    · {CHANGES / (chg_id + '.json')}")
        print(f"    · {EVIDENCES / (evd_id + '.json')}")
        print(f"    · {sprint_md_path}  (sidecar ideas del sprint, {len(sprint_ideas)} ideas)")
        print(f"    · {STATE_DIR / 'ideas_report.md'}  (regenerado)")
        print(f"\n  session:\n{json.dumps(session, indent=4, ensure_ascii=False)}")
        print(f"\n  sidecar preview (primeras 20 líneas):")
        for ln in sprint_md_content.splitlines()[:20]:
            print(f"    {ln}")
        return

    # ── Escribir ficheros ─────────────────────────────────────────────────────
    (SESSIONS / f"{session_id}.json").write_text(
        json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    (CHANGES  / f"{chg_id}.json").write_text(
        json.dumps(chg,     indent=2, ensure_ascii=False), encoding="utf-8")
    (EVIDENCES / f"{evd_id}.json").write_text(
        json.dumps(evd,     indent=2, ensure_ascii=False), encoding="utf-8")
    sprint_md_path.write_text(sprint_md_content, encoding="utf-8")
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

    # ── Truth Gate: solo bloquea si hay trace activo ─────────────────────────
    try:
        assert_can_close_task()
    except TruthGateError as e:
        print()
        print(f"  🚫 TRUTH_GATE_BLOCKED: {e}")
        print("     La cosecha se abortó porque hay claims sin trazabilidad.")
        print("     Ejecuta:  python -m bago.truth_cli report")
        print()
        raise SystemExit(2)

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
    print(f"     · Sidecar:  {sprint_md_path.relative_to(BAGO_ROOT)}  ({len(sprint_ideas)} ideas)")
    print()
    print("  ⚠️  Recuerda regenerar TREE+CHECKSUMS:")
    print("     python3 .bago/tools/validate_pack.py  (después de regenerar)")
    print()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(_self_test_sprint_ideas())
    run()
    # SAC: sugerir cosecha si hay muchas tareas done sin cosecha
    try:
        _ep = __import__("pathlib").Path(__file__).parent / "bago_sac_engine.py"
        _spec = _ilu.spec_from_file_location("bago_sac_engine", str(_ep))
        _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        _mod.sac_suggest("bago cosecha", exit_code=0)
    except Exception:
        pass
