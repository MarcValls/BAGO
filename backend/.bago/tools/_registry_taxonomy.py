"""_registry_taxonomy.py — Layer/scope/agent taxonomy maps and post-processing.

Imports REGISTRY from _registry_entries and mutates entries in-place
to inject layer, scope, agent, stability, and layer_group metadata.

Internal module: import via tool_registry, not directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from _registry_entries import REGISTRY  # noqa: F401 — re-exported

# ── Taxonomía de capas ─────────────────────────────────────────────────────────

LAYERS: dict[str, dict] = {
    "ejecución": {"icon": "⚡", "label": "EJECUCIÓN",  "desc": "ejecutar y avanzar trabajo activo"},
    "calidad":   {"icon": "🔍", "label": "CALIDAD",    "desc": "calidad de código del proyecto"},
    "salud":     {"icon": "💚", "label": "SALUD",      "desc": "salud y mantenimiento del framework"},
    "analítica": {"icon": "📊", "label": "ANALÍTICA",  "desc": "métricas, insights y patrones"},
    "visual":    {"icon": "🎨", "label": "VISUAL",     "desc": "generación de assets e interfaces"},
    "avanzado":  {"icon": "🔧", "label": "AVANZADO",   "desc": "herramientas avanzadas e integraciones"},
}

_LAYER_MAP: dict[str, str] = {
    # EJECUCIÓN
    "start": "ejecución", "next": "ejecución", "ideas": "ejecución",
    "select": "ejecución", "session": "ejecución", "task": "ejecución",
    "done": "ejecución", "flow": "ejecución", "sprint": "ejecución",
    "goals": "ejecución", "workflow": "ejecución", "reopen": "ejecución",
    "auto": "ejecución", "cosecha": "ejecución", "v2": "ejecución",
    "session_close": "ejecución",
    # CALIDAD
    "scan": "calidad", "review": "calidad", "commit": "calidad",
    "hardcode": "calidad", "spanish": "calidad", "rubber-duck": "calidad",
    "pre-push": "calidad", "secrets": "calidad", "debt": "calidad",
    "risk": "calidad", "naming": "calidad", "types": "calidad",
    "deps": "calidad", "code-quality": "calidad",
    # SALUD
    "health": "salud", "audit": "salud", "doctor": "salud", "heal": "salud",
    "validate": "salud", "sync": "salud", "check": "salud",
    "consistency": "salud", "config-check": "salud", "context": "salud",
    "repo": "salud", "project": "salud", "stale": "salud",
    "detector": "salud", "map": "salud", "scope": "salud",
    # ANALÍTICA
    "insights": "analítica", "habit": "analítica", "chronicle": "analítica",
    "dashboard": "analítica", "efficiency": "analítica", "stability": "analítica",
    "report": "analítica", "diff": "analítica", "status": "analítica",
    # VISUAL
    "hub": "visual", "image-studio": "visual", "sprite-studio": "visual",
    "image_gen": "visual", "banner": "visual",
    # AVANZADO
    "llm": "avanzado", "lsp": "avanzado", "orchestrate": "avanzado",
    "cabinet": "avanzado", "rules": "avanzado", "db": "avanzado",
    "peer": "avanzado", "find-tool": "avanzado", "ask": "avanzado",
    "music": "avanzado",
    "why": "avanzado", "research": "avanzado", "install": "avanzado",
    "hello": "avanzado", "git": "avanzado",
    "siembra": "salud",
    "recientes": "analítica",
    "repo-clone": "salud", "repo-list": "salud", "repo-switch": "salud",
    "project-init": "salud", "project-link": "salud", "project-unlink": "salud",
    "project-state": "salud", "deactivate": "salud", "promote": "salud", "learn": "salud",
}

_SCOPE_MAP: dict[str, str] = {
    # framework — opera sobre el propio framework BAGO
    "health": "framework", "validate": "framework", "sync": "framework",
    "check": "framework", "consistency": "framework", "config-check": "framework",
    "stability": "framework", "efficiency": "framework", "sincerity": "framework",
    "doctor": "framework", "heal": "framework", "auto": "framework",
    "banner": "framework", "rules": "framework", "db": "framework",
    "cabinet": "framework", "install": "framework", "hello": "framework",
    "report": "framework", "scope": "framework", "siembra": "framework",
    # project — opera sobre el proyecto activo
    "scan": "project", "review": "project", "commit": "project",
    "pre-push": "project", "secrets": "project", "debt": "project",
    "risk": "project", "naming": "project", "types": "project",
    "deps": "project", "code-quality": "project",
    "image-studio": "project", "sprite-studio": "project",
    "image_gen": "project", "lsp": "project", "git": "project",
    "music": "project",
    # both — opera sobre el framework Y/O proyectos
    "start": "both", "next": "both", "ideas": "both", "select": "both",
    "session": "both", "task": "both", "done": "both", "flow": "both",
    "sprint": "both", "goals": "both", "workflow": "both", "reopen": "both",
    "cosecha": "both", "v2": "both", "session_close": "both",
    "audit": "both", "context": "both", "repo": "both", "project": "both",
    "insights": "both", "habit": "both", "chronicle": "both",
    "dashboard": "both", "diff": "both", "status": "both",
    "recientes": "both",
    "hub": "both", "llm": "both", "orchestrate": "both", "peer": "both",
    "find-tool": "both", "ask": "both", "why": "both", "research": "both",
    "detector": "both", "stale": "both", "map": "both",
    "repo-clone": "both", "repo-list": "both", "repo-switch": "both",
    "project-init": "both", "project-link": "both", "project-unlink": "both",
    "project-state": "both", "deactivate": "both", "promote": "both", "learn": "both",
}

# ── Agent map — qué agente interno es responsable de cada comando ──────────────
# Agentes disponibles (ver .bago/roles/):
#   ANALISTA · ARQUITECTO · GENERADOR · ORGANIZADOR · VALIDADOR (produccion)
#   AUDITOR_CANONICO · CENTINELA_SINCERIDAD · VERTICE             (supervision)
#   REVISOR_SEGURIDAD · REVISOR_PERFORMANCE · REVISOR_UX          (especialistas)
#   INTEGRADOR_REPO                                                (especialistas)
_AGENT_MAP: dict[str, str] = {
    # ANALISTA — Análisis estático, detección, métricas, búsqueda
    "detector":    "ANALISTA",
    "scope":       "ANALISTA",
    "efficiency":  "ANALISTA",
    "stability":   "ANALISTA",
    "code-quality":"ANALISTA",
    "naming":      "ANALISTA",
    "types":       "ANALISTA",
    "deps":        "ANALISTA",
    "map":         "ANALISTA",
    "context":     "ANALISTA",
    "diff":        "ANALISTA",
    "why":         "ANALISTA",
    "research":    "ANALISTA",
    "scan":        "ANALISTA",
    "debt":        "ANALISTA",
    "risk":        "ANALISTA",
    "find-tool":   "ANALISTA",
    "insights":    "ANALISTA",
    "lsp":         "ANALISTA",
    "habit":       "ANALISTA",
    "review":      "ANALISTA",
    # ARQUITECTO — Flujo, automatización, planificación, clonado
    "auto":           "ARQUITECTO",
    "flow":           "ARQUITECTO",
    "cabinet":        "ARQUITECTO",
    "orchestrate":    "ARQUITECTO",
    "music":          "ARQUITECTO",
    "repo-clone":     "ARQUITECTO",
    "llm":            "ARQUITECTO",
    "project-init":   "ARQUITECTO",
    "project-link":   "ARQUITECTO",
    "project-unlink": "ARQUITECTO",
    "next":           "ARQUITECTO",
    "peer":           "ARQUITECTO",
    "hub":            "ARQUITECTO",
    "siembra":        "ARQUITECTO",
    # GENERADOR — Generación de artefactos, reportes, imágenes
    "cosecha":       "GENERADOR",
    "image_gen":     "GENERADOR",
    "report":        "GENERADOR",
    "banner":        "GENERADOR",
    "chronicle":     "GENERADOR",
    "sprite-studio": "GENERADOR",
    "image-studio":  "GENERADOR",
    # ORGANIZADOR — Sprint, workflow, sesión, estado, repos, DB
    "dashboard":     "ORGANIZADOR",
    "ideas":         "ORGANIZADOR",
    "workflow":      "ORGANIZADOR",
    "sprint":        "ORGANIZADOR",
    "task":          "ORGANIZADOR",
    "v2":            "ORGANIZADOR",
    "session":       "ORGANIZADOR",
    "session_close": "ORGANIZADOR",
    "reopen":        "ORGANIZADOR",
    "git":           "ORGANIZADOR",
    "db":            "ORGANIZADOR",
    "done":          "ORGANIZADOR",
    "status":        "ORGANIZADOR",
    "sync":          "ORGANIZADOR",
    "repo":          "ORGANIZADOR",
    "repo-list":     "ORGANIZADOR",
    "repo-switch":   "ORGANIZADOR",
    "select":        "ORGANIZADOR",
    "project-state": "ORGANIZADOR",
    "deactivate":    "VALIDADOR",
    "promote":       "ORGANIZADOR",
    "learn":         "ORGANIZADOR",
    "project":       "ORGANIZADOR",
    "ask":           "ORGANIZADOR",
    "goals":         "ORGANIZADOR",
    "recientes":     "ORGANIZADOR",
    # VALIDADOR — Salud, validación, diagnóstico
    "health":        "VALIDADOR",
    "audit":         "VALIDADOR",
    "validate":      "VALIDADOR",
    "check":         "VALIDADOR",
    "stale":         "VALIDADOR",
    "config-check":  "VALIDADOR",
    "doctor":        "VALIDADOR",
    "heal":          "VALIDADOR",
    "consistency":   "VALIDADOR",
    # CENTINELA_SINCERIDAD — Integridad de commits y sinceridad
    "commit":        "CENTINELA_SINCERIDAD",
    "pre-push":      "CENTINELA_SINCERIDAD",
    "sincerity":     "CENTINELA_SINCERIDAD",
    # AUDITOR_CANONICO — Reglas y auditoría canónica
    "rules":         "AUDITOR_CANONICO",
    # REVISOR_SEGURIDAD — Seguridad y secretos
    "secrets":       "REVISOR_SEGURIDAD",
    # VERTICE — Gobierno del sistema, entrada, instalación
    "hello":         "VERTICE",
    "install":       "VERTICE",
    "start":         "VERTICE",
}

# ── Inject layer + scope + agent into each REGISTRY entry ─────────────────────

for _cmd, _entry in REGISTRY.items():
    if not _entry.layer:
        _entry.layer = _LAYER_MAP.get(_cmd, "avanzado")
    if not _entry.scope:
        _entry.scope = _SCOPE_MAP.get(_cmd, "both")
    if not _entry.agent:
        _entry.agent = _AGENT_MAP.get(_cmd, "ORGANIZADOR")

# ── Kernel Lockdown classification (v3.2) ─────────────────────────────────────

_CORE_CMDS: frozenset[str] = frozenset({
    "health", "audit", "status", "task", "session",
    "project", "sync", "scope", "secrets", "validate", "context",
})
_DANGEROUS_CMDS: frozenset[str] = frozenset({
    "install", "autonomous", "orchestrate", "cabinet", "peer", "db", "auto", "spiral",
})
_INTERNAL_CMDS: frozenset[str] = frozenset({
    "banner", "hello", "hub", "start", "done",
})
_LAYER_GROUP_MAP: dict[str, str] = {
    # core public interface
    "health": "core",
    "status": "core",
    "validate": "core",
    "audit": "core",
    "task": "core",
    "flow": "core",
    "session": "core",
    "project": "core",
    "context": "core",
    "sync": "core",
    "scope": "core",
    "secrets": "core",
    # agents
    "llm": "agents",
    "route": "agents",
    "autonomous": "agents",
    "auto": "agents",
    "ask": "agents",
    "research": "agents",
    "chronicle": "agents",
    # ui
    "hub": "ui",
    "dashboard": "ui",
    "peer": "ui",
    # labs
    "image-studio": "labs",
    "sprite-studio": "labs",
    "image_gen": "labs",
    "music": "labs",
    "ableton-template": "labs",
}

for _cmd, _entry in REGISTRY.items():
    if _entry.deprecated:
        _entry.stability = "legacy"
    elif _cmd in _CORE_CMDS:
        _entry.stability = "core"
        _entry.preflight_policy = "required"
    elif _cmd in _DANGEROUS_CMDS:
        _entry.stability = "dangerous"
        _entry.risk = "dangerous"
    elif _cmd in _INTERNAL_CMDS:
        _entry.stability = "internal"
        _entry.preflight_policy = "none"
    # else: stability="experimental", risk="safe", preflight_policy="optional" (defaults)
    _entry.layer_group = _LAYER_GROUP_MAP.get(_cmd, _entry.layer_group)

# ── Visual badges ──────────────────────────────────────────────────────────────

SCOPE_BADGE: dict[str, str] = {
    "framework": "🔵",
    "project":   "🟢",
    "both":      "⚪",
}
