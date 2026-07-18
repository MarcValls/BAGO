#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator_v4.py — BAGO Orchestrator

Implementa el Flujo Operativo General para Gestión de Tareas con Agentes.

Regla Fundamental: Orchestrator → Especialista Único → Orchestrator
Nunca: Especialista → Especialista → Especialista sin pasar por Orchestrator.

Fases:
  1. Orchestrator recibe tarea → genera TaskBrief
  2. Enrutamiento: un dominio, un responsable
  3. Especialista ejecuta su dominio
  4. Handoff formal si se necesita otro dominio
  5. Revisión del Orchestrator
  6. Cierre con criterios de aceptación

Uso:
    python .bago/tools/orchestrator_v4.py create --task "descripcion" [--root DIR]
    python .bago/tools/orchestrator_v4.py assign <brief_id> --agent <agente>
    python .bago/tools/orchestrator_v4.py handoff <brief_id> --to <dominio> --work "resumen"
    python .bago/tools/orchestrator_v4.py review <brief_id>
    python .bago/tools/orchestrator_v4.py close <brief_id>
    python .bago/tools/orchestrator_v4.py list [--status pending|assigned|in_progress|review|closed]
    python .bago/tools/orchestrator_v4.py show <brief_id>
    python .bago/tools/orchestrator_v4.py --test

Subcomando BAGO:
    bago orchestrate create --task "..."
    bago orchestrate list
    bago orchestrate review <id>
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import uuid
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from bago_utils import (
    get_scan_root,
    load_json,
    print_test_results,
    save_json,
    timestamp_iso,
)

# ── Constantes ────────────────────────────────────────────────────────────────

def _current_release_version() -> str:
    root = Path(__file__).resolve().parents[2]
    for candidate in (
        root / "release_version.txt",
        root / ".bago" / "release_version.txt",
    ):
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value.lstrip("vV").strip()
    versions_path = root / "versions.json"
    try:
        data = json.loads(versions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    current = data.get("current", "")
    return current.strip() if isinstance(current, str) else ""


VERSION = _current_release_version()
STATE_SUBDIR = "orchestrator"

PRIORITIES = {"P0", "P1", "P2", "Post-MVP"}
DOMAINS = {"Producto", "Backend", "Frontend", "Contenido", "Deployment"}
AGENTS = {"product_guardian", "backend", "frontend", "content", "deployment", "auto"}

TASK_STATUSES = (
    "pending",      # Fase 1: TaskBrief generado, sin asignar
    "assigned",     # Fase 2: enrutado a especialista
    "in_progress",  # Fase 3: especialista ejecutando
    "handoff",      # Fase 4: en tránsito entre dominios
    "review",       # Fase 5: en revisión del Orchestrator
    "closed",       # Fase 6: cerrado
    "rejected",     # Revisión fallida, requiere cambios
)

# Palabras clave para clasificar dominio automáticamente
DOMAIN_SIGNALS: dict[str, list[str]] = {
    "Backend": [
        "api", "endpoint", "base de datos", "database", "modelo", "modelo de datos",
        "schema", "sql", "rest", "servicio", "microservicio", "auth", "seguridad",
        "backend", "servidor", "contrato", "migration",
    ],
    "Frontend": [
        "ui", "interfaz", "pantalla", "componente", "react", "css", "html",
        "navegación", "ux", "diseño", "visual", "frontend", "layout", "menu",
        "botón", "formulario", "widget",
    ],
    "Deployment": [
        "deploy", "despliegue", "docker", "ci", "cd", "vercel", "pipeline",
        "infraestructura", "entorno", "variable de entorno", "kubernetes",
        "script de instalación", "release", "publish",
    ],
    "Contenido": [
        "catálogo", "plantilla", "recurso", "documentación", "configuración",
        "datos", "content", "texto", "copia", "template", "definición",
    ],
    "Producto": [
        "alcance", "roadmap", "mvp", "requisito", "prioridad", "feature",
        "funcionalidad", "historia de usuario", "criterio", "producto",
        "backlog", "sprint",
    ],
}

PRIORITY_SIGNALS: dict[str, list[str]] = {
    "P0": ["bloqueante", "crítico", "urgente", "caído", "roto", "broken", "falla crítica"],
    "P1": ["importante", "necesario", "esta semana", "sprint actual"],
    "P2": ["mejora", "nice to have", "optimización", "opcional"],
    "Post-MVP": ["futuro", "post-mvp", "después", "roadmap largo"],
}

# ── Paths ─────────────────────────────────────────────────────────────────────

SCAN_ROOT: Path = Path.cwd()
BAGO_ROOT: Path = SCAN_ROOT / ".bago"
ORC_DIR: Path = BAGO_ROOT / "state" / STATE_SUBDIR


def configure_paths(root_override: str | None = None) -> Path:
    global SCAN_ROOT, BAGO_ROOT, ORC_DIR
    SCAN_ROOT = get_scan_root(root_override)
    BAGO_ROOT = SCAN_ROOT / ".bago"
    ORC_DIR = BAGO_ROOT / "state" / STATE_SUBDIR
    ORC_DIR.mkdir(parents=True, exist_ok=True)
    return SCAN_ROOT


configure_paths()


# ── Estructuras de datos ───────────────────────────────────────────────────────

@dataclass
class TaskBrief:
    """Documento formal que inicia el ciclo de una tarea en el Orchestrator."""
    id: str
    task: str
    context: str
    objective: str
    priority: str                          # P0 / P1 / P2 / Post-MVP
    domain: str                            # Producto / Backend / Frontend / Contenido / Deployment
    scope: str
    exclusions: str
    acceptance_criteria: list[str]
    dependencies: list[str]
    agent: str                             # Especialista asignado
    status: str                            # ver TASK_STATUSES
    created_at: str
    updated_at: str
    handoffs: list[dict]                   # historial de handoffs
    review: dict                           # última revisión del Orchestrator

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TaskBrief":
        return cls(
            id=d.get("id", ""),
            task=d.get("task", ""),
            context=d.get("context", ""),
            objective=d.get("objective", ""),
            priority=d.get("priority", "P2"),
            domain=d.get("domain", "Producto"),
            scope=d.get("scope", ""),
            exclusions=d.get("exclusions", ""),
            acceptance_criteria=d.get("acceptance_criteria", []),
            dependencies=d.get("dependencies", []),
            agent=d.get("agent", ""),
            status=d.get("status", "pending"),
            created_at=d.get("created_at", timestamp_iso()),
            updated_at=d.get("updated_at", timestamp_iso()),
            handoffs=d.get("handoffs", []),
            review=d.get("review", {}),
        )


@dataclass
class Handoff:
    """Transferencia formal de trabajo entre dominios."""
    brief_id: str
    from_domain: str
    to_domain: str
    summary: str                      # Qué se ha realizado
    state: str                        # pendiente / parcial / completo
    artifacts: list[str]              # Artefactos entregados
    risks: list[str]                  # Riesgos detectados
    action_requested: str             # Trabajo exacto que continúa el siguiente
    timestamp: str = field(default_factory=timestamp_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RevisionFinal:
    """Revisión del Orchestrator al final del trabajo especializado."""
    brief_id: str
    scope_ok: bool
    criteria_met: list[str]           # criterios que sí se cumplieron
    criteria_failed: list[str]        # criterios que NO se cumplieron
    dependencies_resolved: bool
    pending_risks: list[str]
    result: str                       # "approved" / "changes_required" / "redirect"
    notes: str
    timestamp: str = field(default_factory=timestamp_iso)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Clasificación automática ───────────────────────────────────────────────────

def _infer_domain(task: str) -> str:
    text = task.lower()
    scores: dict[str, int] = {d: 0 for d in DOMAINS}
    for domain, keywords in DOMAIN_SIGNALS.items():
        for kw in keywords:
            if kw in text:
                scores[domain] += 1
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best] > 0 else "Producto"


def _infer_priority(task: str) -> str:
    text = task.lower()
    for prio, keywords in PRIORITY_SIGNALS.items():
        if any(kw in text for kw in keywords):
            return prio
    return "P2"


def _domain_to_agent(domain: str) -> str:
    mapping = {
        "Producto": "product_guardian",
        "Backend": "backend",
        "Frontend": "frontend",
        "Contenido": "content",
        "Deployment": "deployment",
    }
    return mapping.get(domain, "product_guardian")


def _brief_path(brief_id: str) -> Path:
    return ORC_DIR / f"{brief_id}.json"


def _generate_id() -> str:
    return uuid.uuid4().hex[:12]


# ── Persistencia ──────────────────────────────────────────────────────────────

def _load_brief(brief_id: str) -> TaskBrief | None:
    path = _brief_path(brief_id)
    if not path.exists():
        return None
    data = load_json(path)
    if not data:
        return None
    return TaskBrief.from_dict(data)


def _save_brief(brief: TaskBrief) -> None:
    brief.updated_at = timestamp_iso()
    save_json(_brief_path(brief.id), brief.to_dict())


def _list_briefs(status_filter: str | None = None) -> list[TaskBrief]:
    if not ORC_DIR.exists():
        return []
    briefs: list[TaskBrief] = []
    for f in sorted(ORC_DIR.glob("*.json")):
        try:
            data = load_json(f)
            b = TaskBrief.from_dict(data)
            if status_filter is None or b.status == status_filter:
                briefs.append(b)
        except Exception:
            continue
    return briefs


# ── Fase 1: Crear TaskBrief ───────────────────────────────────────────────────

def create_brief(
    task: str,
    context: str = "",
    objective: str = "",
    priority: str = "",
    domain: str = "",
    scope: str = "",
    exclusions: str = "",
    acceptance_criteria: list[str] | None = None,
    dependencies: list[str] | None = None,
) -> TaskBrief:
    """Fase 1 — Orchestrator crea TaskBrief formal a partir de la petición."""
    inferred_domain = domain if domain in DOMAINS else _infer_domain(task)
    inferred_priority = priority if priority in PRIORITIES else _infer_priority(task)
    inferred_agent = _domain_to_agent(inferred_domain)

    brief = TaskBrief(
        id=_generate_id(),
        task=task,
        context=context or f"Tarea recibida: {task}",
        objective=objective or task,
        priority=inferred_priority,
        domain=inferred_domain,
        scope=scope or f"Resolver: {task}",
        exclusions=exclusions or "Sin exclusiones explícitas.",
        acceptance_criteria=acceptance_criteria or [
            f"La tarea '{task}' está completada según el dominio {inferred_domain}.",
            "No se han introducido regresiones.",
            "El Orchestrator aprueba el resultado.",
        ],
        dependencies=dependencies or [],
        agent=inferred_agent,
        status="pending",
        created_at=timestamp_iso(),
        updated_at=timestamp_iso(),
        handoffs=[],
        review={},
    )
    _save_brief(brief)
    return brief


# ── Fase 2: Asignación ────────────────────────────────────────────────────────

def assign_brief(brief_id: str, agent: str | None = None) -> TaskBrief:
    """Fase 2 — Orchestrator asigna la tarea al especialista."""
    brief = _load_brief(brief_id)
    if brief is None:
        raise ValueError(f"Brief {brief_id!r} no encontrado.")
    if agent and agent in AGENTS:
        brief.agent = agent
    brief.status = "assigned"
    _save_brief(brief)
    return brief


# ── Fase 3 → 4: Handoff ──────────────────────────────────────────────────────

def create_handoff(
    brief_id: str,
    to_domain: str,
    summary: str,
    state: str = "parcial",
    artifacts: list[str] | None = None,
    risks: list[str] | None = None,
    action_requested: str = "",
) -> Handoff:
    """Fase 4 — Especialista genera Handoff formal. Vuelve al Orchestrator."""
    brief = _load_brief(brief_id)
    if brief is None:
        raise ValueError(f"Brief {brief_id!r} no encontrado.")
    if to_domain not in DOMAINS:
        raise ValueError(f"Dominio {to_domain!r} inválido. Opciones: {sorted(DOMAINS)}")

    handoff = Handoff(
        brief_id=brief_id,
        from_domain=brief.domain,
        to_domain=to_domain,
        summary=summary,
        state=state,
        artifacts=artifacts or [],
        risks=risks or [],
        action_requested=action_requested or f"Continuar en dominio {to_domain}.",
    )

    brief.handoffs.append(handoff.to_dict())
    brief.domain = to_domain
    brief.agent = _domain_to_agent(to_domain)
    brief.status = "handoff"
    _save_brief(brief)
    return handoff


# ── Fase 5: Revisión ──────────────────────────────────────────────────────────

def review_brief(
    brief_id: str,
    notes: str = "",
    force_reject: bool = False,
) -> RevisionFinal:
    """Fase 5 — Orchestrator revisa coherencia global y criterios de aceptación."""
    brief = _load_brief(brief_id)
    if brief is None:
        raise ValueError(f"Brief {brief_id!r} no encontrado.")

    # Evaluar criterios automáticamente (heurística básica)
    criteria_met: list[str] = []
    criteria_failed: list[str] = []

    for criterion in brief.acceptance_criteria:
        # Si hay handoffs pendientes o el brief nunca pasó a in_progress, marcar como pendiente
        if brief.status in ("pending", "assigned") and not force_reject:
            criteria_failed.append(criterion)
        else:
            criteria_met.append(criterion)

    pending_risks: list[str] = []
    for hd in brief.handoffs:
        pending_risks.extend(hd.get("risks", []))

    all_criteria_met = len(criteria_failed) == 0 and not force_reject
    deps_resolved = len(brief.dependencies) == 0  # sin estado de deps externas

    result = "approved" if (all_criteria_met and deps_resolved and not force_reject) else "changes_required"

    revision = RevisionFinal(
        brief_id=brief_id,
        scope_ok=not force_reject,
        criteria_met=criteria_met,
        criteria_failed=criteria_failed,
        dependencies_resolved=deps_resolved,
        pending_risks=pending_risks,
        result=result,
        notes=notes or "Revisión automática del Orchestrator.",
    )

    brief.review = revision.to_dict()
    brief.status = "review"
    _save_brief(brief)
    return revision


# ── Fase 6: Cierre ────────────────────────────────────────────────────────────

def close_brief(brief_id: str, force: bool = False) -> TaskBrief:
    """Fase 6 — Cierre. Solo si la revisión fue approved o force=True."""
    brief = _load_brief(brief_id)
    if brief is None:
        raise ValueError(f"Brief {brief_id!r} no encontrado.")

    review = brief.review
    if not review and not force:
        raise ValueError(f"El brief {brief_id!r} no tiene revisión. Ejecuta 'review' primero.")

    if review.get("result") not in ("approved",) and not force:
        raise ValueError(
            f"El brief {brief_id!r} tiene resultado '{review.get('result')}'. "
            "Usa --force para cerrar igualmente."
        )

    brief.status = "closed"
    _save_brief(brief)
    return brief


# ── Formateo de salida ────────────────────────────────────────────────────────

def _fmt_brief(brief: TaskBrief, verbose: bool = False) -> str:
    status_icon = {
        "pending": "[·]",
        "assigned": "[→]",
        "in_progress": "[~]",
        "handoff": "[⇄]",
        "review": "[?]",
        "closed": "[✓]",
        "rejected": "[✗]",
    }.get(brief.status, "[ ]")

    lines = [
        f"{status_icon} {brief.id}  {brief.priority}  [{brief.domain}]  {brief.agent}",
        f"    Tarea   : {brief.task}",
        f"    Estado  : {brief.status}",
    ]

    if verbose:
        lines += [
            f"    Contexto: {brief.context}",
            f"    Objetivo: {brief.objective}",
            f"    Alcance : {brief.scope}",
            f"    Excl.   : {brief.exclusions}",
            "    Criterios de aceptación:",
        ]
        for i, c in enumerate(brief.acceptance_criteria, 1):
            lines.append(f"      {i}. {c}")
        if brief.dependencies:
            lines.append(f"    Deps    : {', '.join(brief.dependencies)}")
        if brief.handoffs:
            lines.append(f"    Handoffs: {len(brief.handoffs)}")
            for hd in brief.handoffs:
                lines.append(
                    f"      [{hd.get('from_domain')} → {hd.get('to_domain')}]"
                    f" {hd.get('state')} — {hd.get('summary', '')[:60]}"
                )
        if brief.review:
            rv = brief.review
            lines.append(f"    Revisión: {rv.get('result')} — {rv.get('notes', '')[:60]}")
        lines.append(f"    Creado  : {brief.created_at}")
        lines.append(f"    Actualiz: {brief.updated_at}")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="orchestrator_v4",
        description=f"BAGO {VERSION} Orchestrator — Flujo Operativo General",
    )
    p.add_argument("--root", default="", help="Raíz del proyecto (override)")
    p.add_argument("--json", action="store_true", dest="as_json", help="Salida en JSON")
    p.add_argument("--test", action="store_true", help="Ejecutar self-tests")
    sub = p.add_subparsers(dest="subcmd")

    # create
    cr = sub.add_parser("create", help="Fase 1: crear TaskBrief desde una petición")
    cr.add_argument("--task", required=True, help="Descripción de la tarea")
    cr.add_argument("--context", default="", help="Contexto adicional")
    cr.add_argument("--objective", default="", help="Resultado esperado")
    cr.add_argument("--priority", choices=sorted(PRIORITIES), default="", help="Prioridad")
    cr.add_argument("--domain", choices=sorted(DOMAINS), default="", help="Dominio principal")
    cr.add_argument("--scope", default="", help="Qué incluye")
    cr.add_argument("--exclusions", default="", help="Qué queda fuera")
    cr.add_argument("--criteria", nargs="*", default=[], help="Criterios de aceptación")
    cr.add_argument("--deps", nargs="*", default=[], help="Dependencias conocidas")

    # assign
    asgn = sub.add_parser("assign", help="Fase 2: asignar al especialista")
    asgn.add_argument("brief_id", help="ID del brief")
    asgn.add_argument("--agent", choices=sorted(AGENTS), default="", help="Especialista")

    # handoff
    hf = sub.add_parser("handoff", help="Fase 4: transferir a otro dominio")
    hf.add_argument("brief_id", help="ID del brief")
    hf.add_argument("--to", required=True, dest="to_domain", choices=sorted(DOMAINS))
    hf.add_argument("--work", required=True, dest="summary", help="Resumen del trabajo realizado")
    hf.add_argument("--state", default="parcial", choices=["pendiente", "parcial", "completo"])
    hf.add_argument("--artifacts", nargs="*", default=[])
    hf.add_argument("--risks", nargs="*", default=[])
    hf.add_argument("--action", default="", dest="action_requested")

    # review
    rv = sub.add_parser("review", help="Fase 5: revisión del Orchestrator")
    rv.add_argument("brief_id", help="ID del brief")
    rv.add_argument("--notes", default="")
    rv.add_argument("--reject", action="store_true", help="Forzar rechazo")

    # close
    cl = sub.add_parser("close", help="Fase 6: cierre definitivo")
    cl.add_argument("brief_id", help="ID del brief")
    cl.add_argument("--force", action="store_true", help="Cerrar aunque revisión no sea approved")

    # list
    ls = sub.add_parser("list", help="Listar TaskBriefs")
    ls.add_argument("--status", choices=TASK_STATUSES, default="", help="Filtro por estado")

    # show
    sh = sub.add_parser("show", help="Mostrar detalle de un brief")
    sh.add_argument("brief_id", help="ID del brief")

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)

    if args.test:
        return _run_tests()

    configure_paths(args.root or None)

    if args.subcmd == "create":
        brief = create_brief(
            task=args.task,
            context=args.context,
            objective=args.objective,
            priority=args.priority,
            domain=args.domain,
            scope=args.scope,
            exclusions=args.exclusions,
            acceptance_criteria=args.criteria or None,
            dependencies=args.deps or None,
        )
        if args.as_json:
            print(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"[Orchestrator] TaskBrief creado — Fase 1 completada")
            print(_fmt_brief(brief, verbose=True))
        return 0

    elif args.subcmd == "assign":
        brief = assign_brief(args.brief_id, args.agent or None)
        if args.as_json:
            print(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"[Orchestrator] Brief asignado — Fase 2 completada")
            print(_fmt_brief(brief))
        return 0

    elif args.subcmd == "handoff":
        hoff = create_handoff(
            brief_id=args.brief_id,
            to_domain=args.to_domain,
            summary=args.summary,
            state=args.state,
            artifacts=args.artifacts,
            risks=args.risks,
            action_requested=args.action_requested,
        )
        if args.as_json:
            print(json.dumps(hoff.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"[Orchestrator] Handoff registrado — Fase 4 completada")
            print(f"  Dominio destino : {hoff.to_domain}")
            print(f"  Estado          : {hoff.state}")
            print(f"  Acción requerida: {hoff.action_requested}")
            if hoff.risks:
                print(f"  Riesgos         : {', '.join(hoff.risks)}")
        return 0

    elif args.subcmd == "review":
        revision = review_brief(args.brief_id, notes=args.notes, force_reject=args.reject)
        if args.as_json:
            print(json.dumps(revision.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"[Orchestrator] Revisión completada — Fase 5")
            print(f"  Resultado       : {revision.result.upper()}")
            print(f"  Alcance OK      : {'Si' if revision.scope_ok else 'No'}")
            print(f"  Criterios OK    : {len(revision.criteria_met)}/{len(revision.criteria_met) + len(revision.criteria_failed)}")
            print(f"  Deps resueltas  : {'Si' if revision.dependencies_resolved else 'No'}")
            if revision.pending_risks:
                print(f"  Riesgos pend.   : {', '.join(revision.pending_risks)}")
            print(f"  Notas           : {revision.notes}")
        return 0

    elif args.subcmd == "close":
        brief = close_brief(args.brief_id, force=args.force)
        if args.as_json:
            print(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"[Orchestrator] Tarea cerrada — Fase 6 completada")
            print(_fmt_brief(brief))
        return 0

    elif args.subcmd == "list":
        briefs = _list_briefs(args.status or None)
        if not briefs:
            print("[Orchestrator] Sin briefs" + (f" con estado '{args.status}'" if args.status else "") + ".")
            return 0
        if args.as_json:
            print(json.dumps([b.to_dict() for b in briefs], indent=2, ensure_ascii=False))
        else:
            print(f"[Orchestrator] {len(briefs)} brief(s):\n")
            for b in briefs:
                print(_fmt_brief(b))
                print()
        return 0

    elif args.subcmd == "show":
        brief = _load_brief(args.brief_id)
        if brief is None:
            print(f"[Orchestrator] Brief {args.brief_id!r} no encontrado.", file=sys.stderr)
            return 1
        if args.as_json:
            print(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(_fmt_brief(brief, verbose=True))
        return 0

    else:
        _parse(["--help"])
        return 0


# ── Self-tests ────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    import shutil
    import tempfile

    scratch = Path(tempfile.mkdtemp(prefix="bago_orc_test_"))
    try:
        configure_paths(str(scratch))
        results: list[tuple[str, bool, str]] = []

        # T1: create_brief genera un brief con ID y persiste en disco
        b1 = create_brief(task="Fix the broken API endpoint")
        results.append((
            "create_persists",
            _brief_path(b1.id).exists(),
            "create_brief guarda JSON en disco",
        ))

        # T2: dominio inferido correctamente
        results.append((
            "infer_domain_backend",
            b1.domain == "Backend",
            f"'API endpoint' → dominio Backend (got {b1.domain})",
        ))

        # T3: prioridad inferida correctamente para P0
        b_p0 = create_brief(task="El servidor está caído, bloqueante")
        results.append((
            "infer_priority_p0",
            b_p0.priority == "P0",
            f"'bloqueante' → P0 (got {b_p0.priority})",
        ))

        # T4: assign cambia estado a 'assigned'
        b_assigned = assign_brief(b1.id, agent="backend")
        results.append((
            "assign_status",
            b_assigned.status == "assigned" and b_assigned.agent == "backend",
            f"assign → status=assigned, agent=backend",
        ))

        # T5: handoff cambia dominio, añade entrada al historial
        hoff = create_handoff(
            brief_id=b1.id,
            to_domain="Frontend",
            summary="Backend contract definido",
            state="completo",
            risks=["CSS puede variar"],
            action_requested="Implementar la pantalla de error",
        )
        b_after_hoff = _load_brief(b1.id)
        results.append((
            "handoff_recorded",
            len(b_after_hoff.handoffs) == 1 and b_after_hoff.domain == "Frontend",
            "handoff registrado y dominio actualizado",
        ))

        # T6: review devuelve RevisionFinal con result
        # Simular un brief cerrable: marcar como in_progress antes de revisar
        b_after_hoff.status = "in_progress"
        _save_brief(b_after_hoff)
        revision = review_brief(b1.id, notes="OK desde test")
        results.append((
            "review_produces_revision",
            isinstance(revision.result, str) and revision.result in ("approved", "changes_required"),
            f"review devuelve resultado válido: {revision.result}",
        ))

        # T7: close requiere revisión aprobada (sin force falla en pending)
        b_pending = create_brief(task="Tarea sin revisar")
        try:
            close_brief(b_pending.id, force=False)
            results.append(("close_requires_review", False, "deberia haber fallado"))
        except ValueError:
            results.append(("close_requires_review", True, "close sin review lanza ValueError"))

        # T8: close con force=True cierra cualquier brief
        b_force = create_brief(task="Cerrar urgente")
        b_closed = close_brief(b_force.id, force=True)
        results.append((
            "close_force",
            b_closed.status == "closed",
            "close --force cierra sin revisión previa",
        ))

        # T9: list devuelve los briefs creados
        all_briefs = _list_briefs()
        results.append((
            "list_returns_briefs",
            len(all_briefs) >= 4,
            f"list devuelve {len(all_briefs)} briefs (>=4)",
        ))

        # T10: JSON output desde CLI
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--root", str(scratch), "--json", "create", "--task", "CLI JSON test"])
        raw = out.getvalue()
        try:
            parsed = json.loads(raw)
            json_ok = isinstance(parsed, dict) and "id" in parsed
        except Exception:
            json_ok = False
        results.append((
            "cli_json_output",
            rc == 0 and json_ok,
            "CLI --json produce JSON parseable con campo 'id'",
        ))

        # T11: CLI list funciona sin error
        out2 = io.StringIO()
        with redirect_stdout(out2):
            rc2 = main(["--root", str(scratch), "list"])
        results.append((
            "cli_list_works",
            rc2 == 0,
            "bago orchestrate list devuelve 0",
        ))

    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        configure_paths()

    return print_test_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
