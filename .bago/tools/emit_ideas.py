#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import unicodedata

# Windows UTF-8 fix: cp1252 can't encode checkmarks, emoji, box-drawing chars
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _norm(s: str) -> str:
    """Normaliza un título para comparación: minúsculas + sin diacríticos."""
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode("ascii")

ROOT = Path(__file__).resolve().parents[2]
# Rango de salida del selector: mínimo operativo y máximo de carga cognitiva.
# El selector SIEMPRE debe publicar entre MIN_IDEAS y MAX_IDEAS ideas por sesión.
# SELECTOR_RANGE_ENFORCED_IMPLEMENTED
MIN_IDEAS = 5
MAX_IDEAS = 20

DB_PATH = ROOT / ".bago" / "state" / "bago.db"
CATALOG_PATH = ROOT / ".bago" / "ideas_catalog.json"


# ── SQLite helpers ───────────────────────────────────────────────────────────

def _db_available() -> bool:
    return DB_PATH.exists()


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_implemented_titles_from_db() -> set[str]:
    """Devuelve títulos normalizados implementados registrados en bago.db."""
    if not _db_available():
        return set()
    try:
        conn = _db_conn()
        rows = conn.execute("SELECT idea_title FROM implemented_ideas").fetchall()
        conn.close()
        return {_norm(str(r["idea_title"])) for r in rows if r["idea_title"]}
    except Exception:
        return set()


def load_ideas_from_db(feat: dict, extra_flags: dict) -> list[dict] | None:
    """
    Carga ideas desde bago.db aplicando condiciones de features y extra_cond.
    Devuelve None si la BD no existe (fallback a código hardcodeado).
    Para cada slot numérico elige la idea de mayor generación cuyas condiciones pasen.
    """
    if not _db_available():
        return None
    try:
        conn = _db_conn()
        rows = conn.execute(
            "SELECT * FROM ideas WHERE status = 'available' ORDER BY slot NULLS LAST, generation DESC, priority DESC"
        ).fetchall()
        conn.close()
    except Exception:
        return None

    implemented_db = _load_implemented_titles_from_db() | load_implemented_titles()

    def _is_implemented(catalog_title: str) -> bool:
        """True si catalog_title coincide exacto O está contenido en algún
        título de implemented (cubre sufijos añadidos al registrar).
        # COSECHA_FILTER_IMPLEMENTED
        """
        n = _norm(catalog_title)
        if not n:
            return False
        if n in implemented_db:
            return True
        for impl in implemented_db:
            if n in impl:
                return True
        return False

    slot_seen: set[int] = set()
    result: list[dict] = []

    for row in rows:
        idea = dict(row)
        slot = idea["slot"]
        requires = json.loads(idea.get("requires") or "[]")
        blocks   = json.loads(idea.get("blocks")   or "[]")
        extra    = idea.get("extra_cond", "always")

        # Filtrar ideas ya implementadas (doble fuente: JSON + DB) — substring
        if _is_implemented(idea["title"]):
            continue

        # Evaluar feature gates
        if not all(feat.get(r) for r in requires):
            continue
        if any(feat.get(b) for b in blocks):
            continue

        # Evaluar condición extra
        if extra != "always" and not extra_flags.get(extra, False):
            continue

        if slot is not None:
            if slot in slot_seen:
                continue  # ya tenemos la mejor generación para este slot
            slot_seen.add(slot)

        # Convertir al formato que espera el resto del código
        result.append({
            "id":       idea.get("id", ""),
            "priority": idea["priority"],
            "section":  idea["section"],
            "risk":     idea["risk"],
            "title":    idea["title"],
            "summary":  idea["summary"],
            "metric":   idea.get("metric", ""),
            "w2":       idea.get("w2", ""),
            "detail":   json.loads(idea.get("detail") or "[]"),
        })

    result.sort(key=lambda x: (-x["priority"], x["title"]))
    return result


def _load_catalog() -> dict:
    """Carga ideas_catalog.json. Devuelve dict vacío si no existe o está corrupto."""
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def evaluate_catalog(catalog: dict, feat: dict) -> list[dict]:
    """Evalúa ideas desde bago.db con las feature flags dadas.
    El parámetro catalog se acepta por compatibilidad; las ideas vienen de la DB."""
    return load_ideas_from_db(feat, {}) or []


def apply_dynamic_scoring(ideas: list[dict]) -> list[dict]:
    """Alias público de _apply_dynamic_score para uso desde bago_next y otros módulos."""
    return _apply_dynamic_score(ideas)


def _load_global_state() -> dict:
    """Lee global_state.json; devuelve {} si no existe o está corrupto."""
    gs_file = ROOT / ".bago" / "state" / "global_state.json"
    try:
        return json.loads(gs_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _apply_dynamic_score(ideas: list[dict]) -> list[dict]:
    """
    Ajusta la prioridad de cada idea según señales del estado actual.

    Reglas base:
      +5  si no hay tarea activa (exploración libre)
      -10 si hay tarea activa (status != done) y risk == 'high' (no distraer)
      +5  si section == 'contextuales' (señal de relevancia)

    Reglas de registro:
      +4  si ninguna palabra clave del título coincide con ideas ya implementadas
      -4  si hay ≥2 palabras clave en común (área ya trabajada)

    Señales de global_state.json:
      +3  si system_health == 'green' (base estable, buena hora para añadir)
      +2  si sessions (inventory) > 5 (sistema con historial real)
      -5  si system_health == 'red' (estabilizar antes de añadir features)
      -3  si sessions == 0 y la idea no es de section 'mantenimiento'
           (sin historial aún, priorizar mantenimiento primero)

    Señales contextuales de workflow activo (# SCORING_CONTEXT_IMPLEMENTED):
      W2 (implementación): +3 si idea tiene keywords de implementación
      W4 (debug): +3 si idea tiene keywords de diagnóstico/arreglo
      W8 (exploración): +3 si idea tiene keywords exploratorias
      health_pct >= 80: +2 (base sana para nuevas features)
      health_pct < 50:  -3 (inestabilidad, priorizar arreglos)
    """
    # ── señal de tarea activa (status != done) ────────────────────────────────
    task_file = ROOT / ".bago" / "state" / "pending_w2_task.json"
    has_active_task = False
    if task_file.exists():
        try:
            tdata = json.loads(task_file.read_text(encoding="utf-8"))
            has_active_task = tdata.get("status") not in ("done", "closed")
        except Exception:
            has_active_task = True

    # ── señales de global_state ───────────────────────────────────────────────
    gs = _load_global_state()
    health        = str(gs.get("system_health", "")).lower()
    # Usar session_closes (artefactos .md) como proxy de historial; 'sessions' lo gestiona el validador
    session_closes = int(gs.get("inventory", {}).get("session_closes", 0))

    # Workflow activo y health_pct numérico
    active_workflow = str(gs.get("sprint_status", {}).get("active_workflow") or "").upper()
    try:
        health_pct = int(gs.get("guardian_findings", {}).get("health_pct") or 0)
    except (TypeError, ValueError):
        health_pct = 0

    _WF_KEYWORDS: dict[str, set[str]] = {
        "W2": {"implement", "mejora", "añadir", "registr", "cierre", "generar", "crea", "auto"},
        "W4": {"debug", "error", "fix", "bug", "arregl", "fallo", "problem", "correg"},
        "W8": {"explora", "investig", "analiz", "research", "diseño", "estudi", "plan"},
    }

    # ── palabras clave de ideas ya implementadas ──────────────────────────────
    impl_titles = load_implemented_titles()  # ya normalizadas con _norm()
    impl_keywords: set[str] = set()
    for t in impl_titles:
        impl_keywords.update(w for w in t.split() if len(w) > 4)

    for idea in ideas:
        delta = 0
        risk    = str(idea.get("risk", "")).lower()
        section = str(idea.get("section", "")).lower()
        title   = str(idea.get("title", ""))
        title_norm = _norm(title)

        # Reglas base de tarea activa
        if not has_active_task:
            delta += 5                       # explorar libremente
        elif risk == "high":
            delta -= 10                      # no distraer con alto riesgo

        # Preferir ideas contextuales
        if section == "contextuales":
            delta += 5

        # Scoring dinámico por registro
        if impl_keywords:
            idea_words = {w for w in title_norm.split() if len(w) > 4}
            overlap = idea_words & impl_keywords
            if not overlap:
                delta += 4                   # trabajo genuinamente nuevo
            elif len(overlap) >= 2:
                delta -= 4                   # área ya trabajada extensamente

        # Señales de global_state
        if health == "green":
            delta += 3                       # base sana, buena hora para features
        elif health == "red":
            delta -= 5                       # estabilizar primero

        if session_closes > 5:
            delta += 2                       # señales históricas disponibles
        elif session_closes == 0 and section != "mantenimiento":
            delta -= 3                       # sin historial: priorizar mantenimiento

        # Señales contextuales de workflow activo
        if active_workflow in _WF_KEYWORDS:
            wf_kw = _WF_KEYWORDS[active_workflow]
            title_words = set(title_norm.split())
            if any(any(w.startswith(kw) for w in title_words) for kw in wf_kw):
                delta += 3                   # alineado con el workflow activo

        # Health numérico
        if health_pct >= 80:
            delta += 2                       # base sana, momento de avanzar
        elif health_pct < 50 and health_pct > 0:
            delta -= 3                       # inestabilidad: priorizar estabilización

        idea["priority"] = int(idea.get("priority", 0)) + delta

    ideas.sort(key=lambda x: (-x["priority"], x["title"]))
    return ideas


def load_fallback_from_db() -> list[dict]:
    """Carga ideas de respaldo (sin slot) desde la BD para rellenar hasta MIN_IDEAS."""
    if not _db_available():
        return []
    try:
        conn = _db_conn()
        rows = conn.execute(
            "SELECT * FROM ideas WHERE slot IS NULL AND status = 'available' ORDER BY priority DESC"
        ).fetchall()
        conn.close()
        implemented_db = _load_implemented_titles_from_db() | load_implemented_titles()
        feat = detect_implemented_features()
        result = []
        for row in rows:
            idea = dict(row)  # sqlite3.Row → dict so .get() works
            if idea["title"] in implemented_db:
                continue
            requires = json.loads(idea.get("requires") or "[]")
            if not all(feat.get(r) for r in requires):
                continue
            blocks = json.loads(idea.get("blocks") or "[]")
            if any(feat.get(b) for b in blocks):
                continue
            result.append({
                "priority": idea["priority"],
                "section":  idea["section"],
                "risk":     idea["risk"],
                "title":    idea["title"],
                "summary":  idea["summary"],
                "metric":   idea.get("metric", ""),
                "w2":       idea.get("w2", ""),
                "detail":   json.loads(idea.get("detail") or "[]"),
            })
        return result
    except Exception:
        return []


# ── Hardcoded fallback (cuando no hay BD) ───────────────────────────────────

FALLBACK_IDEAS: list[dict[str, object]] = [
    {
        "priority": 66,
        "section": "respaldo",
        "risk": "low",
        "metric": "README y selector describen la misma ruta de arranque.",
        "title": "Alinear README con selector",
        "summary": "Hacer que la entrada humana y el selector de ideas expliquen el mismo recorrido sin ambiguedades.",
        "detail": [
            "Entrada: README y comandos cortos del pack.",
            "Salida: navegacion coherente entre ideas, WF y arranque.",
            "Ventaja: reduce la friccion en el primer paso de cada sesion.",
        ],
        "w2": "Actualizar la documentacion de entrada sin tocar la logica del selector.",
    },
    {
        "priority": 64,
        "section": "respaldo",
        "risk": "low",
        "blocks": ["selector_range_enforced"],
        "metric": "El selector siempre publica el rango 5-20 sin desviaciones.",
        "title": "Reforzar rango del selector",
        "summary": "Hacer explicito el limite de 5 a 20 ideas en la salida del selector.",
        "detail": [
            "Entrada: enumeracion actual del selector.",
            "Salida: reglas de cantidad visibles para el usuario.",
            "Ventaja: evita listas demasiado cortas o excesivas.",
        ],
        "w2": "Codificar el rango de salida en el selector y verificarlo con una ejecucion real.",
    },
    {
        "priority": 62,
        "section": "respaldo",
        "risk": "low",
        "blocks": ["compact_recommendation"],
        "metric": "La recomendacion final queda en una sola accion explícita.",
        "title": "Compactar recomendacion final",
        "summary": "Reducir la friccion del final del selector con una recomendacion mas directa.",
        "detail": [
            "Entrada: salida de ideas ya ordenadas.",
            "Salida: siguiente paso corto y visible.",
            "Ventaja: facilita pasar de idea a decision sin leer de nuevo toda la lista.",
        ],
        "w2": "Ajustar el texto final de `./ideas` sin alterar el ranking.",
    },
]



def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def parse_state_sections(state_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buffer: list[str] = []

    for line in state_text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip().lower()
            buffer = []
            continue
        if current is not None:
            buffer.append(line)

    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def score(pairs: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return sorted(pairs, key=lambda item: (-item[0], item[1]))


def report_status(path: Path) -> dict | None:
    if not file_exists(path):
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def summarize_report(name: str, report: dict | None) -> str:
    if not report:
        return f"{name}: no disponible"
    status = report.get("status", report.get("overall_status", "unknown"))
    return (
        f"{name}: status={status}, "
        f"failures={report.get('failure_count', 'n/a')}, "
        f"workers={report.get('workers', 'n/a')}, "
        f"duration={report.get('duration_seconds', 'n/a')}s"
    )


def order_ideas_by_section(sections: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    return sections["contextuales"] + sections["respaldo"]


# ── canonical gate ─────────────────────────────────────────────────────────────

def run_canonical_gate(smoke_path: Path) -> tuple[bool, list[str], list[str]]:
    """Run validate_pack + validate_state and check smoke if available.

    Returns (all_passed, ko_messages, warn_messages).
    KO on any canonical validator failure or if smoke is available but failing.
    WARN (non-blocking) if smoke is unavailable.
    """
    bago_tools = ROOT / ".bago" / "tools"
    ko: list[str] = []
    warn: list[str] = []

    for script in ("validate_pack.py", "validate_state.py"):
        result = subprocess.run(
            [sys.executable, str(bago_tools / script)],
            capture_output=True,
            text=True,
        )
        out_lines = [l for l in (result.stdout + result.stderr).splitlines() if l.strip()]
        if result.returncode != 0:
            # Find the detail error line (comes after KO) or the KO line itself
            error_line = ""
            for i, line in enumerate(out_lines):
                if line.strip().startswith("KO") and i + 1 < len(out_lines):
                    error_line = out_lines[i + 1]
                    break
                if any(kw in line for kw in ("mismatch", "missing", "error", "Error", "reference found", "unknown")):
                    error_line = line
                    break
            if not error_line:
                error_line = out_lines[-1] if out_lines else script
            ko.append(f"  [KO] ✗ {script}: {error_line}")
        else:
            first_line = out_lines[-1] if out_lines else script
            warn.append(f"  [GO] ✓ {script}: {first_line}")

    smoke_report = report_status(smoke_path)
    if smoke_report is None:
        warn.append("  [WARN] ⚠ smoke: no disponible (no bloqueante)")
    else:
        smoke_status = str(smoke_report.get("status", "unknown")).lower()
        if smoke_status in ("pass", "ok", "green", "success") and smoke_report.get("failure_count", 1) == 0:
            warn.append(f"  [GO] ✓ smoke: status={smoke_status}")
        else:
            ko.append(f"  [KO] ✗ smoke: status={smoke_status}, failures={smoke_report.get('failure_count', 'n/a')}")

    return len(ko) == 0, ko, warn


def filter_ideas_for_baseline_mode(items: list[dict[str, object]]) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for item in items:
        risk = str(item.get("risk", "")).lower().strip()
        metric = str(item.get("metric", "")).strip()
        if risk != "low":
            continue
        if not metric:
            continue
        filtered.append(item)
    return filtered


def detect_implemented_features() -> dict[str, bool]:
    """Detecta qué ideas ya están implementadas inspeccionando el filesystem."""
    tools = ROOT / ".bago" / "tools"
    state = ROOT / ".bago" / "state"
    bago_readme = ROOT / ".bago" / "README.md"
    banner_text = (tools / "bago_banner.py").read_text(encoding="utf-8") if (tools / "bago_banner.py").exists() else ""
    show_task_text = (tools / "show_task.py").read_text(encoding="utf-8") if (tools / "show_task.py").exists() else ""

    gate_in_code = (
        (tools / "validate_pack.py").exists()
        and (tools / "validate_state.py").exists()
    )

    # session_closes_counted: session_close_*.md artefactos > 0 (campo dedicado para no romper el validador)
    try:
        gs = json.loads((state / "global_state.json").read_text(encoding="utf-8"))
        session_closes_counted = int(gs.get("inventory", {}).get("session_closes", 0)) > 0
    except Exception:
        session_closes_counted = False

    # catalog_exhaustion_handled: la guía de renovación usa un sentinel explícito
    # para no detectar su propia definición en este mismo archivo.
    emit_text = Path(__file__).read_text(encoding="utf-8")
    catalog_exhaustion_handled = "# CATALOG_RENEWAL_GUIDE_IMPLEMENTED" in emit_text

    return {
        "handoff_w2":                (tools / "show_task.py").exists(),
        "stability_cmd":             (tools / "stability_summary.py").exists(),
        "ideas_wrapper":             (ROOT / "ideas").exists(),
        "gate_in_code":              gate_in_code,
        "readme_aligned":            bago_readme.exists() and "bago stability" in bago_readme.read_text(encoding="utf-8"),
        "pending_task":              (state / "pending_w2_task.json").exists(),
        "session_opener":            (tools / "session_opener.py").exists(),
        "banner_shows_task":         "_active_task" in banner_text,
        "impl_registry":             (state / "implemented_ideas.json").exists(),
        # Slot 9: progreso visible
        "progress_in_banner":        "implementadas" in banner_text,
        # Slot 10: sesiones reales
        "session_closes_counted":    session_closes_counted,
        # Slot 11: cosecha post-tarea
        "cosecha_post_task":         "cosecha" in show_task_text.lower(),
        # Slot 12: guía de renovación + autorenovación
        "catalog_exhaustion_handled": catalog_exhaustion_handled,
        "auto_renew_active":          "# AUTO_RENEW_IMPLEMENTED" in emit_text,
        # Slot 13: dashboard con ideas
        "dashboard_shows_ideas":      "ideas_summary" in (
            (tools / "pack_dashboard.py").read_text(encoding="utf-8")
            if (tools / "pack_dashboard.py").exists() else ""),
        # Slot 14: resumen automático de sprint
        "sprint_summary_auto":        len(list(state.glob("sprint_summary_*.md"))) > 0,
        # Slot 15: ideas personalizadas
        "custom_ideas_cli":           "--add" in emit_text,
        # Slot 16: health score real
        "health_score_real":          "session_closes" in (
            (tools / "health_score.py").read_text(encoding="utf-8")
            if (tools / "health_score.py").exists() else ""),
        # Slot 11 gen 2: cosecha con ideas del sprint
        "cosecha_sprint_ideas":       "# COSECHA_SPRINT_IDEAS_IMPLEMENTED" in (
            (tools / "cosecha.py").read_text(encoding="utf-8")
            if (tools / "cosecha.py").exists() else ""),
        # Slots 17-21: wave 3 features
        "sprint_velocity":            "# SPRINT_VELOCITY_IMPLEMENTED" in (
            (tools / "sprint_summary.py").read_text(encoding="utf-8")
            if (tools / "sprint_summary.py").exists() else ""),
        "health_in_banner":           "# HEALTH_IN_BANNER_IMPLEMENTED" in banner_text,
        "cosecha_health_compare":     "# COSECHA_HEALTH_COMPARE_IMPLEMENTED" in (
            (tools / "cosecha.py").read_text(encoding="utf-8")
            if (tools / "cosecha.py").exists() else ""),
        "ideas_exportable":           "--export" in (
            (tools / "sprint_summary.py").read_text(encoding="utf-8")
            if (tools / "sprint_summary.py").exists() else ""),
        "catalog_guide_added":        '"_guide"' in (
            (ROOT / ".bago" / "ideas_catalog.json").read_text(encoding="utf-8")
            if (ROOT / ".bago" / "ideas_catalog.json").exists() else ""),
        # Slot 13 gen 2: historial de ideas en dashboard
        "ideas_history_in_dashboard": "recent" in (
            (tools / "pack_dashboard.py").read_text(encoding="utf-8")
            if (tools / "pack_dashboard.py").exists() else ""),
        # Wave 4 features
        "velocity_in_dashboard":      "# VELOCITY_IN_DASHBOARD_IMPLEMENTED" in (
            (tools / "pack_dashboard.py").read_text(encoding="utf-8")
            if (tools / "pack_dashboard.py").exists() else ""),
        "cosecha_health_trend":       "# COSECHA_HEALTH_TREND_IMPLEMENTED" in (
            (tools / "cosecha.py").read_text(encoding="utf-8")
            if (tools / "cosecha.py").exists() else ""),
        "catalog_in_stability":       "catalog_status" in (
            (tools / "stability_summary.py").read_text(encoding="utf-8")
            if (tools / "stability_summary.py").exists() else ""),
        "full_sprint_in_stability":   "# FULL_SPRINT_IN_STABILITY_IMPLEMENTED" in (
            (tools / "stability_summary.py").read_text(encoding="utf-8")
            if (tools / "stability_summary.py").exists() else ""),
        "banner_compact_mode":        "# BANNER_COMPACT_MODE_IMPLEMENTED" in banner_text,
        "dashboard_export_link":      "# DASHBOARD_EXPORT_LINK_IMPLEMENTED" in (
            (tools / "pack_dashboard.py").read_text(encoding="utf-8")
            if (tools / "pack_dashboard.py").exists() else ""),
        # Slot 1 gen 3: Cierre automático de sesión
        "close_auto":                 "session_close_generator" in (
            (tools / "show_task.py").read_text(encoding="utf-8")
            if (tools / "show_task.py").exists() else ""),
        # Slot 2 gen 3: Alerta de task obsoleta
        "banner_stale_alert":         "task obsoleta" in banner_text or "stale_msg" in banner_text,
        # Slot 3 gen 1: Gate seguro antes de implementar — stability_cmd suffices
        "stable_reports":             (tools / "stability_summary.py").exists(),
        # Slot 3 gen 3+: Scoring dinámico por registro
        "scoring_dynamic":            "_apply_dynamic_score" in Path(__file__).read_text(encoding="utf-8"),
        # Slot 3 gen 4: Ranking contextual por estado — not yet implemented
        "scoring_context":            "# SCORING_CONTEXT_IMPLEMENTED" in Path(__file__).read_text(encoding="utf-8"),
        # Slot 4+: repo with at least one commit
        "repo_not_empty":             (ROOT / ".git" / "COMMIT_EDITMSG").exists(),
        # Slot 4 gen 2: README enlaza ideas con W2 — README mentions W2 handoff
        "readme_flow_section":        "W2" in (
            (ROOT / ".bago" / "README.md").read_text(encoding="utf-8")
            if (ROOT / ".bago" / "README.md").exists() else ""),
        # Reabrir desde continuidad: bago reopen command
        "reopen_from_continuity":     "# REOPEN_FROM_CONTINUITY_IMPLEMENTED" in (
            (tools / "bago_reopen.py").read_text(encoding="utf-8")
            if (tools / "bago_reopen.py").exists() else ""),
        # Entrada rápida del repo: bago next shortcut in ideas footer
        "quick_repo_entry":           "# QUICK_REPO_ENTRY_IMPLEMENTED" in Path(__file__).read_text(encoding="utf-8"),
        # Reforzar rango del selector: MIN/MAX constants explicitly documented
        "selector_range_enforced":    "# SELECTOR_RANGE_ENFORCED_IMPLEMENTED" in Path(__file__).read_text(encoding="utf-8"),
        # Compactar recomendacion final: single-line compact footer
        "compact_recommendation":     "# COMPACT_RECOMMENDATION_IMPLEMENTED" in Path(__file__).read_text(encoding="utf-8"),
        # Delegar análisis a agentes en ciclo W2: code-quality in bago_next.py
        "agent_delegation_loop":      "# AGENT_DELEGATION_LOOP_IMPLEMENTED" in (
            (tools / "bago_next.py").read_text(encoding="utf-8")
            if (tools / "bago_next.py").exists() else ""),
        # Verificar cabinet al cerrar tarea: cabinet check in show_task.py --done
        "cabinet_on_close":           "# CABINET_ON_CLOSE_IMPLEMENTED" in (
            (tools / "show_task.py").read_text(encoding="utf-8")
            if (tools / "show_task.py").exists() else ""),
        # bago hello sugiere reopen si hay sesión previa
        "reopen_in_hello":            "# REOPEN_IN_HELLO_IMPLEMENTED" in (
            (tools / "bago_hello.py").read_text(encoding="utf-8")
            if (tools / "bago_hello.py").exists() else ""),
        "intent_filter_ideas":        "# INTENT_FILTER_IMPLEMENTED" in (
            Path(__file__).read_text(encoding="utf-8")),
        "dry_run_next":               "# DRY_RUN_NEXT_IMPLEMENTED" in (
            (tools / "bago_next.py").read_text(encoding="utf-8")
            if (tools / "bago_next.py").exists() else ""),
        "bago_diff_sessions":         "# BAGO_DIFF_SESSIONS_IMPLEMENTED" in (
            (tools / "bago_diff.py").read_text(encoding="utf-8")
            if (tools / "bago_diff.py").exists() else ""),
        "ideas_export":               "# IDEAS_EXPORT_IMPLEMENTED" in (
            Path(__file__).read_text(encoding="utf-8")),
        "auto_commit_hint":           "# AUTO_COMMIT_HINT_IMPLEMENTED" in (
            (tools / "show_task.py").read_text(encoding="utf-8")
            if (tools / "show_task.py").exists() else ""),
    }


def load_implemented_titles() -> set[str]:
    """Devuelve el conjunto de títulos normalizados de ideas ya registradas como implementadas."""
    impl_file = ROOT / ".bago" / "state" / "implemented_ideas.json"
    if not impl_file.exists():
        return set()
    try:
        data = json.loads(impl_file.read_text(encoding="utf-8"))
        entries = list(data.get("implemented") or []) + list(data.get("ideas_completed") or [])
        return {_norm(str(e.get("title", ""))) for e in entries}
    except Exception:
        return set()


def build_idea_sections(items: list[dict[str, object]], done_titles: set[str] | None = None) -> dict[str, list[dict[str, object]]]:
    if done_titles is None:
        done_titles = set()
    contextual = [
        item
        for item in items
        if str(item.get("section", "contextuales")) == "contextuales"
    ]
    contextual = sorted(contextual, key=lambda item: (-int(item["priority"]), str(item["title"])))
    contextual = contextual[:MAX_IDEAS]

    # Collect non-contextual items already present in items (e.g. DB respaldo ideas)
    respaldo: list[dict[str, object]] = [
        item for item in items
        if str(item.get("section", "contextuales")) != "contextuales"
    ]

    # Fill from hardcoded FALLBACK_IDEAS only if still below minimum, filtering blocked ones
    if len(contextual) + len(respaldo) < MIN_IDEAS:
        feat = detect_implemented_features()
        seen_titles = {_norm(str(item["title"])) for item in contextual + respaldo} | done_titles
        for fallback in FALLBACK_IDEAS:
            if len(contextual) + len(respaldo) >= MIN_IDEAS:
                break
            title = _norm(str(fallback["title"]))
            if title in seen_titles:
                continue
            fb_blocks = fallback.get("blocks", [])
            if any(feat.get(b) for b in fb_blocks):
                continue
            respaldo.append(dict(fallback))
            seen_titles.add(title)

    respaldo = sorted(respaldo, key=lambda item: (-int(item["priority"]), str(item["title"])))
    # Hard cap: total must not exceed MAX_IDEAS
    total = len(contextual) + len(respaldo)
    if total > MAX_IDEAS:
        respaldo = respaldo[:MAX_IDEAS - len(contextual)]
    return {"contextuales": contextual, "respaldo": respaldo}


def _auto_renew_catalog() -> int:
    """
    Reconstruye bago.db desde ideas_catalog.json para descubrir nuevas generaciones/slots.
    # AUTO_RENEW_IMPLEMENTED
    Devuelve el nuevo número de ideas disponibles tras la reconstrucción, o -1 si falla.
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "db_init", Path(__file__).resolve().parent / "db_init.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.reset_ideas()
        return 0   # señal OK; el caller recarga ideas
    except Exception:
        return -1


def print_sectioned_ideas(sections: dict[str, list[dict[str, object]]]) -> None:
    total = len(sections["contextuales"]) + len(sections["respaldo"])
    range_label = f"[rango: {MIN_IDEAS}–{MAX_IDEAS}]"
    if total < MIN_IDEAS:
        range_status = f"⚠ {total} ideas — por debajo del mínimo ({MIN_IDEAS})  {range_label}"
    elif total > MAX_IDEAS:
        range_status = f"⚠ {total} ideas — por encima del máximo ({MAX_IDEAS})  {range_label}"
    else:
        range_status = f"✓ dentro del rango  {range_label}"
    print(
        f"Total ideas: {total} "
        f"(contextuales={len(sections['contextuales'])}, respaldo={len(sections['respaldo'])})  {range_status}"
    )
    if total < MIN_IDEAS:
        # CATALOG_RENEWAL_GUIDE_IMPLEMENTED
        print(f"  💡  Para renovar el catálogo: python bago db reset-ideas")
        print(f"  💡  Para añadir ideas nuevas: edita .bago/ideas_catalog.json y ejecuta db reset-ideas")
    counter = 1
    for item in order_ideas_by_section(sections):
        w2 = str(item.get("w2", "Sin siguiente paso definido"))
        has_metric = bool(str(item.get("metric", "")).strip())
        metric_badge = " 📊" if has_metric else " ⚠️sin métrica"
        print(f"{counter}. [{item['priority']}] {item['title']}{metric_badge}")
        print(f"   descripcion: {item['summary']}")
        print(f"   siguiente paso: {w2}")
        print("")
        counter += 1


def render_handoff(selected: dict[str, object]) -> list[str]:
    title = str(selected["title"])
    summary = str(selected["summary"])
    detail = [str(line) for line in selected["detail"]]  # type: ignore[index]
    w2 = str(selected["w2"])
    metric = str(selected.get("metric", "")).strip()

    if title == "Handoff idea -> W2":
        objective = "Convertir una idea seleccionada en una tarea lista para implementar."
        scope = "Generar una salida accionable al aceptar una idea sin tocar el ranking ni el detalle."
        non_scope = "No cambia la selección, el scoring ni los reports de estabilidad."
        files = [
            ".bago/tools/emit_ideas.py",
        ]
        validation = [
            "`./ideas --detail 1` mantiene la salida actual.",
            "`./ideas --accept 1` imprime objetivo, alcance, no alcance, archivos candidatos y validación.",
            "`./ideas` sin flags conserva el selector existente.",
        ]
    else:
        objective = summary
        scope = "Materializar la idea seleccionada con el menor cambio suficiente."
        non_scope = "No expandir el alcance fuera de la idea elegida."
        files = [".bago/tools/emit_ideas.py"]
        validation = [
            "La salida debe explicar el cambio, los archivos y la verificación mínima.",
        ]
        if metric:
            validation.append(f"Métrica objetivo: {metric}")

    lines = [
        "- Handoff:",
        f"  - Objetivo: {objective}",
        f"  - Alcance: {scope}",
        f"  - No alcance: {non_scope}",
        f"  - Archivos candidatos: {', '.join(files)}",
        "  - Validación mínima:",
    ]
    lines.extend(f"    - {item}" for item in validation)
    lines.append(f"  - Siguiente paso: {w2}")
    if detail:
        lines.append("  - Contexto de la idea:")
        lines.extend(f"    - {line}" for line in detail)
    return lines


def build_handoff_data(selected: dict[str, object], index: int) -> dict[str, object]:
    """Construye el dict estructurado del handoff para persistir en disco."""
    title = str(selected["title"])
    summary = str(selected["summary"])
    detail = [str(line) for line in selected["detail"]]  # type: ignore[index]
    w2 = str(selected["w2"])
    metric = str(selected.get("metric", "")).strip()
    priority = int(str(selected.get("priority", 0)))

    if title == "Handoff idea -> W2":
        objective = "Convertir una idea seleccionada en una tarea lista para implementar."
        scope = "Generar una salida accionable al aceptar una idea sin tocar el ranking ni el detalle."
        non_scope = "No cambia la selección, el scoring ni los reports de estabilidad."
        files = [".bago/tools/emit_ideas.py"]
        validation = [
            "`./ideas --detail 1` mantiene la salida actual.",
            "`./ideas --accept 1` imprime objetivo, alcance, no alcance, archivos candidatos y validación.",
            "`./ideas` sin flags conserva el selector existente.",
        ]
    else:
        objective = summary
        scope = "Materializar la idea seleccionada con el menor cambio suficiente."
        non_scope = "No expandir el alcance fuera de la idea elegida."
        files = [".bago/tools/emit_ideas.py"]
        validation = ["La salida debe explicar el cambio, los archivos y la verificación mínima."]
        if metric:
            validation.append(f"Métrica objetivo: {metric}")

    return {
        "idea_index": index,
        "idea_title": title,
        "priority": priority,
        "workflow": "W2_IMPLEMENTACION_CONTROLADA",
        "objetivo": objective,
        "alcance": scope,
        "no_alcance": non_scope,
        "archivos_candidatos": files,
        "validacion_minima": validation,
        "siguiente_paso": w2,
        "metric": metric,
        "contexto": detail,
        "status": "pending",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
    }


def save_handoff(data: dict[str, object]) -> Path:
    """Escribe el handoff en .bago/state/pending_w2_task.json y devuelve la ruta."""
    dest = ROOT / ".bago" / "state" / "pending_w2_task.json"
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


_INTENT_TO_SECTION: dict[str, str] = {
    "implementar": "contextuales",
    "depurar":     "deuda",
    "cerrar":      "ciclo",
    "respaldo":    "respaldo",
}


def parse_args(argv: list[str]) -> tuple[int | str | None, bool, bool, bool, str | None, bool, bool]:
    detail_index = None
    accept = False
    select = False
    baseline = False
    intent: str | None = None
    export = False
    health = False
    idx = 1

    while idx < len(argv):
        arg = argv[idx]
        if arg in {"-h", "--help"}:
            print(
                "Usage: emit_ideas.py [--detail N] [--accept N] [--select] [--baseline] "
                "[--intent TYPE] [--export] [--health]\n\n"
                "Show 5 to 20 contextual ideas prioritized by stability. Use --detail "
                "to expand a selected idea, --accept to mark it ready for W2, "
                "--select for the interactive slot selector, --baseline for "
                "low-risk ideas only, --intent to filter by type "
                "(implementar, depurar, cerrar, respaldo), --export to write "
                "ideas_snapshot.md to .bago/state/, or --health to show catalog stats."
            )
            raise SystemExit(0)
        if arg == "--select":
            select = True
            idx += 1
            continue
        if arg == "--baseline":
            baseline = True
            idx += 1
            continue
        if arg == "--health":
            health = True
            idx += 1
            continue
        if arg == "--intent":
            if idx + 1 >= len(argv):
                raise SystemExit("--intent requires a type: implementar, depurar, cerrar, respaldo")
            intent = argv[idx + 1]
            idx += 2
            continue
        if arg == "--export":
            export = True
            idx += 1
            continue
        if arg == "--detail":
            if idx + 1 >= len(argv):
                raise SystemExit("--detail requires a numeric idea index or idea ID")
            raw = argv[idx + 1]
            detail_index = int(raw) if raw.isdigit() else raw
            idx += 2
            continue
        if arg == "--accept":
            if idx + 1 >= len(argv):
                raise SystemExit("--accept requires a numeric idea index or idea ID")
            raw = argv[idx + 1]
            detail_index = int(raw) if raw.isdigit() else raw
            accept = True
            idx += 2
            continue
        raise SystemExit(f"Unknown argument: {arg}")

    return detail_index, accept, select, baseline, intent, export, health


def _show_catalog_health() -> int:
    """Muestra estadísticas del catálogo de ideas desde bago.db."""
    if not _db_available():
        print("  ✗ bago.db no encontrado — sin datos de catálogo.")
        return 1

    conn = _db_conn()
    try:
        # Estadísticas de ideas por status
        rows = conn.execute("SELECT status, COUNT(*) as n FROM ideas GROUP BY status").fetchall()
        by_status: dict[str, int] = {r["status"]: r["n"] for r in rows}
        total_ideas = sum(by_status.values())

        # Ideas implementadas en tabla implemented_ideas
        try:
            impl_count = conn.execute("SELECT COUNT(*) FROM implemented_ideas").fetchone()[0]
        except Exception:
            impl_count = 0

        # Ideas por sección (solo disponibles)
        sections = conn.execute(
            "SELECT section, COUNT(*) as n FROM ideas WHERE status='available' GROUP BY section ORDER BY n DESC"
        ).fetchall()

        # Guardian runs
        try:
            grun = conn.execute(
                "SELECT health_pct, run_date FROM guardian_runs ORDER BY run_date DESC LIMIT 1"
            ).fetchone()
        except Exception:
            grun = None
    finally:
        conn.close()

    available = by_status.get("available", 0)
    blocked   = by_status.get("blocked", 0)
    done      = by_status.get("done", 0)
    other     = total_ideas - available - blocked - done

    bar_avail  = "█" * min(available, 40)
    bar_done   = "░" * min(impl_count, 40)

    print("📊  bago ideas --health — estado del catálogo")
    print("=" * 48)
    print(f"  Total ideas en DB  : {total_ideas}")
    print(f"  Disponibles        : {available:3d}  {bar_avail}")
    print(f"  Implementadas      : {impl_count:3d}  {bar_done}")
    print(f"  Bloqueadas         : {blocked}")
    if done:
        print(f"  Marcadas done (DB) : {done}")
    if other:
        print(f"  Otros estados      : {other}")
    print()

    if sections:
        print("  Disponibles por sección:")
        for s in sections:
            print(f"    {s['section']:<20} {s['n']:3d}")
        print()

    # Rango operativo
    status_icon = "✅" if available >= MIN_IDEAS else "⚠️ "
    print(f"  Rango operativo    : {MIN_IDEAS}–{MAX_IDEAS}  →  {status_icon} {available} disponibles")
    if available < MIN_IDEAS:
        print(f"  💡 Ejecuta: bago db reset-ideas  para renovar el catálogo")

    if grun:
        print(f"  Último guardian    : {grun['health_pct']}%  ({grun['run_date']})")

    print()
    return 0


def _build_ideas_hardcoded(
    feat: dict,
    stable_reports: bool,
    baseline_clean_mode: bool,
    sections: dict,
    matrix: dict | None,
    repo_lines: int,
) -> list[dict[str, object]]:
    """Construye las ideas hardcodeadas (fallback cuando no hay bago.db)."""
    ideas: list[dict[str, object]] = []

    # Slot 1: Handoff W2 → Opener → Cierre automático
    if not feat["handoff_w2"]:
        ideas.append({"priority": 90, "section": "contextuales", "risk": "low",
            "metric": "El handoff incluye objetivo, alcance, no alcance, archivos y validación mínima.",
            "title": "Handoff idea -> W2",
            "summary": "Añadir una plantilla de salida que convierta una idea seleccionada en tarea lista para implementar con alcance, archivos y validación.",
            "detail": ["Entrada: una idea elegida tras revisar el selector.",
                       "Salida: objetivo, alcance, archivos candidatos y validación mínima.",
                       "Ventaja: reduce la fricción entre ideación e implementación."],
            "w2": "Pasar la idea elegida a W2 con un alcance pequeño y un criterio de salida claro."})
    elif not feat["session_opener"]:
        ideas.append({"priority": 90, "section": "contextuales", "risk": "low",
            "metric": "bago session lee pending_w2_task.json y lanza session_preflight con objetivo, roles y artefactos pre-rellenados.",
            "title": "Opener de sesión desde task",
            "summary": "Añadir `bago session` que lee el handoff aceptado y abre la sesión W2 con preflight pre-rellenado, evitando trabajo manual.",
            "detail": ["Entrada: pending_w2_task.json con objetivo, archivos y validación.",
                       "Salida: llamada a session_preflight.py con los datos del handoff.",
                       "Ventaja: elimina el paso manual de copiar datos del handoff al preflight."],
            "w2": "Implementar bago session en el script raíz delegando en session_preflight.py."})
    else:
        ideas.append({"priority": 90, "section": "contextuales", "risk": "low",
            "metric": "bago task --done genera y guarda automáticamente el artefacto de cierre de sesión.",
            "title": "Cierre automático de sesión",
            "summary": "Al marcar la tarea como done, generar automáticamente el artefacto de cierre con resumen de cambios y evidencias.",
            "detail": ["Entrada: tarea W2 completada (pending_w2_task.json con status=done).",
                       "Salida: artefacto de cierre con resumen, CHG/EVD generados y estado actualizado.",
                       "Ventaja: elimina el paso manual de redactar el cierre después de implementar."],
            "w2": "Extender show_task.py --done para llamar al generador de cierre de sesión."})

    # Slot 2: Stability → Banner → Stale task alert
    if not feat["stability_cmd"]:
        ideas.append({"priority": 86, "section": "contextuales", "risk": "low",
            "metric": "El resumen incluye estado de smoke, VM y soak en un único bloque.",
            "title": "Resumen único de estabilidad",
            "summary": "Consolidar smoke, VM y soak en un informe corto para decidir si una idea nueva compite con estabilidad antes de tocar código.",
            "detail": ["Entrada: los últimos reports del sandbox.",
                       "Salida: un resumen de salud operacional para decidir si conviene proponer cambios.",
                       "Ventaja: evita idear sobre una base ya inestable."],
            "w2": "Si el resumen está en verde, permitir avanzar a una idea concreta."})
    elif not feat["banner_shows_task"]:
        ideas.append({"priority": 86, "section": "contextuales", "risk": "low",
            "metric": "El banner muestra el estado de la tarea W2 activa (título + estado) si pending_w2_task.json existe.",
            "title": "Banner muestra task activa",
            "summary": "Mostrar en el banner de BAGO si hay una tarea W2 pendiente o completada, para visibilidad inmediata al arrancar.",
            "detail": ["Entrada: pending_w2_task.json si existe.",
                       "Salida: línea extra en el banner con título y estado (⏳/✅).",
                       "Ventaja: el usuario sabe al abrir BAGO si tiene trabajo en curso."],
            "w2": "Leer pending_w2_task.json en bago_banner.py y añadir línea condicional al banner."})
    else:
        ideas.append({"priority": 86, "section": "contextuales", "risk": "low",
            "metric": "bago stability y el banner alertan si la task lleva más de 3 días sin completarse.",
            "title": "Alerta de task obsoleta",
            "summary": "Si pending_w2_task.json lleva más de 3 días sin marcarse done, mostrar aviso en banner y en bago stability.",
            "detail": ["Entrada: pending_w2_task.json con campo accepted_at.",
                       "Salida: aviso visual (⚠️) en banner y en stability cuando la task supera 3 días.",
                       "Ventaja: evita que tareas abiertas queden olvidadas."],
            "w2": "Añadir lógica de antigüedad en bago_banner.py y stability_summary.py."})

    # Slot 3: Gate → Registro → Scoring dinámico
    if not feat["gate_in_code"] and stable_reports:
        ideas.append({"priority": 84, "section": "contextuales", "risk": "low",
            "metric": "Ninguna idea avanza si validate_pack/validate_state/smoke no están en verde.",
            "title": "Gate seguro antes de implementar",
            "summary": "Bloquear sugerencias nuevas si validate_pack, validate_state o smoke no están en verde.",
            "detail": ["Entrada: validadores canónicos y smoke del sandbox.",
                       "Salida: permiso o bloqueo para seguir ideando e implementar.",
                       "Ventaja: protege la estabilidad antes de abrir trabajo nuevo."],
            "w2": "Si el gate pasa, la idea elegida puede convertirse en W2."})
    elif feat["gate_in_code"] and not feat["impl_registry"]:
        ideas.append({"priority": 84, "section": "contextuales", "risk": "low",
            "metric": "El selector no repite una idea marcada como implementada en implemented_ideas.json.",
            "title": "Registro de ideas implementadas",
            "summary": "Guardar en estado qué ideas ya fueron implementadas para que el selector evolucione en lugar de repetirlas en cada sesión.",
            "detail": ["Entrada: lista de ideas aceptadas e implementadas.",
                       "Salida: archivo .bago/state/implemented_ideas.json con IDs y fechas.",
                       "Ventaja: el selector siempre propone trabajo nuevo, no repetido."],
            "w2": "Crear implemented_ideas.json y leerlo en emit_ideas para filtrar ideas ya hechas."})
    elif feat["impl_registry"]:
        ideas.append({"priority": 84, "section": "contextuales", "risk": "low",
            "metric": "El scoring de ideas sube cuando la feature que proponen no está en implemented_ideas.json.",
            "title": "Scoring dinámico por registro",
            "summary": "Ajustar la prioridad de las ideas en función de si la feature que proponen ya fue implementada, incrementando el score de las que aportan trabajo nuevo.",
            "detail": ["Entrada: implemented_ideas.json con historial de ideas completadas.",
                       "Salida: ideas reordenadas priorizando trabajo genuinamente nuevo.",
                       "Ventaja: el selector se vuelve más preciso con el tiempo."],
            "w2": "Leer implemented_ideas.json en emit_ideas y aplicar penalización de score a ideas similares ya hechas."})

    if matrix and matrix.get("status") == "pass":
        ideas.append({"priority": 82, "section": "contextuales", "risk": "medium",
            "metric": "WF responde por intención y reduce navegación manual.",
            "title": "Selector por intención",
            "summary": "Extender WF para filtrar ideas y workflows por intención, por ejemplo idea, implementar, depurar o cerrar.",
            "detail": ["Entrada: intención del usuario.",
                       "Salida: selector más fino para aterrizar al workflow correcto.",
                       "Ventaja: evita navegar manualmente cuando la intención ya está clara."],
            "w2": "Usar la intención seleccionada para orientar la tarea siguiente."})

    if baseline_clean_mode:
        ideas.append({"priority": 78, "section": "contextuales", "risk": "low",
            "metric": "Cada idea aceptada declara una mejora medible en trazabilidad u operación.",
            "title": "Ideas orientadas a baseline",
            "summary": "Proponer solo cambios que mantengan el baseline limpio y generen un incremento medible en trazabilidad u operacion.",
            "detail": ["Entrada: baseline limpio y estable.",
                       "Salida: ideas pequeñas con mejora mensurable.",
                       "Ventaja: alinea la ideación con la continuidad del pack."],
            "w2": "Seleccionar una idea que preserve el baseline y tenga bajo riesgo."})

    if sections.get("cierre de sesión"):
        ideas.append({"priority": 74, "section": "contextuales", "risk": "medium",
            "metric": "Reapertura evita reconstrucción manual y reduce pasos de arranque.",
            "title": "Reabrir desde continuidad",
            "summary": "Añadir un modo para reactivar la sesión desde el cierre actual sin reconstruir contexto manualmente.",
            "detail": ["Entrada: cierre de sesión ya escrito en estado.",
                       "Salida: reanudación más rápida sin perder contexto.",
                       "Ventaja: mantiene continuidad de trabajo entre sesiones."],
            "w2": "Si se acepta, convertirlo en una mejora pequeña y segura de continuidad."})

    if repo_lines > 0:
        ideas.append({"priority": 70, "section": "contextuales", "risk": "medium",
            "metric": "La primera decisión del usuario llega a una acción en un paso.",
            "title": "Entrada rápida del repo",
            "summary": "Conectar ideas con README y WF para que la primera decisión del usuario vaya a una acción concreta sin leer toda la canonica.",
            "detail": ["Entrada: comandos cortos y selector de workflows.",
                       "Salida: menos fricción para abrir ideas o W2.",
                       "Ventaja: mejora la usabilidad diaria del repo."],
            "w2": "Promover la idea seleccionada a una tarea corta y directa."})

    ideas.append({"priority": 68, "section": "contextuales", "risk": "medium",
        "metric": "El ranking refleja señales de estado actual y reduce recomendaciones estáticas.",
        "title": "Mejorar ranking de ideas",
        "summary": "Ajustar el scoring para reflejar señales del estado actual y evitar prioridades estáticas que oculten trabajo real.",
        "detail": ["Entrada: estado BAGO, salud de reports y workflow activo.",
                   "Salida: orden de ideas más sensible al contexto operativo.",
                   "Ventaja: reduce sesgos de ranking y evita ciclos de recomendación."],
        "w2": "Implementar un ranking contextual acotado y validarlo con ejemplos reales del estado."})

    return ideas


def _export_ideas_snapshot(ideas: list[dict]) -> Path:
    """Escribe ideas_snapshot.md en .bago/state/ y devuelve la ruta."""
    # # IDEAS_EXPORT_IMPLEMENTED
    from datetime import datetime, timezone
    out = ROOT / ".bago" / "state" / "ideas_snapshot.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# BAGO Ideas — snapshot {now}\n"]
    for i, idea in enumerate(ideas, 1):
        title   = idea.get("title", "—")
        summary = idea.get("summary", "")
        w2      = idea.get("w2", "")
        prio    = idea.get("priority", "?")
        lines.append(f"## {i}. [{prio}] {title}\n")
        if summary:
            lines.append(f"{summary}\n")
        if w2:
            lines.append(f"**Siguiente paso:** {w2}\n")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    detail_index, accept, select, baseline_flag, intent_filter, export_flag, health_flag = parse_args(sys.argv)  # INTENT_FILTER_IMPLEMENTED

    # ── Modo --health: estadísticas del catálogo ─────────────────────────────
    if health_flag:
        return _show_catalog_health()

    # ── Modo selector interactivo ────────────────────────────────────────────
    if select:
        import ideas_selector
        ideas_selector.main()
        return 0
    state_path = ROOT / ".bago/state/ESTADO_BAGO_ACTUAL.md"
    global_state_path = ROOT / ".bago/state/global_state.json"
    smoke_path = ROOT / "sandbox/runtime/last-report.json"
    vm_path = ROOT / "sandbox/runtime-vm/last-report-vm.json"
    soak_path = ROOT / "sandbox/runtime-vm/last-soak-report-vm.json"
    matrix_path = ROOT / "sandbox/runtime-vm/matrix/last-matrix-summary.json"
    readme_path = ROOT / "README.md"

    # ── canonical gate ─────────────────────────────────────────────────────────
    gate_passed, gate_ko, gate_warn = run_canonical_gate(smoke_path)
    if not gate_passed:
        print("BAGO ideas selector — GATE KO")
        print("=" * 44)
        print("Validadores canónicos en fallo. Repara antes de idear.")
        print("")
        for msg in gate_ko:
            print(msg)
        for msg in gate_warn:
            print(msg)
        print("")
        print("KO → ninguna idea avanza. Ejecuta `bago stability` para el detalle.")
        return 1
    # ── /gate ──────────────────────────────────────────────────────────────────

    state_text = read_text(state_path) if file_exists(state_path) else ""
    sections = parse_state_sections(state_text)
    global_state = load_json(global_state_path) if file_exists(global_state_path) else {}

    smoke = report_status(smoke_path)
    vm = report_status(vm_path)
    soak = report_status(soak_path)
    matrix = report_status(matrix_path)

    repo_lines = 0
    if file_exists(readme_path):
        repo_lines = len(read_text(readme_path).splitlines())

    # --baseline flag fuerza modo baseline independientemente de global_state
    baseline_clean_mode = baseline_flag or (global_state.get("baseline_status") == "active_clean_core")
    feat = detect_implemented_features()

    stable_reports = all(
        report and report.get("status") == "pass" and report.get("failure_count", 1) == 0
        for report in (smoke, vm, soak)
        if report is not None
    )

    _state_dir = ROOT / ".bago" / "state"
    _has_session_close_files = bool(list(_state_dir.glob("session_close_*.md"))) if _state_dir.exists() else False

    extra_flags = {
        "stable_reports":    stable_reports,
        "matrix_pass":       bool(matrix and matrix.get("status") == "pass"),
        "baseline_clean":    baseline_clean_mode,
        "has_session_close": bool(sections.get("cierre de sesión")) or _has_session_close_files,
        "has_readme":        repo_lines > 0,
    }

    # ── Cargar ideas: SQLite si existe, hardcoded como fallback ───────────────
    ideas_from_db = load_ideas_from_db(feat, extra_flags)
    using_db = ideas_from_db is not None

    if using_db:
        ideas: list[dict[str, object]] = ideas_from_db  # type: ignore[assignment]
    else:
        ideas = _build_ideas_hardcoded(feat, stable_reports, baseline_clean_mode,
                                        sections, matrix, repo_lines)

    if baseline_clean_mode:
        ideas = filter_ideas_for_baseline_mode(ideas)

    # Filtrar ideas cuyo título ya fue registrado como implementado
    done_titles = load_implemented_titles()
    if done_titles:
        ideas = [i for i in ideas if _norm(str(i.get("title", ""))) not in done_titles]

    # Ajuste dinámico de score según estado actual
    ideas = _apply_dynamic_score(ideas)

    # ── Filtro por intención (--intent) ──────────────────────────────────────
    if intent_filter:
        target_section = _INTENT_TO_SECTION.get(intent_filter, intent_filter)
        ideas = [i for i in ideas if str(i.get("section", "")) == target_section]
        if not ideas:
            print(f"  (sin ideas disponibles para --intent {intent_filter!r})")
            return 0

    # Rellenar con fallback hasta MIN_IDEAS si hay pocas (no aplica con --intent)
    if not intent_filter and len(ideas) < MIN_IDEAS:
        fallback_pool = load_fallback_from_db() if using_db else list(FALLBACK_IDEAS)
        seen = {_norm(str(i.get("title", ""))) for i in ideas} | done_titles
        for fb in fallback_pool:
            if len(ideas) >= MIN_IDEAS:
                break
            fb_title = _norm(str(fb.get("title", "")))
            if fb_title not in seen:
                ideas.append(fb)
                seen.add(fb_title)

    idea_sections = build_idea_sections(ideas, done_titles=done_titles)
    ideas = order_ideas_by_section(idea_sections)

    # ── Autorenovación: si < MIN_IDEAS rebuild DB y recarga ───────────────────
    _auto_renewed = False
    _total_after_fill = len(idea_sections["contextuales"]) + len(idea_sections["respaldo"])
    if _total_after_fill < MIN_IDEAS and using_db:
        _result = _auto_renew_catalog()
        if _result == 0:
            _auto_renewed = True
            # Recargar con el catálogo reconstruido
            ideas_from_db = load_ideas_from_db(feat, extra_flags)
            if ideas_from_db is not None:
                ideas = ideas_from_db
                if baseline_clean_mode:
                    ideas = filter_ideas_for_baseline_mode(ideas)
                ideas = [i for i in ideas if _norm(str(i.get("title", ""))) not in done_titles]
                ideas = _apply_dynamic_score(ideas)
                # Re-rellenar con fallback
                if len(ideas) < MIN_IDEAS:
                    fallback_pool = load_fallback_from_db()
                    seen2 = {_norm(str(i.get("title", ""))) for i in ideas} | done_titles
                    for fb in fallback_pool:
                        if len(ideas) >= MIN_IDEAS:
                            break
                        fb_title = _norm(str(fb.get("title", "")))
                        if fb_title not in seen2:
                            ideas.append(fb)
                            seen2.add(fb_title)
                idea_sections = build_idea_sections(ideas, done_titles=done_titles)
                ideas = order_ideas_by_section(idea_sections)

    print("BAGO ideas selector")
    if using_db:
        print(f"  fuente: bago.db ({DB_PATH.name})")
    if _auto_renewed:
        print("  🔄  catálogo renovado automáticamente")

    # Auto-generar sprint summaries si hay sprints completos sin resumen
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("sprint_summary", Path(__file__).parent / "sprint_summary.py")
        _smod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_smod)
        _new_summaries = _smod.generate_if_due()
        for _sp in _new_summaries:
            print(f"  📋 Sprint summary generado: {_sp.name}")
    except Exception:
        pass
    if baseline_clean_mode:
        print("  modo: --baseline activo — solo ideas low-risk con métrica medible")
        if baseline_flag:
            print("  (forzado por flag --baseline)")
    print("")
    print_sectioned_ideas(idea_sections)

    if export_flag:
        snap = _export_ideas_snapshot(ideas)
        print(f"\n  📄 Exportado: {snap}")

    print("")
    if detail_index is None:
        if ideas:
            top = ideas[0]
            # COMPACT_RECOMMENDATION_IMPLEMENTED — recomendacion directa en dos líneas
            print(f"→ [{top['priority']}] {top['title']}  ·  bago ideas --accept 1")
            # QUICK_REPO_ENTRY_IMPLEMENTED — acceso directo de un paso a W2
            print(f"  ↳ Acceso rápido: bago next  (acepta y abre W2 en un solo comando)")
        else:
            print("→ No hay ideas disponibles. Revisa el backlog o añade más al catálogo.")
        return 0

    # ── Resolver ID string → posición numérica ───────────────────────────────
    if isinstance(detail_index, str):
        idea_id = detail_index
        resolved = next(
            (i + 1 for i, idea in enumerate(ideas) if idea.get("id") == idea_id),
            None,
        )
        if resolved is None:
            raise SystemExit(f"Idea ID '{idea_id}' no encontrada en las ideas disponibles")
        detail_index = resolved

    if detail_index < 1 or detail_index > len(ideas):
        raise SystemExit(f"Invalid idea index: {detail_index}")

    selected = ideas[detail_index - 1]
    print(f"Selected idea: {detail_index}. {selected['title']}")
    for line in selected["detail"]:
        print(f"- {line}")
    print(f"- Next step: {selected['w2']}")
    if accept:
        metric = str(selected.get("metric", "")).strip()
        if not metric:
            print("- Status: RECHAZADA — sin métrica medible")
            print("")
            print("Esta idea no declara una mejora medible en trazabilidad u operación.")
            print("Para aceptarla, la idea debe tener un campo 'metric' no vacío.")
            print("Elige una idea que declare un incremento concreto y verificable.")
            return 1
        print("- Status: accepted for W2")
        print("- Workflow: run `make workflow-tactical NAME=W2`")
        for line in render_handoff(selected):
            print(line)
        handoff_data = build_handoff_data(selected, detail_index)
        saved_path = save_handoff(handoff_data)
        print(f"\n→ Tarea guardada en {saved_path.relative_to(ROOT)}")
        print("  Consulta con: bago task")
    else:
        print("- Status: awaiting acceptance")
        print(f"- If you want to accept it, run `./ideas --accept {detail_index}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
