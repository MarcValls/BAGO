#!/usr/bin/env python3
"""
bago menu — Menú interactivo de comandos BAGO jerarquizado por flujo de trabajo.

Interfaz curses con sidebar de grupos + lista de comandos + preview.
La jerarquía sigue el flujo real de una sesión BAGO:
  Sesión → Ideas → Tarea activa → Calidad → Código → Agentes → ...

Navegación:
  ↑↓         mover dentro del grupo activo
  → / Tab    entrar en lista / siguiente grupo
  ←          volver al sidebar de grupos
  Enter      ejecutar el comando seleccionado
  q / Esc    salir sin ejecutar

Uso:
  bago menu               → abre el menú interactivo
  bago menu --list        → lista todos los grupos y comandos (sin interacción)
"""
from __future__ import annotations

import curses
import json
import sqlite3
import subprocess
import sys
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
        return ["  No hay snapshots guardados aún."]
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
        return ["  Inbox vacío — no hay tareas pendientes."]
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
    "code-metrics":      lambda _: _ld_code_metrics(_),
    "code-search":       lambda _: _ld_code_search(_),
    "lint-runner":       lambda _: _ld_lint_runner(_),
    "rubber-duck":       lambda _: _ld_rubber_duck(_),
    "naming":            lambda _: _ld_code_meta(_),
    "hardcode":          lambda _: _ld_code_meta(_),
    "secrets":           lambda _: _ld_code_meta(_),
    "toolsmith":         lambda _: _ld_toolsmith(_),
    "route":             lambda _: _ld_route(_),
    # Workspace & repos
    "repo-clone":        lambda _: _ld_repo_clone(_),
    "repo-list":         lambda _: _ld_repo_list(_),
    "repo-switch":       lambda _: _ld_repo_switch(_),
    "map":               lambda _: _ld_map(_),
    # Informes
    "work_matrix":       lambda _: _ld_work_matrix(_),
    "docs":              lambda _: _ld_docs(_),
    "chronicle":         lambda _: _ld_chronicle(_),
    # Config & entorno
    "alias-manager":     lambda _: _ld_alias_manager(_),
    "env-manager":       lambda _: _ld_env_manager(_),
    "personality-panel": lambda _: _ld_personality(_),
    # Infraestructura
    "net-scan":          lambda _: _ld_net(_),
    "ping-server":       lambda _: _ld_net(_),
    "notify-desktop":    lambda _: _ld_notify_desktop(_),
    "build-clean":       lambda _: _ld_build_clean(_),
    "build-run":         lambda _: _ld_build_run(_),
}

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



# Cada entrada: (nombre_grupo, [(cmd, descripción_corta, descripción_larga)])
MENU: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("🚀  Sesión", [
        ("start",            "Arranca sesión BAGO",          "Panel visual completo: health, workspace, tarea activa, ideas priorizadas"),
        ("status",           "Estado actual del sistema",    "Flujo activo + tarea pendiente + health score en 3 líneas"),
        ("hello",            "Bienvenida y contexto",        "Resumen de estado: workflow, sprint, voces CAP activas"),
        ("next",             "Siguiente idea → tarea",       "Toma la idea top del backlog y abre una tarea de trabajo"),
        ("devmode",          "Dev / User mode toggle",       "Developer: vista framework completa. User: vista project-first limpia"),
        ("workspace-select", "Elige espacio de trabajo",     "Menú: framework (self) | directorio padre | ruta externa. Persiste en repo_context.json"),
        ("recent-projects",  "Proyectos recientes",          "Historial de repos visitados con sesiones e ideas implementadas"),
    ]),
    ("💡  Ideas", [
        ("ideas",   "Ver backlog priorizado",       "Lista ideas ordenadas por contexto, sprint y urgencia", [
            ("",           "(lista)",      "Muestra las top 5-20 ideas priorizadas por contexto (predeterminado)"),
            ("--select",   "--select",     "Selector interactivo del backlog con navegación"),
            ("--baseline", "--baseline",   "Solo ideas de bajo riesgo, estables y probadas"),
            ("--export",   "--export",     "Exporta snapshot de ideas a .bago/state/ideas_snapshot.md"),
            ("--health",   "--health",     "Estadísticas del catálogo: total, por estado, por intención"),
            ("--all",      "--all",        "Muestra ideas de todos los proyectos (ignora filtro devmode)"),
        ]),
        ("cosecha", "Capturar nueva idea",          "Registra una idea nueva en bago.db con título, contexto y prioridad"),
        ("next",    "Aceptar idea top como tarea",  "Shortcut: toma la idea #1 y la convierte en tarea activa"),
        ("assign",  "Asignar idea a tarea",         "Convierte una idea específica en la tarea activa del sprint"),
        ("select",  "Seleccionar idea del backlog", "Navegación interactiva del backlog con filtros"),
        ("inbox",   "Bandeja de entrada",           "Ideas capturadas sin clasificar pendientes de triaje"),
        ("promote", "Promover idea a sprint",       "Sube una idea al sprint activo con prioridad ajustada"),
        ("reopen",  "Reabrir tarea cerrada",        "Reabre una tarea done para revisión o continuación"),
    ]),
    ("📋  Tarea activa", [
        ("task",     "Ver tarea actual",     "Muestra la tarea activa: idea, contexto, pasos pendientes"),
        ("done",     "Cerrar tarea actual",  "Registra la tarea como completada con evidencia"),
        ("workflow", "Gestionar workflow",   "Inicia, avanza o cierra el workflow activo del sprint"),
        ("flow",     "Estado del flujo",     "Vista del grafo de workflow: nodos, transiciones, estado"),
        ("sprint",   "Panel del sprint",     "Resumen del sprint: ideas completadas, velocidad, próximos"),
        ("goals",    "Objetivos del sprint", "Define y revisa los objetivos cualitativos del sprint"),
        ("scope",    "Scope de la tarea",    "Define qué archivos/módulos están en scope para esta tarea"),
    ]),
    ("✅  Calidad & Salud", [
        ("health",    "Score de salud 0-100",        "5 dimensiones: integridad, disciplina, decisiones, stale, consistencia", [
            ("",            "score",       "Score 0-100 ponderado (predeterminado)"),
            ("report",      "report",      "Reporte completo Markdown/HTML con todos los checks"),
            ("stability",   "stability",   "Diagnóstico completo de estabilidad del workspace"),
            ("efficiency",  "efficiency",  "Ratio de eficiencia inter-versiones del framework"),
            ("consistency", "consistency", "Anti-drift: verifica que registry/CI/README son coherentes"),
            ("sincerity",   "sincerity",   "Detecta promesas vacías y sycofancía en docs y sesiones"),
        ]),
        ("validate",  "Validación completa",         "GO/FAIL en manifest, state y pack — ejecutar antes de cada commit", [
            ("",         "(completo)",  "Validación completa: manifest + state + pack (predeterminado)"),
            ("manifest", "manifest",    "Solo valida pack.json contra global_state.json"),
            ("state",    "state",       "Solo valida coherencia de global_state.json y sesiones"),
            ("contents", "contents",    "Valida un ZIP de pack distribuible (pack_contents)"),
        ]),
        ("audit",     "Auditoría de sesión",         "Trail completo: roles, contratos, evidencias, decisiones"),
        ("stale",     "Detectar estado obsoleto",    "Encuentra workflows abandonados, tareas huérfanas, state desincronizado"),
        ("sincerity", "Detector de promesas vacías", "Analiza si el agente cumplió lo que prometió en la sesión"),
        ("stability", "Informe de estabilidad",      "Tendencia histórica del health score con alertas de regresión"),
        ("siembra",   "Semillas de mejora",          "Registra aprendizajes de la sesión como semillas para ideas futuras"),
        ("heal",      "Reparar inconsistencias",     "Auto-repair de problemas detectados por health/validate"),
    ]),
    ("🔍  Análisis de código", [
        ("code-metrics", "Métricas del código",      "Complejidad ciclomática, duplicaciones, líneas por módulo"),
        ("code-search",  "Búsqueda semántica",       "Busca en el historial de código del proyecto con contexto"),
        ("lint-runner",  "Linter configurable",      "Ejecuta pyflakes/ruff/eslint según el tipo de proyecto"),
        ("rubber-duck",  "Debug asistido",           "Explica el problema en voz alta — el sistema hace preguntas"),
        ("naming",       "Check de nomenclatura",    "Verifica convenciones de nombres en el codebase"),
        ("hardcode",     "Detectar hardcoding",      "Encuentra valores hardcodeados que deberían ser config"),
        ("secrets",      "Auditoría de secretos",    "Detecta API keys, passwords y tokens en el código"),
        ("deps",         "Análisis de dependencias", "Estado de dependencias: outdated, vulnerables, no usadas"),
    ]),
    ("🤖  Agentes & IA", [
        ("agent",          "Gateway de agentes",   "Lanza y coordina agentes especializados del sistema BAGO"),
        ("autonomous",     "Bucle autónomo",       "Ejecuta ciclos autónomos de mejora sin intervención humana"),
        ("neural",         "Motor neural",         "Bus de mensajes SSE inter-agente: nodos, mapas, estado"),
        ("neural-toolbox", "Toolbox adaptativo",   "Convierte contexto en lenguaje natural a un toolbox configurado"),
        ("llm",            "Configuración LLM",    "Gestiona el modelo activo, temperatura y parámetros del LLM"),
        ("advisor",        "Consejero estratégico","Recomendaciones de next steps basadas en el estado del sistema"),
        ("toolsmith",      "Creador de tools",     "Genera nuevas herramientas BAGO desde especificación en lenguaje natural"),
        ("route",          "Router de intención",  "Mapea texto libre a comandos BAGO: 'quiero ver mis ideas' → bago ideas"),
    ]),
    ("📁  Workspace & Repos", [
        ("repo-clone",  "Clonar repositorio",    "Clona un repo GitHub en el workspace con auto-setup BAGO"),
        ("repo-list",   "Listar repos clonados", "Lista repositorios en el workspace con estado y health"),
        ("repo-switch", "Cambiar repo activo",   "Cambia el contexto activo entre repositorios del workspace"),
        ("git",         "Contexto git",          "Detect, map, git status, stale — vista git del workspace"),
        ("git-status",  "Estado git detallado",  "Estado completo: branch, staged, unstaged, remotes"),
        ("project",     "Gestión de proyecto",   "Crea, vincula o consulta el estado del proyecto activo"),
        ("context",     "Detector de contexto",  "Identifica automáticamente el tipo de proyecto y sugiere workflow"),
        ("map",         "Mapa del workspace",    "Vista estructural completa del workspace y sus relaciones"),
    ]),
    ("📊  Informes & Conocimiento", [
        ("weekly-report",  "Informe semanal",       "Resumen de la semana: ideas implementadas, salud, velocidad"),
        ("recientes",      "Actividad reciente",    "Commits, sesiones e ideas de los últimos N días"),
        ("snapshot",       "Snapshot del estado",   "Captura y compara snapshots del estado del sistema", [
            ("",        "(comparar)",  "Compara los dos últimos snapshots (predeterminado)"),
            ("--list",  "--list",      "Lista todos los snapshots guardados con fecha y tamaño"),
            ("--ideas", "--ideas",     "Compara solo la sección de ideas entre snapshots"),
            ("--tools", "--tools",     "Compara solo la sección de herramientas entre snapshots"),
            ("--json",  "--json",      "Salida de la comparación en formato JSON"),
        ]),
        ("dashboard",      "Panel principal",       "Dashboard interactivo con todas las métricas del sistema"),
        ("work_matrix",    "Matriz de trabajo",     "Visualiza el trabajo por agente, capa y tipo de tarea"),
        ("search-history", "Búsqueda en historial", "Busca en el historial completo de sesiones BAGO"),
        ("docs",           "Documentación generada","Documentación auto-generada de todos los comandos activos"),
        ("chronicle",      "Crónica del proyecto",  "Historia narrativa del proyecto: decisiones, hitos, aprendizajes"),
    ]),
    ("⚙️  Configuración", [
        ("devmode",           "Dev / User mode",    "Alterna entre vista de framework completa y vista de proyecto"),
        ("alias-manager",     "Gestión de alias",   "Crea, edita y elimina alias personalizados para comandos"),
        ("env-manager",       "Variables de entorno","Gestiona .env del proyecto con validación y diff"),
        ("personality-panel", "Perfil del agente",  "Configura el tono, verbosidad y estilo del agente BAGO"),
        ("version",           "Versión del sistema","Versión actual de BAGO con changelog y notas de upgrade"),
        ("setup",             "Configuración inicial","Wizard de configuración inicial de BAGO en un nuevo sistema"),
        ("install",           "Instalar BAGO",      "Instala BAGO en un repositorio externo"),
    ]),
    ("🛠️  Infraestructura", [
        ("net-scan",      "Escaneo de red",      "Descubre puertos y servicios activos en la red local"),
        ("ping-server",   "Check de servicio",   "Verifica disponibilidad y latencia de un endpoint"),
        ("state-manager", "Gestor de estado",    "Split, materialize y merge del estado por capas"),
        ("seed",          "Semillas del sistema", "Gestiona las semillas de conocimiento del motor BAGO"),
        ("notify-desktop","Notificación desktop", "Envía notificación al sistema operativo"),
        ("notify-bago",   "Notificación BAGO",   "Envía notificación interna al sistema de presencia"),
        ("build-clean",   "Limpiar build",       "Elimina artefactos de build: __pycache__, dist, .eggs"),
        ("build-run",     "Ejecutar build",      "Ejecuta el pipeline de build del proyecto activo"),
    ]),
]

SIDEBAR_W = 20
PREVIEW_H = 6


# ── Sub-opciones modal ────────────────────────────────────────────────────────

def _draw_subopts(stdscr: "curses._CursesWindow", cmd: str,
                  opts: list[tuple[str, str, str]]) -> str | None:
    """Modal centrado para elegir sub-opción/flag de un comando.
    opts: [(args_a_añadir, etiqueta_corta, descripción)]
    Devuelve el comando completo elegido o None si se cancela.
    """
    h, w = stdscr.getmaxyx()
    lbl_w = max(len(o[1]) for o in opts) + 2
    title = f" bago {cmd} — elige una opción "
    modal_w = min(max(len(title) + 4, lbl_w + 50), w - 4)
    modal_h = len(opts) + 6
    my = max(1, (h - modal_h) // 2)
    mx = max(1, (w - modal_w) // 2)
    sel = 0

    while True:
        # Fondo semitransparente (sobreescribe área del modal)
        for row in range(my, min(my + modal_h, h - 1)):
            try:
                stdscr.addstr(row, mx, " " * (modal_w - 1), curses.color_pair(6))
            except curses.error:
                pass

        # Borde
        try:
            stdscr.addstr(my, mx, "┌" + title + "─" * max(0, modal_w - len(title) - 2) + "┐",
                          curses.color_pair(4) | curses.A_BOLD)
            for row in range(my + 1, my + modal_h - 1):
                stdscr.addstr(row, mx, "│", curses.color_pair(4))
                stdscr.addstr(row, mx + modal_w - 1, "│", curses.color_pair(4))
            footer_row = my + modal_h - 2
            foot = "  ↑↓ elegir · Enter ejecutar · Esc cancelar"
            stdscr.addstr(footer_row, mx + 1, foot[:modal_w - 2], curses.color_pair(4))
            stdscr.addstr(my + modal_h - 1, mx,
                          "└" + "─" * (modal_w - 2) + "┘", curses.color_pair(4))
        except curses.error:
            pass

        # Opciones
        for i, (args, label, desc) in enumerate(opts):
            row = my + 2 + i
            if row >= my + modal_h - 2:
                break
            full = f"bago {cmd} {args}".strip()
            if i == sel:
                bar = f" ▶  {label:<{lbl_w}}  {desc}"
                try:
                    stdscr.addstr(row, mx + 1, bar[:modal_w - 2].ljust(modal_w - 2),
                                  curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass
            else:
                try:
                    stdscr.addstr(row, mx + 4, f"{label:<{lbl_w}}", curses.color_pair(5))
                    desc_x = mx + 4 + lbl_w + 2
                    stdscr.addstr(row, desc_x, desc[:mx + modal_w - desc_x - 2],
                                  curses.color_pair(2))
                except curses.error:
                    pass

        stdscr.refresh()
        key = stdscr.getch()

        if key == 27:               # Esc → cancelar
            return None
        elif key == curses.KEY_DOWN:
            sel = (sel + 1) % len(opts)
        elif key == curses.KEY_UP:
            sel = (sel - 1) % len(opts)
        elif key in (10, 13):       # Enter → ejecutar
            args = opts[sel][0]
            return f"bago {cmd} {args}".strip()


# ── Colores ───────────────────────────────────────────────────────────────────

def _init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,    -1)                 # activo / resaltado
    curses.init_pair(2, 8,                    -1)                 # dim
    curses.init_pair(3, curses.COLOR_BLACK,   curses.COLOR_CYAN)  # seleccionado con foco
    curses.init_pair(4, curses.COLOR_YELLOW,  -1)                 # títulos / footer
    curses.init_pair(5, curses.COLOR_GREEN,   -1)                 # nombre de comando
    curses.init_pair(6, curses.COLOR_WHITE,   -1)                 # texto normal
    curses.init_pair(8, curses.COLOR_MAGENTA, -1)                 # preview cmd
    curses.init_pair(9, curses.COLOR_BLACK,   curses.COLOR_YELLOW)# header bar


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


# ── Renderizado TUI ───────────────────────────────────────────────────────────

def _draw(stdscr: "curses._CursesWindow") -> str | None:
    _init_colors()
    curses.curs_set(0)

    active_group = 0
    active_cmd   = 0
    focus        = "sidebar"
    scroll_cmd   = 0
    result: str | None = None
    _prev_key    = None   # (group, cmd_idx) — cache key para live_data
    _cached_live: list[str] = []

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        list_x    = SIDEBAR_W + 1
        list_w    = w - list_x - 1
        list_area = h - PREVIEW_H - 3

        group_name, cmds = MENU[active_group]

        # Recarga live_data solo cuando cambia la selección
        _cur_key = (active_group, active_cmd)
        if _cur_key != _prev_key and 0 <= active_cmd < len(cmds):
            entry = cmds[active_cmd]
            _cached_live = _live_data(entry[0], entry[2])
            _prev_key = _cur_key

        # ── Header ───────────────────────────────────────────────────────────
        right = f" {active_group + 1}/{len(MENU)} · {group_name.split('  ', 1)[-1]} "
        stdscr.addstr(0, 0, " " * (w - 1), curses.color_pair(9))
        stdscr.addstr(0, 2, "BAGO", curses.color_pair(9) | curses.A_BOLD)
        stdscr.addstr(0, 7, "· Menú de Comandos", curses.color_pair(9))
        try:
            stdscr.addstr(0, w - len(right) - 1, right, curses.color_pair(9))
        except curses.error:
            pass

        # ── Sidebar de grupos ─────────────────────────────────────────────────
        for i, (gname, _) in enumerate(MENU):
            y = 2 + i
            if y >= h - PREVIEW_H - 2:
                break
            label = f" {gname}"[:SIDEBAR_W].ljust(SIDEBAR_W)
            if i == active_group:
                attr = (curses.color_pair(3) | curses.A_BOLD) if focus == "sidebar" else (curses.color_pair(1) | curses.A_BOLD)
                stdscr.addstr(y, 0, label, attr)
            else:
                stdscr.addstr(y, 0, label, curses.color_pair(2))

        # Separador vertical
        for y in range(1, h - 1):
            try:
                stdscr.addstr(y, SIDEBAR_W, "│", curses.color_pair(2))
            except curses.error:
                pass

        # ── Cabecera de lista ─────────────────────────────────────────────────
        gname_clean = group_name.split("  ", 1)[-1] if "  " in group_name else group_name
        stdscr.addstr(1, list_x, f" {gname_clean}  ({len(cmds)} comandos)"[:list_w], curses.color_pair(4) | curses.A_BOLD)
        stdscr.addstr(2, list_x, "─" * (list_w - 1), curses.color_pair(2))

        # ── Lista de comandos ─────────────────────────────────────────────────
        visible = cmds[scroll_cmd: scroll_cmd + list_area]
        for i, (cmd, short, _) in enumerate(visible):
            abs_i = scroll_cmd + i
            y = 3 + i
            if y >= h - PREVIEW_H - 1:
                break
            if abs_i == active_cmd and focus == "list":
                bar = f" ▶  bago {cmd}  ─  {short}"
                stdscr.addstr(y, list_x, bar[:list_w].ljust(list_w - 1), curses.color_pair(3) | curses.A_BOLD)
            elif abs_i == active_cmd:
                stdscr.addstr(y, list_x + 1, "▶ ", curses.color_pair(1))
                stdscr.addstr(y, list_x + 3, f"bago {cmd}", curses.color_pair(1) | curses.A_BOLD)
                desc_x = list_x + 3 + len(f"bago {cmd}") + 2
                if desc_x < w - 2:
                    stdscr.addstr(y, desc_x, short[:w - desc_x - 1], curses.color_pair(6))
            else:
                stdscr.addstr(y, list_x + 3, "bago ", curses.color_pair(2))
                stdscr.addstr(y, list_x + 8, cmd, curses.color_pair(5))
                desc_x = list_x + 8 + len(cmd) + 2
                if desc_x < w - 2:
                    stdscr.addstr(y, desc_x, short[:w - desc_x - 1], curses.color_pair(2))

        # Indicadores de scroll
        if scroll_cmd > 0:
            try:
                stdscr.addstr(3, w - 3, "↑", curses.color_pair(4))
            except curses.error:
                pass
        if scroll_cmd + list_area < len(cmds):
            try:
                stdscr.addstr(2 + list_area, w - 3, "↓", curses.color_pair(4))
            except curses.error:
                pass

        # ── Preview del comando seleccionado ──────────────────────────────────
        prev_y = h - PREVIEW_H - 1
        stdscr.addstr(prev_y, list_x, "─" * (list_w - 1), curses.color_pair(2))
        if 0 <= active_cmd < len(cmds):
            entry = cmds[active_cmd]
            cmd_name = entry[0]
            has_opts = len(entry) > 3 and entry[3]
            opts_hint = "  [opciones ▸]" if has_opts else ""
            stdscr.addstr(prev_y + 1, list_x + 1,
                          f"bago {cmd_name}{opts_hint}"[:list_w - 2],
                          curses.color_pair(8) | curses.A_BOLD)
            for li, ln in enumerate(_cached_live[:PREVIEW_H - 2]):
                try:
                    stdscr.addstr(prev_y + 2 + li, list_x + 1, ln[:list_w - 2], curses.color_pair(6))
                except curses.error:
                    pass

        # ── Footer ────────────────────────────────────────────────────────────
        footer = "  ↑↓ navegar  →/Tab: lista  ←: grupos  Enter: ejecutar  q: salir  "
        stdscr.addstr(h - 1, 0, footer[:w - 1], curses.color_pair(4))

        stdscr.refresh()

        # ── Input ─────────────────────────────────────────────────────────────
        key = stdscr.getch()

        if key in (ord('q'), 27):
            break
        elif focus == "sidebar":
            if key == curses.KEY_DOWN:
                active_group = (active_group + 1) % len(MENU)
                active_cmd = 0
                scroll_cmd = 0
            elif key == curses.KEY_UP:
                active_group = (active_group - 1) % len(MENU)
                active_cmd = 0
                scroll_cmd = 0
            elif key in (ord('\t'), curses.KEY_RIGHT, 10, 13):
                focus = "list"
        else:
            if key == curses.KEY_DOWN:
                active_cmd = _clamp(active_cmd + 1, 0, len(cmds) - 1)
                if active_cmd >= scroll_cmd + list_area:
                    scroll_cmd += 1
            elif key == curses.KEY_UP:
                active_cmd = _clamp(active_cmd - 1, 0, len(cmds) - 1)
                if active_cmd < scroll_cmd:
                    scroll_cmd -= 1
            elif key == curses.KEY_LEFT:
                focus = "sidebar"
            elif key == ord('\t'):
                active_group = (active_group + 1) % len(MENU)
                active_cmd = 0
                scroll_cmd = 0
                focus = "list"
            elif key in (10, 13):
                entry = cmds[active_cmd]
                cmd_name = entry[0]
                opts = entry[3] if len(entry) > 3 else None
                if opts:
                    chosen = _draw_subopts(stdscr, cmd_name, opts)
                    if chosen:
                        result = chosen
                        break
                    # Esc en modal → volver al menú sin ejecutar
                else:
                    result = f"bago {cmd_name}"
                    break

    return result


# ── Modo --list (no interactivo) ──────────────────────────────────────────────

def _cmd_list() -> int:
    use_color = sys.stdout.isatty()

    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if use_color else text

    for group_name, cmds in MENU:
        print()
        print(c("1;33", f"  {group_name}"))
        print(c("2", "  " + "─" * 52))
        for cmd, short, _ in cmds:
            print(f"  {c('1;32', f'bago {cmd}'):<35}  {c('2', short)}")
    print()
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def _startup_sequence() -> None:
    """Ejecuta el arranque mínimo antes de mostrar el menú:
    - workspace_selector: elige modo si no está ya configurado
    - record_project: registra este proyecto como reciente
    Solo en TTY interactivo; silencioso si los módulos no están disponibles.
    """
    tools = Path(__file__).parent
    try:
        import importlib.util as ilu

        def _load(name: str):
            spec = ilu.spec_from_file_location(name, tools / f"{name}.py")
            mod = ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        ws = _load("workspace_selector")
        ws.select(skip_if_set=True)

        rp = _load("recent_projects")
        rp.record_project()
    except Exception:
        pass  # Nunca bloquear el arranque del menú


def main() -> None:
    args = sys.argv[1:]

    if "--list" in args:
        sys.exit(_cmd_list())

    if not sys.stdout.isatty():
        print("bago menu requiere un terminal interactivo. Usa --list para salida de texto.")
        sys.exit(1)

    _startup_sequence()

    # ── Elección de modo: manual vs asistente ──────────────────────────────
    import importlib.util as _ilu
    _chat_mod = None
    try:
        _spec = _ilu.spec_from_file_location("bago_chat", Path(__file__).parent / "bago_chat.py")
        _chat_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_chat_mod)
    except Exception:
        pass

    choice = "manual"
    if _chat_mod:
        try:
            choice = curses.wrapper(_chat_mod._startup_choice_curses)
        except Exception:
            choice = "manual"

    if choice == "asistente" and _chat_mod:
        try:
            curses.wrapper(_chat_mod._chat_curses)
        except Exception:
            pass
        sys.exit(0)

    result = curses.wrapper(_draw)

    if result:
        print(f"\n  ▶  {result}\n")
        bago_script = ROOT / "bago"
        cmd_parts = result.split()[1:]
        if bago_script.exists():
            sys.exit(subprocess.run([sys.executable, str(bago_script)] + cmd_parts).returncode)
    else:
        sys.exit(0)


def _self_test() -> None:
    assert len(MENU) == 10, f"Se esperaban 10 grupos, hay {len(MENU)}"
    for group_name, cmds in MENU:
        assert cmds, f"Grupo '{group_name}' sin comandos"
        for entry in cmds:
            assert len(entry) in (3, 4), f"Entrada malformada en '{group_name}': {entry}"
            if len(entry) == 4 and entry[3]:
                for opt in entry[3]:
                    assert len(opt) == 3, f"Sub-opción malformada en '{entry[0]}': {opt}"
    total = sum(len(c) for _, c in MENU)
    opts_count = sum(1 for _, c in MENU for e in c if len(e) > 3 and e[3])
    print(f"  3/3 tests pasaron  ({len(MENU)} grupos, {total} entradas, {opts_count} con sub-opciones)")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
