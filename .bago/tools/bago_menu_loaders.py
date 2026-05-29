from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
from pathlib import Path

ROOT  = Path(__file__).resolve().parent.parent.parent
BAGO  = ROOT / ".bago"
STATE = BAGO / "state"
DB    = STATE / "bago.db"

# ── Live data loaders ─────────────────────────────────────────────────────────
# Cada loader recibe el cmd y devuelve list[str] para mostrar en el preview.
# Deben ser RÁPIDOS (solo lectura de ficheros locales, sin subprocess).

def _jread(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def _dbq(sql: str, params: tuple = ()) -> list:
    import sqlite3

    if not DB.exists():
        return []
    try:
        con = sqlite3.connect(str(DB), timeout=1)
        rows = con.execute(sql, params).fetchall()
        con.close()
        return rows
    except Exception:
        return []

def _ld_health(_: str) -> list[str]:
    gs = _jread(STATE / "global_state.json")
    score = gs.get("health_score", {}).get("last_score", "—")
    ts    = gs.get("health_score", {}).get("last_run", "")[:16].replace("T", " ")
    inv   = gs.get("inventory", {})
    return [
        f"  Score actual: {score}/100   última ejecución: {ts or '—'}",
        f"  Sesiones: {inv.get('sessions','?')}   Comandos en registry: {inv.get('commands','?')}",
        f"  Sub-opciones: score · report · stability · efficiency · consistency · sincerity",
    ]

def _ld_ideas(_: str) -> list[str]:
    avail   = _dbq("SELECT COUNT(*) FROM ideas WHERE status='available'")
    active  = _dbq("SELECT COUNT(*) FROM ideas WHERE status='active'")
    impl    = _dbq("SELECT COUNT(*) FROM ideas WHERE status='implemented'")
    top     = _dbq("SELECT title, priority FROM ideas WHERE status='available' ORDER BY priority DESC LIMIT 2")
    lines   = [f"  Disponibles: {avail[0][0] if avail else '?'}   Activas: {active[0][0] if active else '?'}   Implementadas: {impl[0][0] if impl else '?'}"]
    for row in top:
        lines.append(f"  ↳ [{row[1]}] {row[0][:55]}")
    return lines

def _ld_task(_: str) -> list[str]:
    rows = _dbq("SELECT title, status FROM ideas WHERE status='active' LIMIT 3")
    if not rows:
        return ["  No hay tarea activa en este momento."]
    lines = ["  Tareas activas:"]
    for r in rows:
        lines.append(f"  ▶  {r[0][:60]}")
    return lines

def _ld_next(_: str) -> list[str]:
    rows = _dbq("SELECT title, priority FROM ideas WHERE status='available' ORDER BY priority DESC LIMIT 1")
    if not rows:
        return ["  No hay ideas disponibles en el backlog."]
    return [
        f"  Próxima idea top (prioridad {rows[0][1]}):",
        f"  ▶  {rows[0][0][:60]}",
    ]

def _ld_status(_: str) -> list[str]:
    gs   = _jread(STATE / "global_state.json")
    rc   = _jread(STATE / "repo_context.json")
    wf   = gs.get("active_workflow", {}).get("name", "—")
    sp   = gs.get("active_sprint",   {}).get("name", "—")
    mode = rc.get("working_mode", "—")
    sess = gs.get("last_session", {}).get("session_id", "—")
    rows = _dbq("SELECT COUNT(*) FROM ideas WHERE status='active'")
    return [
        f"  Workflow: {wf}   Sprint: {sp}",
        f"  Modo: {mode}   Última sesión: {sess}",
        f"  Tareas activas: {rows[0][0] if rows else '?'}",
    ]

def _ld_sprint(_: str) -> list[str]:
    gs = _jread(STATE / "global_state.json")
    sp = gs.get("active_sprint", {})
    impl = _dbq("SELECT COUNT(*) FROM ideas WHERE status='implemented'")
    avail = _dbq("SELECT COUNT(*) FROM ideas WHERE status='available'")
    return [
        f"  Sprint: {sp.get('name', '—')}",
        f"  Implementadas: {impl[0][0] if impl else '?'}   En backlog: {avail[0][0] if avail else '?'}",
    ]

def _ld_devmode(_: str) -> list[str]:
    rc   = _jread(STATE / "repo_context.json")
    mode = rc.get("working_mode", "—")
    desc = {"self": "Developer → vista framework completa, todos los comandos",
            "user": "User → vista project-first limpia, comandos esenciales"}.get(mode, mode)
    return [f"  Modo activo: {mode}", f"  {desc}"]

def _ld_workspace(_: str) -> list[str]:
    rc  = _jread(STATE / "repo_context.json")
    return [
        f"  Modo: {rc.get('working_mode', '—')}",
        f"  Proyecto: {rc.get('project_name', '—')}",
        f"  Branch: {rc.get('git_branch', '—')}",
    ]

def _ld_recent(_: str) -> list[str]:
    rp = []
    try:
        rp = json.loads((STATE / "recent_projects.json").read_text())
    except Exception:
        pass
    if not rp:
        return ["  No hay proyectos recientes registrados."]
    lines = ["  Proyectos recientes:"]
    for p in rp[:4]:
        name = p.get("name") or Path(p.get("path", "?")).name
        lines.append(f"  ▷  {name}  — {p.get('path', '')[:45]}")
    return lines

def _ld_git(_: str) -> list[str]:
    # Lee .git/HEAD directamente (sin subprocess)
    head_f = ROOT / ".git" / "HEAD"
    branch = "—"
    if head_f.exists():
        head = head_f.read_text().strip()
        branch = head.replace("ref: refs/heads/", "") if head.startswith("ref:") else head[:7]
    # Último commit
    commit = "—"
    try:
        log_f = ROOT / ".git" / "logs" / "HEAD"
        if log_f.exists():
            last = log_f.read_text().strip().splitlines()[-1]
            commit = last.split("\t")[-1][:55] if "\t" in last else last[-55:]
    except Exception:
        pass
    return [f"  Branch: {branch}", f"  Último commit: {commit}"]

def _ld_snapshot(_: str) -> list[str]:
    snaps = sorted((STATE / "snapshots").glob("*.json")) if (STATE / "snapshots").exists() else []
    if not snaps:
        return ["  No hay snapshots guardados aun."]
    last = snaps[-1]
    return [
        f"  Snapshots disponibles: {len(snaps)}",
        f"  Último: {last.stem[:50]}",
        f"  Sub-opciones: (comparar) · --list · --ideas · --tools · --json",
    ]

def _ld_validate(_: str) -> list[str]:
    gs = _jread(STATE / "global_state.json")
    ts = gs.get("updated_at", "")[:16].replace("T", " ")
    return [
        f"  Última actualización del estado: {ts or '—'}",
        f"  Sub-opciones: (completo) · manifest · state · contents",
    ]

def _ld_sessions(_: str) -> list[str]:
    rows = _dbq("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC LIMIT 3")
    gs   = _jread(STATE / "global_state.json")
    total = gs.get("inventory", {}).get("sessions", "?")
    lines = [f"  Total sesiones registradas: {total}"]
    for r in rows:
        lines.append(f"  ▷  {r[0]}  {r[1][:16]}")
    return lines

# ── NEW LOADERS ──────────────────────────────────────────────────────────────

def _ld_done(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    wf  = gs.get("sprint_status", {}).get("last_completed_workflow", {})
    impl = _dbq("SELECT COUNT(*) FROM ideas WHERE status='implemented'")
    name = wf.get("title") or wf.get("name") or "—"
    dur  = wf.get("duration", "") or ""
    return [
        f"  Último workflow completado: {str(name)[:55]}",
        f"  Duración: {dur or '—'}   Ideas implementadas total: {impl[0][0] if impl else '?'}",
    ]

def _ld_workflow(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    sp  = gs.get("sprint_status", {})
    act = sp.get("active_workflow") or "— ninguno activo"
    last = sp.get("last_completed_workflow", {})
    last_name = last.get("title") or last.get("name") or "—"
    return [
        f"  Activo: {str(act)[:58]}",
        f"  Último completado: {str(last_name)[:52]}",
    ]

def _ld_goals(_: str) -> list[str]:
    gdir  = STATE / "goals"
    files = sorted(gdir.glob("*.json")) if gdir.exists() else []
    if not files:
        return ["  No hay goals registrados."]
    lines = [f"  Goals registrados: {len(files)}"]
    for f in files[:3]:
        try:
            g = json.loads(f.read_text())
            status = g.get("status", "?")
            lines.append(f"  [{status[:4]}] {g.get('title','?')[:52]}")
        except Exception:
            lines.append(f"  ▷  {f.stem}")
    return lines

def _ld_audit(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    val = gs.get("last_validation", {})
    date  = str(val.get("date", "—"))[:16]
    sinc  = val.get("sincerity", "—")
    stab  = val.get("stability", "—")
    gf    = gs.get("guardian_findings", {})
    warn  = gf.get("warnings", "?")
    return [
        f"  Última validación: {date}",
        f"  Sincerity: {sinc}   Stability: {stab}",
        f"  Warnings detectados: {warn}",
    ]

def _ld_stale(_: str) -> list[str]:
    gs   = _jread(STATE / "global_state.json")
    ob   = _jread(STATE / "orphan_baseline.json")
    gf   = gs.get("guardian_findings", {})
    warn = gf.get("warnings", "?")
    last = gf.get("last_run", "—")[:10]
    orp  = ob.get("total", ob.get("count", "?")) if isinstance(ob, dict) else "?"
    return [
        f"  Warnings activos: {warn}   Última revisión: {last}",
        f"  Huérfanos baseline: {orp}",
    ]

def _ld_sincerity(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    val = gs.get("last_validation", {})
    result = val.get("sincerity", "—")
    date   = str(val.get("date", "—"))[:16]
    return [
        f"  Resultado sincerity: {result}",
        f"  Validación del: {date}",
    ]

def _ld_stability(_: str) -> list[str]:
    gs   = _jread(STATE / "global_state.json")
    val  = gs.get("last_validation", {})
    sl   = gs.get("spiral_loop", {})
    stab = val.get("stability", "—")
    cycle = sl.get("last_cycle", "?")
    radius = sl.get("total_radius", "?")
    return [
        f"  Stability: {stab}   Espiral ciclo: {cycle}  radio: {radius}",
        f"  Validado el: {str(val.get('date','—'))[:16]}",
    ]

def _ld_heal(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    gf  = gs.get("guardian_findings", {})
    hp  = gf.get("health_pct", "—")
    warn = gf.get("warnings", "?")
    crit = gf.get("critical_errors", 0)
    return [
        f"  Health: {hp}%   Errores críticos: {crit}",
        f"  Warnings activos: {warn}   → ejecuta heal para remediar",
    ]

def _ld_inbox(_: str) -> list[str]:
    data  = _jread(STATE / "inbox.json")
    tasks = data.get("tasks", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    n = len(tasks)
    if not tasks:
        return ["  Inbox vacio - no hay tareas pendientes."]
    lines = [f"  Tareas en inbox: {n}"]
    for t in tasks[:3]:
        title = (t.get("title") or t.get("text") or str(t))[:55] if isinstance(t, dict) else str(t)[:55]
        lines.append(f"  ▷  {title}")
    return lines

def _ld_siembra(_: str) -> list[str]:
    data = _jread(STATE / "siembras.json")
    seeds = data.get("siembras", []) if isinstance(data, dict) else []
    n = len(seeds)
    return [
        f"  Siembras/aprendizajes registrados: {n}",
        f"  Padre: {data.get('padre', '—') if isinstance(data, dict) else '—'}",
    ]

def _ld_llm(_: str) -> list[str]:
    cfg = _jread(STATE / "llm_config.json")
    return [
        f"  Motor: {cfg.get('engine','—')}   Modelo activo: {cfg.get('active_model','—')}",
        f"  Servidor: {cfg.get('server_url','—')}",
    ]

def _ld_autonomous(_: str) -> list[str]:
    a = _jread(STATE / "autonomous_state.json")
    ts = str(a.get("last_cycle_ts", "—"))[:16].replace("T", " ")
    return [
        f"  Estado: {a.get('status','—')}   Decisión: {a.get('last_decision','—')}",
        f"  Ciclos: {a.get('cycle_count','?')}   Estabilidad: {a.get('stable_count','?')}   Último: {ts}",
    ]

def _ld_agents(_: str) -> list[str]:
    ag = _jread(STATE / "agents_registry.json")
    agents = {k: v for k, v in ag.items() if not k.startswith("_")} if isinstance(ag, dict) else {}
    n = len(agents)
    names = ", ".join(list(agents.keys())[:4])
    return [
        f"  Agentes registrados: {n}",
        f"  {names}",
    ]

def _ld_neural(_: str) -> list[str]:
    f = STATE / "neural_events.jsonl"
    if not f.exists():
        return ["  No hay eventos neurales registrados."]
    lines_raw = f.read_text(errors="ignore").strip().splitlines()
    n = len(lines_raw)
    last_type = "—"
    try:
        last_type = json.loads(lines_raw[-1]).get("event_type", "—")
    except Exception:
        pass
    return [
        f"  Eventos neurales: {n}",
        f"  Último tipo: {last_type}",
    ]

def _ld_version(_: str) -> list[str]:
    gs = _jread(STATE / "global_state.json")
    ver = gs.get("bago_version", "—")
    hist = gs.get("version_history", [])
    lines = [f"  Versión BAGO: {ver}"]
    for v in reversed(hist[-2:]):
        lines.append(f"  v{v.get('version','?')} [{v.get('label','?')}] — {v.get('released','?')}")
    return lines

def _ld_notify(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    nb  = gs.get("tools", {}).get("notify_bago", {})
    return [
        f"  Proveedor: {nb.get('active_provider','—')}   Estado: {nb.get('status','—')}",
        f"  Teléfono: {nb.get('phone','—')}",
    ]

def _ld_dashboard(_: str) -> list[str]:
    gs   = _jread(STATE / "global_state.json")
    gf   = gs.get("guardian_findings", {})
    inv  = gs.get("inventory", {})
    avail = _dbq("SELECT COUNT(*) FROM ideas WHERE status='available'")
    act   = _dbq("SELECT COUNT(*) FROM ideas WHERE status='active'")
    return [
        f"  Health: {gf.get('health_pct','?')}%   Warnings: {gf.get('warnings','?')}",
        f"  Sesiones: {inv.get('sessions','?')}   Cmds: {inv.get('commands','?')}",
        f"  Ideas: {avail[0][0] if avail else '?'} disponibles, {act[0][0] if act else '?'} activas",
    ]

def _ld_cosecha(_: str) -> list[str]:
    gs = _jread(STATE / "global_state.json")
    kb = gs.get("knowledge_base", {})
    impl = _dbq("SELECT COUNT(*) FROM ideas WHERE status='implemented'")
    return [
        f"  Ficheros knowledge: {kb.get('files_count','?')}   Última: {kb.get('last_harvest','—')}",
        f"  Ideas cosechadas (implementadas): {impl[0][0] if impl else '?'}",
    ]

def _ld_promote(_: str) -> list[str]:
    rows = _dbq("SELECT title, priority FROM ideas WHERE status='available' ORDER BY priority DESC LIMIT 3")
    avail = _dbq("SELECT COUNT(*) FROM ideas WHERE status='available'")
    lines = [f"  Ideas disponibles para promover: {avail[0][0] if avail else '?'}"]
    for r in rows:
        lines.append(f"  [{r[1]}] {r[0][:55]}")
    return lines

def _ld_reopen(_: str) -> list[str]:
    rows  = _dbq("SELECT title FROM ideas WHERE status='implemented' ORDER BY rowid DESC LIMIT 2")
    impl  = _dbq("SELECT COUNT(*) FROM ideas WHERE status='implemented'")
    lines = [f"  Ideas implementadas (reabrir→disponible): {impl[0][0] if impl else '?'}"]
    for r in rows:
        lines.append(f"  ▷  {r[0][:60]}")
    return lines

def _ld_context(_: str) -> list[str]:
    rc  = _jread(STATE / "repo_context.json")
    gs  = _jread(STATE / "global_state.json")
    proj = gs.get("active_project", rc.get("project_name", "—"))
    return [
        f"  Proyecto: {proj}   Modo: {rc.get('working_mode','—')}",
        f"  Branch: {rc.get('git_branch','—')}   Tipo: {rc.get('project_type','—')}",
    ]

def _ld_project(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    rc  = _jread(STATE / "repo_context.json")
    proj = gs.get("active_project", rc.get("project_name", "—"))
    return [
        f"  Proyecto activo: {proj}",
        f"  Modo: {rc.get('working_mode','—')}   Branch: {rc.get('git_branch','—')}",
    ]

def _ld_deps(_: str) -> list[str]:
    dm   = _jread(STATE / "deps_manifest.json")
    packs = dm.get("packs", {})
    names = ", ".join(list(packs.keys())[:5])
    return [
        f"  Versión BAGO manifest: {dm.get('bago_version','—')}",
        f"  Packs ({len(packs)}): {names}",
    ]

def _ld_install(_: str) -> list[str]:
    ic  = _jread(STATE / "install_complete.json")
    ts  = str(ic.get("accepted_at", "—"))[:16].replace("T", " ")
    return [
        f"  BAGO v{ic.get('bago_version','?')} instalado en {ts}",
        f"  Python: {ic.get('python_version','—')}   Plataforma: {ic.get('platform','—')}",
    ]

def _ld_state_manager(_: str) -> list[str]:
    files = list(STATE.iterdir()) if STATE.exists() else []
    jsons = sum(1 for f in files if f.suffix == ".json")
    dbs   = sum(1 for f in files if f.suffix == ".db")
    return [
        f"  Archivos de estado: {len(files)} total ({jsons} JSON, {dbs} DB)",
        f"  Directorio: {STATE}",
    ]

def _ld_weekly(_: str) -> list[str]:
    rows = _dbq(
        "SELECT session_id, created_at FROM sessions "
        "WHERE created_at >= date('now','-7 days') ORDER BY created_at DESC LIMIT 3"
    )
    sprints_dir = STATE / "sprints"
    scount = len(list(sprints_dir.glob("*.json"))) if sprints_dir.exists() else 0
    lines = [f"  Sesiones esta semana: {len(rows)}   Sprints archivados: {scount}"]
    for r in rows:
        lines.append(f"  ▷  {r[0]}  {r[1][:16]}")
    return lines

def _ld_advisor(_: str) -> list[str]:
    f = STATE / "advisor_context.jsonl"
    if not f.exists():
        return ["  No hay contexto de advisor registrado."]
    lines_raw = f.read_text(errors="ignore").strip().splitlines()
    return [f"  Entradas de contexto advisor: {len(lines_raw)}"]

def _ld_scope(_: str) -> list[str]:
    rc  = _jread(STATE / "repo_context.json")
    gs  = _jread(STATE / "global_state.json")
    proj = gs.get("active_project", rc.get("project_name", "—"))
    act  = _dbq("SELECT COUNT(*) FROM ideas WHERE status='active'")
    return [
        f"  Scope: {proj}   Modo: {rc.get('working_mode','—')}",
        f"  Tareas activas en scope: {act[0][0] if act else '?'}",
    ]

# ── FINAL 24 LOADERS (filesystem / code analysis) ────────────────────────────

def _ld_code_metrics(_: str) -> list[str]:
    py  = len(list(ROOT.rglob("*.py")))
    ts  = len(list(ROOT.rglob("*.ts"))) + len(list(ROOT.rglob("*.js")))
    dirs = sum(1 for d in ROOT.iterdir() if d.is_dir() and not d.name.startswith("."))
    return [
        f"  Archivos .py: {py}   JS/TS: {ts}",
        f"  Directorios top-level: {dirs}",
    ]

def _ld_code_search(_: str) -> list[str]:
    rc = _jread(STATE / "repo_context.json")
    proj = rc.get("project_name", str(ROOT.name))
    py   = len(list(ROOT.rglob("*.py")))
    return [
        f"  Proyecto: {proj}   ({py} archivos .py indexables)",
        f"  Uso: bago code-search <patrón>",
    ]

def _ld_lint_runner(_: str) -> list[str]:
    gs  = _jread(STATE / "global_state.json")
    val = gs.get("last_validation", {})
    date = str(val.get("date", "—"))[:16]
    py   = len(list(ROOT.rglob("*.py")))
    return [
        f"  Última validación: {date}   ({py} archivos a analizar)",
        f"  Ejecuta: bago lint-runner para informe completo",
    ]

def _ld_rubber_duck(_: str) -> list[str]:
    rows = _dbq("SELECT title FROM ideas WHERE status='active' LIMIT 1")
    task = rows[0][0][:55] if rows else "sin tarea activa"
    return [
        f"  Tarea activa: {task}",
        f"  El duck escuchará y hará las preguntas correctas.",
    ]

def _ld_code_meta(_: str) -> list[str]:
    py = len(list(ROOT.rglob("*.py")))
    rc = _jread(STATE / "repo_context.json")
    return [
        f"  Proyecto: {rc.get('project_name', ROOT.name)}   {py} archivos .py",
        f"  Análisis estático: sin estado previo almacenado",
    ]

def _ld_toolsmith(_: str) -> list[str]:
    ag   = _jread(STATE / "agents_registry.json")
    tools = {k: v for k, v in ag.items() if not k.startswith("_")} if isinstance(ag, dict) else {}
    tools_dir = Path(__file__).parent
    n_tools = len(list(tools_dir.glob("*.py")))
    return [
        f"  Tools en .bago/tools/: {n_tools}",
        f"  Agentes: {len(tools)}   → {', '.join(list(tools.keys())[:3])}",
    ]

def _ld_route(_: str) -> list[str]:
    f = STATE / "routing_history.jsonl"
    if not f.exists():
        return ["  Sin historial de enrutamiento."]
    lines = f.read_text(errors="ignore").strip().splitlines()
    try:
        last = json.loads(lines[-1])
        return [
            f"  Eventos: {len(lines)}   Último agente: {last.get('agent','—')}",
            f"  Modelo: {last.get('model','—')}   Confianza: {last.get('confidence','?')}%",
        ]
    except Exception:
        return [f"  Eventos de routing: {len(lines)}"]

def _ld_repo_clone(_: str) -> list[str]:
    rc = _jread(STATE / "repo_context.json")
    return [
        f"  Workspace: {ROOT.parent}",
        f"  Proyecto actual: {rc.get('project_name', ROOT.name)}",
    ]

def _ld_repo_list(_: str) -> list[str]:
    ws   = ROOT.parent
    repos = [d.name for d in ws.iterdir() if d.is_dir() and (d / ".git").exists()][:6]
    return [
        f"  Repos git en {ws.name}/: {len(repos)}",
        "  " + "  ".join(repos[:4]) if repos else "  (ninguno encontrado)",
    ]

def _ld_repo_switch(_: str) -> list[str]:
    rc = _jread(STATE / "repo_context.json")
    head_f = ROOT / ".git" / "HEAD"
    branch = "—"
    if head_f.exists():
        h = head_f.read_text().strip()
        branch = h.replace("ref: refs/heads/", "") if h.startswith("ref:") else h[:7]
    return [
        f"  Repo actual: {rc.get('project_name', ROOT.name)}   Branch: {branch}",
        f"  Modo: {rc.get('working_mode','—')}",
    ]

def _ld_map(_: str) -> list[str]:
    dirs = [d.name for d in ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")][:6]
    py   = len(list(ROOT.rglob("*.py")))
    return [
        f"  Directorios: {', '.join(dirs[:5])}",
        f"  Total .py: {py}",
    ]

def _ld_work_matrix(_: str) -> list[str]:
    avail = _dbq("SELECT COUNT(*) FROM ideas WHERE status='available'")
    act   = _dbq("SELECT COUNT(*) FROM ideas WHERE status='active'")
    impl  = _dbq("SELECT COUNT(*) FROM ideas WHERE status='implemented'")
    rows  = _dbq("SELECT COUNT(*) FROM sessions")
    return [
        f"  Ideas: {avail[0][0] if avail else '?'} disp · {act[0][0] if act else '?'} act · {impl[0][0] if impl else '?'} impl",
        f"  Sesiones totales: {rows[0][0] if rows else '?'}",
    ]

def _ld_docs(_: str) -> list[str]:
    docs = ROOT / "docs"
    if not docs.exists():
        return ["  No hay directorio docs/."]
    files = list(docs.rglob("*.*"))
    mds   = [f for f in files if f.suffix == ".md"]
    return [
        f"  Docs: {len(files)} archivos   {len(mds)} Markdown",
        "  " + "  ".join(f.name[:20] for f in mds[:3]),
    ]

def _ld_chronicle(_: str) -> list[str]:
    rows = _dbq("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC LIMIT 2")
    total = _dbq("SELECT COUNT(*) FROM sessions")
    lines = [f"  Sesiones registradas: {total[0][0] if total else '?'}"]
    for r in rows:
        lines.append(f"  ▷  {r[0]}  {r[1][:16]}")
    return lines

def _ld_alias_manager(_: str) -> list[str]:
    config_dir = ROOT / "config"
    alias_files = list(config_dir.glob("alias*")) if config_dir.exists() else []
    bago_config = Path(__file__).parent.parent / "config"
    alias_files += list(bago_config.glob("alias*")) if bago_config.exists() else []
    if not alias_files:
        return ["  Sin archivos de alias configurados.", "  Usa bago alias-manager para gestionar aliases."]
    return [f"  Archivos alias: {len(alias_files)}   → {alias_files[0].name}"]

def _ld_env_manager(_: str) -> list[str]:
    env_files = list(ROOT.glob(".env*")) + list(ROOT.glob("**/.env"))
    return [
        f"  Archivos .env encontrados: {len(env_files)}",
        "  " + "  ".join(f.name for f in env_files[:4]) if env_files else "  (ninguno)",
    ]

def _ld_personality(_: str) -> list[str]:
    gs = _jread(STATE / "global_state.json")
    ver = gs.get("bago_version", "—")
    return [
        f"  Identidad BAGO v{ver}",
        "  Configura nombre, tono y preferencias de la IA.",
    ]

def _ld_net(_: str) -> list[str]:
    cfg = _jread(STATE / "llm_config.json")
    return [
        f"  LLM server: {cfg.get('server_url','—')}",
        f"  Motor: {cfg.get('engine','—')}",
    ]

def _ld_notify_desktop(_: str) -> list[str]:
    import platform
    sys_info = platform.system()
    return [
        f"  Plataforma: {sys_info}",
        "  Notificaciones de escritorio via osascript (macOS) o notify-send (Linux)",
    ]

def _ld_build_clean(_: str) -> list[str]:
    caches = list(ROOT.rglob("__pycache__"))
    pyc    = list(ROOT.rglob("*.pyc"))
    return [
        f"  Directorios __pycache__: {len(caches)}",
        f"  Archivos .pyc: {len(pyc)}   → bago build-clean para eliminar",
    ]

def _ld_build_run(_: str) -> list[str]:
    rc   = _jread(STATE / "repo_context.json")
    proj = rc.get("project_name", ROOT.name)
    has_setup = (ROOT / "pyproject.toml").exists() or (ROOT / "setup.py").exists()
    has_pkg   = (ROOT / "package.json").exists()
    tipo = "Python" if has_setup else ("Node.js" if has_pkg else "desconocido")
    return [
        f"  Proyecto: {proj}   Tipo: {tipo}",
        "  Ejecuta el proyecto en modo dev/producción.",
    ]


def _ld_orphan_shield(_: str) -> list[str]:
    ob = _jread(STATE / "orphan_baseline.json")
    known = ob.get("count", len(ob.get("known_orphans", [])))
    return [
        f"  Huérfanos baseline conocidos: {known}",
        f"  Ejecuta para detectar nuevos huérfanos de archivo/registry/ruta",
    ]


def _ld_doc_index(_: str) -> list[str]:
    docs_dir = ROOT / "docs"
    docs = list(docs_dir.glob("*.md")) if docs_dir.exists() else []
    return [
        f"  Documentos en docs/: {len(docs)}",
        f"  Ejecuta para ver cobertura: qué tools están documentados",
    ]



def _ld_canon(_: str) -> list[str]:
    import json
    from pathlib import Path
    log_path = Path(__file__).resolve().parent.parent / 'state' / 'canon_log.json'
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text())
            cycles = log.get('cycles', 0)
            last = log.get('last_run', 'nunca')[:16].replace('T',' ')
            bases = log.get('baselines', {})
            warn = bases.get('MODULAR', {}).get('warn_count', '?')
            undoc = bases.get('SCAN', {}).get('undoc_count', '?')
            return [
                f'  Ciclos completados: {cycles} · último: {last}',
                f'  MODULAR: {warn} WARN  SCAN: {undoc} sin doc',
            ]
        except Exception:
            pass
    return [
        '  Bucle de Shepard: 4 modos x 3 voces',
        '  Sin ciclos registrados aún — ejecuta para iniciar',
    ]


# ── DISPATCHER ───────────────────────────────────────────────────────────────

# Dispatcher: cmd → loader function
_LIVE_LOADERS: dict[str, callable] = {
    # Existing
    "health":            _ld_health,
    "ideas":             _ld_ideas,
    "task":              _ld_task,
    "next":              _ld_next,
    "assign":            _ld_task,
    "status":            _ld_status,
    "sprint":            _ld_sprint,
    "devmode":           _ld_devmode,
    "workspace-select":  _ld_workspace,
    "recent-projects":   _ld_recent,
    "git":               _ld_git,
    "git-status":        _ld_git,
    "snapshot":          _ld_snapshot,
    "validate":          _ld_validate,
    "hello":             _ld_status,
    # Sesión & workflow
    "start":             _ld_status,
    "done":              _ld_done,
    "workflow":          _ld_workflow,
    "flow":              _ld_workflow,
    "goals":             _ld_goals,
    "scope":             _ld_scope,
    # Calidad & salud
    "audit":             _ld_audit,
    "stale":             _ld_stale,
    "sincerity":         _ld_sincerity,
    "stability":         _ld_stability,
    "heal":              _ld_heal,
    # Ideas & backlog
    "select":            _ld_ideas,
    "promote":           _ld_promote,
    "reopen":            _ld_reopen,
    "inbox":             _ld_inbox,
    "cosecha":           _ld_cosecha,
    # Sesiones & informes
    "sessions":          _ld_sessions,
    "search-history":    _ld_sessions,
    "recientes":         _ld_sessions,
    "weekly-report":     _ld_weekly,
    "dashboard":         _ld_dashboard,
    # Agentes & IA
    "agent":             _ld_agents,
    "autonomous":        _ld_autonomous,
    "neural":            _ld_neural,
    "neural-toolbox":    _ld_neural,
    "llm":               _ld_llm,
    "advisor":           _ld_advisor,
    # Workspace & context
    "project":           _ld_project,
    "context":           _ld_context,
    # Infraestructura & config
    "siembra":           _ld_siembra,
    "seed":              _ld_siembra,
    "version":           _ld_version,
    "notify-bago":       _ld_notify,
    "deps":              _ld_deps,
    "setup":             _ld_install,
    "install":           _ld_install,
    "state-manager":     _ld_state_manager,
    # Análisis de código
    "code-metrics":      _ld_code_metrics,
    "code-search":       _ld_code_search,
    "lint-runner":       _ld_lint_runner,
    "rubber-duck":       _ld_rubber_duck,
    "naming":            _ld_code_meta,
    "hardcode":          _ld_code_meta,
    "secrets":           _ld_code_meta,
    "toolsmith":         _ld_toolsmith,
    "route":             _ld_route,
    # Workspace & repos
    "repo-clone":        _ld_repo_clone,
    "repo-list":         _ld_repo_list,
    "repo-switch":       _ld_repo_switch,
    "map":               _ld_map,
    # Informes
    "work_matrix":       _ld_work_matrix,
    "docs":              _ld_docs,
    "chronicle":         _ld_chronicle,
    # Config & entorno
    "alias-manager":     _ld_alias_manager,
    "env-manager":       _ld_env_manager,
    "personality-panel": _ld_personality,
    # Infraestructura
    "net-scan":          _ld_net,
    "ping-server":       _ld_net,
    "notify-desktop":    _ld_notify_desktop,
    "build-clean":       _ld_build_clean,
    "build-run":         _ld_build_run,
    "orphan-shield":     _ld_orphan_shield,
    "doc-index":         _ld_doc_index,
    "canon":             _ld_canon,
}


def _live_data(cmd: str, long_desc: str) -> list[str]:
    """Devuelve líneas de preview: datos live si hay loader, sino descripción wrapeada."""
    loader = _LIVE_LOADERS.get(cmd)
    if loader:
        try:
            return loader(cmd)
        except Exception:
            pass
    # Fallback: word-wrap de long_desc
    words = long_desc.split()
    line, lines = "", []
    for word in words:
        if len(line) + len(word) + 1 > 56:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return ["  " + l for l in lines[:3]]
