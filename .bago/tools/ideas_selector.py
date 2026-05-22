#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ideas_selector.py — Selector interactivo de ideas BAGO agrupadas por slot.

Uso:
    python bago ideas --select
    python bago select

Entrada del usuario:
    3           → plan para la idea con índice 3
    slot 2      → plan para todo el slot 2 (todas las generaciones)
    1,4,14      → plan para las ideas 1, 4 y 14
    q / Enter   → salir
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / ".bago" / "state" / "bago.db"
IMPLEMENTED_FILE = ROOT / ".bago" / "state" / "implemented_ideas.json"


def _normalize_title(t: str) -> str:
    """Normaliza título para comparación: lowercase + strip + collapse spaces."""
    if not t:
        return ""
    return " ".join(str(t).lower().split())


def _load_implemented_keys() -> tuple[set[str], set[str]]:
    """Carga sets de (titles_normalizados, ids) desde implemented_ideas.json.

    Soporta los dos campos coexistentes del schema:
      · implemented      → [{title, slot, done_at}]
      · ideas_completed  → [{id, title, date, ...}]

    Retorna (titles_set, ids_set). Devuelve sets vacíos si el fichero no existe
    o no se puede leer (no rompe el selector).
    # COSECHA_FILTER_IMPLEMENTED
    """
    titles: set[str] = set()
    ids: set[str] = set()
    if not IMPLEMENTED_FILE.exists():
        return titles, ids
    try:
        data = json.loads(IMPLEMENTED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return titles, ids
    for entry in (data.get("implemented") or []):
        t = _normalize_title(entry.get("title"))
        if t:
            titles.add(t)
    for entry in (data.get("ideas_completed") or []):
        t = _normalize_title(entry.get("title"))
        if t:
            titles.add(t)
        i = entry.get("id")
        if i:
            ids.add(str(i))
    return titles, ids


# ── Helpers de DB ────────────────────────────────────────────────────────────

def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _detect_features() -> dict[str, bool]:
    """Importa detect_implemented_features desde emit_ideas para reutilizarla."""
    try:
        sys.path.insert(0, str(ROOT / ".bago" / "tools"))
        from emit_ideas import detect_implemented_features
        return detect_implemented_features()
    except Exception:
        return {}


def _extra_flags(feat: dict[str, bool]) -> dict[str, bool]:
    state = ROOT / ".bago" / "state"
    tools = ROOT / ".bago" / "tools"
    smoke = state / "smoke_report.json"
    baseline_flag = state / "baseline_mode.flag"
    matrix_path = state / "matrix_report.json"
    return {
        "always":           True,
        "stable_reports":   smoke.exists(),
        "matrix_pass":      matrix_path.exists(),
        "baseline_clean":   baseline_flag.exists(),
        "has_session_close": any((state).glob("session_close_*.md")),
        "has_readme":       (ROOT / ".bago" / "README.md").exists(),
    }


# ── Carga de ideas ────────────────────────────────────────────────────────────

def _availability(idea: dict, feat: dict[str, bool], extra: dict[str, bool]) -> tuple[str, str]:
    """
    Devuelve (status, reason):
        "available"   — todas las condiciones pasan
        "locked"      — falta una feature (requires/blocks)
        "conditional" — extra_cond no cumple
    """
    requires = json.loads(idea.get("requires") or "[]")
    blocks   = json.loads(idea.get("blocks")   or "[]")
    ec       = idea.get("extra_cond", "always")

    missing = [r for r in requires if not feat.get(r)]
    blocking = [b for b in blocks if feat.get(b)]

    if missing:
        return "locked", "req: " + ", ".join(missing)
    if blocking:
        return "locked", "bloq: " + ", ".join(blocking)
    if ec != "always" and not extra.get(ec, False):
        return "conditional", ec
    return "available", ""


def load_all_ideas() -> tuple[list[dict], dict[str, bool], dict[str, bool]]:
    """
    Carga TODAS las ideas de bago.db sin filtrar, evaluando disponibilidad.
    Devuelve (ideas, feat, extra_flags).

    Las ideas que aparecen en implemented_ideas.json se marcan con
    _status="implemented" y se EXCLUYEN del retorno por defecto. Esto
    cierra el ciclo catálogo ↔ implemented y evita que ideas ya cerradas
    sigan dominando el ranking.
    # COSECHA_FILTER_IMPLEMENTED
    """
    feat = _detect_features()
    extra = _extra_flags(feat)

    if not DB_PATH.exists():
        return [], feat, extra

    conn = _db_conn()
    rows = conn.execute(
        "SELECT * FROM ideas ORDER BY slot NULLS LAST, generation ASC, priority DESC"
    ).fetchall()
    conn.close()

    impl_titles, impl_ids = _load_implemented_keys()

    ideas = []
    for row in rows:
        idea = dict(row)
        # Excluir ideas ya implementadas (por id O por substring de título).
        # Substring porque al registrar implementadas a veces se añaden
        # sufijos ("— sidecar W9", "(bago health)", etc.) que rompen una
        # comparación exacta. El catalog title es siempre más corto y está
        # contenido en el implemented title, no al revés, así que aplicamos
        # "catalog_title in implemented_title".
        idea_id = str(idea.get("id") or "")
        cat_title = _normalize_title(idea.get("title"))
        is_implemented = (idea_id and idea_id in impl_ids)
        if not is_implemented and cat_title:
            for impl_title in impl_titles:
                if cat_title in impl_title:
                    is_implemented = True
                    break
        if is_implemented:
            continue
        status, reason = _availability(idea, feat, extra)
        idea["_status"] = status    # "available" | "locked" | "conditional"
        idea["_reason"] = reason
        idea["_requires_list"] = json.loads(idea.get("requires") or "[]")
        idea["_blocks_list"]   = json.loads(idea.get("blocks")   or "[]")
        ideas.append(idea)

    return ideas, feat, extra


def group_by_slot(ideas: list[dict]) -> dict:
    """Devuelve dict: slot (int|None) → [ideas ordenadas por gen]."""
    groups: dict = {}
    for idea in ideas:
        slot = idea["slot"]
        groups.setdefault(slot, []).append(idea)
    # Ordenar slots: primero numéricos ascendente, luego None
    ordered: dict = {}
    for slot in sorted((k for k in groups if k is not None)) + [None]:
        if slot in groups:
            ordered[slot] = groups[slot]
    return ordered


# ── Render de la pantalla ─────────────────────────────────────────────────────

SLOT_NAMES = {
    1: "Flujo de tarea completo",
    2: "Visibilidad del sistema",
    3: "Calidad del ciclo de ideas",
    4: "Selector por intención",
    5: "Ideas orientadas a baseline",
    6: "Reabrir desde continuidad",
    7: "Entrada rápida del repo",
    8: "Ranking contextual",
}

STATUS_ICON = {
    "available":   "[OK]",
    "locked":      "[--]",
    "conditional": "[ ?]",
}


def render_display(ideas: list[dict]) -> tuple[str, dict[int, dict]]:
    """
    Construye la pantalla de selección.
    Devuelve (texto, index_map) donde index_map: número (1-based) → idea.
    """
    groups = group_by_slot(ideas)
    lines: list[str] = []
    index_map: dict[int, dict] = {}
    counter = 1

    lines.append("")
    lines.append("=" * 66)
    lines.append("  BAGO - Selector de Ideas")
    lines.append("=" * 66)

    for slot, slot_ideas in groups.items():
        lines.append("")
        if slot is not None:
            name = SLOT_NAMES.get(slot, f"Slot {slot}")
            prio = slot_ideas[0]["priority"] if slot_ideas else ""
            lines.append(f"  SLOT {slot} [{prio}] -- {name}")
            lines.append("  " + "-" * 62)
        else:
            lines.append("  sin-slot -- Respaldo")
            lines.append("  " + "-" * 62)

        for idea in slot_ideas:
            idx = counter
            index_map[idx] = idea
            counter += 1

            icon = STATUS_ICON[idea["_status"]]
            gen_label = f"GEN {idea['generation']}" if idea.get("generation") else "   "
            title = idea["title"]
            reason = f"  ({idea['_reason']})" if idea["_reason"] else ""

            lines.append(f"  [{idx:2d}] {icon} {gen_label}  {title}{reason}")

    lines.append("")
    lines.append("=" * 66)
    lines.append("  Escribe:")
    lines.append("    <N>       -> plan para esa idea")
    lines.append("    slot <N>  -> plan para el slot N completo")
    lines.append("    <N>,<M>   -> plan para varias ideas")
    lines.append("    q / intro -> salir")
    lines.append("=" * 66)
    lines.append("")

    return "\n".join(lines), index_map


# ── Parseo de selección ───────────────────────────────────────────────────────

def parse_selection(line: str, index_map: dict[int, dict], groups: dict) -> list[dict] | None:
    """
    Parsea la entrada del usuario y devuelve lista de ideas seleccionadas.
    Devuelve None si la entrada no es válida.
    """
    line = line.strip()
    if not line or line.lower() == "q":
        return []  # señal de salir

    # slot N
    if line.lower().startswith("slot "):
        try:
            slot_num = int(line.split()[1])
        except (IndexError, ValueError):
            return None
        slot_ideas = groups.get(slot_num)
        if not slot_ideas:
            return None
        return list(slot_ideas)

    # N,M,K  o  N
    try:
        indices = [int(x.strip()) for x in line.split(",")]
    except ValueError:
        return None

    result = []
    for i in indices:
        idea = index_map.get(i)
        if idea is None:
            return None
        result.append(idea)
    return result


# ── Render del plan ───────────────────────────────────────────────────────────

def _sort_by_dependencies(ideas: list[dict]) -> list[dict]:
    """Ordena las ideas seleccionadas respetando la cadena requires."""
    # Orden simple: primero por slot, luego por generation
    return sorted(
        ideas,
        key=lambda x: (
            x["slot"] if x["slot"] is not None else 999,
            x.get("generation") or 0,
        ),
    )


def render_plan(ideas: list[dict]) -> str:
    """Genera el plan de implementación para la lista de ideas seleccionadas."""
    if not ideas:
        return ""

    ordered = _sort_by_dependencies(ideas)
    lines: list[str] = []
    lines.append("")

    if len(ordered) == 1:
        idea = ordered[0]
        slot_label = f"SLOT {idea['slot']}" if idea["slot"] else "sin-slot"
        lines.append("=" * 66)
        lines.append(f"  Plan: {slot_label} GEN {idea.get('generation', '?')} -- {idea['title']}")
        lines.append("=" * 66)
    else:
        titles = ", ".join(i["title"] for i in ordered[:3])
        if len(ordered) > 3:
            titles += f" (+{len(ordered)-3} mas)"
        lines.append("=" * 66)
        lines.append(f"  Plan combinado: {len(ordered)} ideas")
        lines.append(f"  {titles}")
        lines.append("=" * 66)

    for idea in ordered:
        slot_label = f"SLOT {idea['slot']}" if idea["slot"] else "sin-slot"
        gen_label  = f"GEN {idea.get('generation', '?')}"
        lines.append("")
        lines.append(f"  {slot_label} {gen_label} -- {idea['title']}")
        lines.append("  " + "-" * 60)

        # Objetivo / descripción
        summary = idea.get("summary") or idea.get("description") or ""
        if summary:
            lines.append(f"  Objetivo : {_wrap(summary, 57, '             ')}")

        # W2 / siguiente paso
        w2 = idea.get("w2") or ""
        if w2:
            lines.append(f"  Paso W2  : {_wrap(w2, 57, '             ')}")

        # Métrica
        metric = idea.get("metric") or ""
        if metric:
            lines.append(f"  Metrica  : {_wrap(metric, 57, '             ')}")

        # Estado
        if idea["_status"] == "available":
            lines.append(f"  Estado   : [OK] DISPONIBLE")
        elif idea["_status"] == "locked":
            lines.append(f"  Estado   : [--] BLOQUEADA -- {idea['_reason']}")
        else:
            lines.append(f"  Estado   : [ ?] CONDICIONAL -- {idea['_reason']}")

        # Prerequisitos
        reqs = idea["_requires_list"]
        if reqs:
            lines.append(f"  Requiere : {', '.join(reqs)}")

    # Orden de implementación
    if len(ordered) > 1:
        lines.append("")
        lines.append("  Orden recomendado:")
        for n, idea in enumerate(ordered, 1):
            slot_label = f"SLOT {idea['slot']}" if idea["slot"] else "sin-slot"
            avail = "[OK]" if idea["_status"] == "available" else "[--]"
            lines.append(f"    {n}. {avail} {slot_label} GEN {idea.get('generation','?')} -- {idea['title']}")

    lines.append("")
    lines.append("=" * 66)
    return "\n".join(lines)


def _wrap(text: str, width: int, indent: str) -> str:
    """Ajuste de línea simple para texto largo."""
    if len(text) <= width:
        return text
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return ("\n" + indent).join(lines)


# ── Aceptar idea → pending_w2_task.json ──────────────────────────────────────

def _accept_idea(idea: dict) -> None:
    """Escribe pending_w2_task.json con los datos de la idea seleccionada."""
    import datetime
    task = {
        "title":      idea["title"],
        "objetivo":   idea.get("summary") or idea.get("title"),
        "alcance":    idea.get("w2") or "",
        "no_alcance": "",
        "archivos":   [],
        "validacion": idea.get("metric") or "",
        "status":     "pending",
        "source":     "ideas_selector",
        "slot":       idea.get("slot"),
        "generation": idea.get("generation"),
        "accepted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    out = ROOT / ".bago" / "state" / "pending_w2_task.json"
    out.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [OK] Task guardada en: {out.relative_to(ROOT)}")
    print(f"  Titulo: {task['title']}")
    print(f"  Siguiente: python bago session\n")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    # Encoding para emojis en Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ideas, feat, extra = load_all_ideas()

    if not ideas:
        print("[WARN] No hay ideas en bago.db. Ejecuta: python bago db init")
        return

    groups = group_by_slot(ideas)
    display, index_map = render_display(ideas)

    print(display)

    while True:
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            break

        if not raw or raw.lower() == "q":
            break

        selected = parse_selection(raw, index_map, groups)

        if selected is None:
            total = len(index_map)
            print(f"  [!] Entrada no valida. Usa: N (1-{total}), slot N, o N,M,K")
            continue

        if not selected:
            break

        plan_text = render_plan(selected)
        print(plan_text)

        # Ofrecer --accept si hay exactamente 1 idea disponible
        available = [i for i in selected if i["_status"] == "available"]
        if len(available) == 1 and len(selected) == 1:
            idea = available[0]
            try:
                ans = input(f"  Aceptar '{idea['title']}' como task W2? [s/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("")
                break
            if ans in ("s", "si", "sí", "y", "yes"):
                _accept_idea(idea)

        # Volver a mostrar display para nueva selección
        print(display)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo + filtro implemented."""
    from pathlib import Path as _P
    import tempfile
    assert _P(__file__).exists(), "fichero no encontrado"

    # Tests del filtro implemented (sin tocar disco real)
    fails: list[str] = []
    global IMPLEMENTED_FILE
    saved = IMPLEMENTED_FILE
    try:
        # Caso 1: fichero inexistente → sets vacíos, no rompe
        IMPLEMENTED_FILE = Path(tempfile.gettempdir()) / "__bago_does_not_exist__.json"
        titles, ids = _load_implemented_keys()
        if titles or ids:
            fails.append("sin fichero debería dar sets vacíos")

        # Caso 2: fichero válido con ambos campos
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({
                "implemented": [{"title": "Idea A", "slot": None, "done_at": "x"}],
                "ideas_completed": [{"id": "id_b", "title": "Idea B", "date": "y"}],
            }, f)
            tmp_path = f.name
        IMPLEMENTED_FILE = _P(tmp_path)
        titles, ids = _load_implemented_keys()
        if "idea a" not in titles:
            fails.append("título de implemented no normalizado al set")
        if "idea b" not in titles:
            fails.append("título de ideas_completed no en titles")
        if "id_b" not in ids:
            fails.append("id de ideas_completed no en ids")

        # Caso 3: título con espacios y caps → normalizado
        if _normalize_title("  Hola  Mundo  ") != "hola mundo":
            fails.append("normalize falla con espacios múltiples")
        if _normalize_title(None) != "":
            fails.append("normalize None debería dar ''")

        # Caso 4: JSON corrupto → sets vacíos, no rompe
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json}")
            corrupt = f.name
        IMPLEMENTED_FILE = _P(corrupt)
        titles, ids = _load_implemented_keys()
        if titles or ids:
            fails.append("JSON corrupto debería dar sets vacíos")
    finally:
        IMPLEMENTED_FILE = saved
        try: _P(tmp_path).unlink()
        except Exception: pass
        try: _P(corrupt).unlink()
        except Exception: pass

    if fails:
        for f in fails:
            print("  FAIL:", f)
        print(f"FAIL: {len(fails)} test(s)")
        raise SystemExit(1)
    print("  1/1 base + 4/4 filter-implemented tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
