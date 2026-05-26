"""_registry_taxonomy.py — Layer/scope/agent taxonomy maps and post-processing.

Imports REGISTRY from _registry_entries and mutates entries in-place
to inject layer, scope, agent, stability, and layer_group metadata.

Internal module: import vía tool_registry, not directly.

Modelo cognitivo BAGO — Bucle Shepard (4 capas):
  MOTOR      — orquesta el ciclo: routing, agentes, ejecución
  CONSUMO    — percibe el entorno: lectura, detección, input
  MEMORIA    — persiste el estado: historial, conocimiento, métricas
  GENERACION — produce artefactos: output, código, reportes, notificaciones
  DOMINIO    — herramientas de dominio específico (música, visual, etc.)
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from _registry_entries import REGISTRY  # noqa: F401 — re-exported

# ── Taxonomía de capas — Modelo cognitivo BAGO ─────────────────────────────────

LAYERS: dict[str, dict] = {
    "motor":      {"icon": "⚙️",  "label": "MOTOR",      "desc": "orquestación del ciclo: routing, agentes, ejecución"},
    "consumo":    {"icon": "👁️",  "label": "CONSUMO",    "desc": "percepción del entorno: lectura, detección, input"},
    "memoria":    {"icon": "🧠",  "label": "MEMORIA",    "desc": "estado persistente: historial, conocimiento, métricas"},
    "generacion": {"icon": "✨",  "label": "GENERACIÓN", "desc": "artefactos: output, código, reportes, notificaciones"},
    "dominio":    {"icon": "🎨",  "label": "DOMINIO",    "desc": "herramientas de dominio específico"},
}

_LAYER_MAP: dict[str, str] = {
    # ── MOTOR — orquesta el bucle Shepard ─────────────────────────────────────
    "agent":            "motor",
    "agent-config":     "motor",
    "alias-manager":    "motor",
    "assign":           "motor",
    "auto":             "motor",
    "autonomous":       "motor",
    "autonomy":         "motor",
    "boot":             "motor",
    "build-run":        "motor",
    "cabinet":          "motor",
    "canon":            "motor",   # bucle Shepard propiamente dicho
    "create":           "motor",
    "done":             "motor",
    "field":            "motor",
    "flow":             "motor",
    "gateway":          "motor",
    "install":          "motor",
    "llm":              "motor",
    "llm-node":         "motor",
    "lsp":              "motor",
    "menu":             "motor",
    "neural":           "motor",
    "neural-toolbox":   "motor",
    "next":             "motor",
    "orchestrate":      "motor",
    "peer":             "motor",
    "route":            "motor",
    "safeguard":        "motor",
    "script-runner":    "motor",
    "select":           "motor",
    "skill":            "motor",
    "spiral":           "motor",
    "spiral-agent":     "motor",
    "start":            "motor",
    "toolsmith":        "motor",
    "workflow":         "motor",
    "workflow-navigator":"motor",
    # ── CONSUMO — percibe el entorno ───────────────────────────────────────────
    "ask":              "consumo",
    "code-metrics":     "consumo",
    "code-search":      "consumo",
    "config-check":     "consumo",
    "context":          "consumo",
    "deps":             "consumo",
    "diff":             "consumo",
    "doc-index":        "consumo",
    "env-manager":      "consumo",
    "find-tool":        "consumo",
    "git-status":       "consumo",
    "hardcode":         "consumo",
    "inbox":            "consumo",
    "lint-runner":      "consumo",
    "log-viewer":       "consumo",
    "naming":           "consumo",
    "net-scan":         "consumo",
    "orphan-shield":    "consumo",
    "orphans":          "consumo",
    "ping-server":      "consumo",
    "placeholder_scan": "consumo",
    "preflight-check":  "consumo",
    "repo":             "consumo",
    "scope":            "consumo",
    "search-history":   "consumo",
    "secrets":          "consumo",
    "size-check":       "consumo",
    "spanish":          "consumo",
    "types":            "consumo",
    # ── MEMORIA — persiste y recuerda ─────────────────────────────────────────
    "artifact-counter": "memoria",
    "audit":            "memoria",
    "benchmark":        "memoria",
    "chronicle":        "memoria",
    "dashboard":        "memoria",
    "dashboard-risks":  "memoria",
    "stats-panel":      "memoria",
    "demo":             "generacion",
    "debt":             "memoria",
    "devmode":          "memoria",
    "focus-mode":       "memoria",
    "goals":            "memoria",
    "habit":            "memoria",
    "health":           "memoria",
    "ideas":            "memoria",
    "insights":         "memoria",
    "npath":            "memoria",
    "project":          "memoria",
    "project-summary":  "memoria",
    "publish-kit":      "generacion",
    "recent-projects":  "memoria",
    "recientes":        "memoria",
    "reopen":           "memoria",
    "risk":             "memoria",
    "session":          "memoria",
    "siembra":          "memoria",
    "snapshot":         "memoria",
    "sprint":           "memoria",
    "state-manager":    "memoria",
    "status":           "memoria",
    "sync":             "memoria",
    "task":             "memoria",
    "validate":         "memoria",
    "version":          "memoria",
    "weekly-report":    "memoria",
    "work_matrix":      "memoria",
    "workspace-select": "memoria",
    # ── GENERACIÓN — produce artefactos ───────────────────────────────────────
    "advisor":          "generacion",
    "build-clean":      "generacion",
    "deactivate":       "generacion",
    "doc-agent":        "generacion",
    "docs":             "generacion",
    "heal-paths":       "generacion",
    "html-export":      "generacion",
    "notify-bago":      "generacion",
    "notify-desktop":   "generacion",
    "notify-whatsapp":  "generacion",
    "personality-panel":"generacion",
    "research":         "generacion",
    "review":           "generacion",
    "rubber-duck":      "generacion",
    "rules":            "generacion",
    "seed":             "generacion",
    "setup":            "generacion",
    "template-gen":     "generacion",
    "why":              "generacion",
    # ── DOMINIO — herramientas de dominio específico ──────────────────────────
    "ableton-template": "dominio",
    "banner":           "dominio",
    "hub":              "dominio",
    "image-studio":     "dominio",
    "image_gen":        "dominio",
    "launch":           "dominio",
    "music":            "dominio",
    "music-saas":       "dominio",
    "sprite-studio":    "dominio",
    # internal helpers
    "hello":            "motor",
    "self":             "motor",   # autoreparación del framework
}

_SCOPE_MAP: dict[str, str] = {
    # framework — opera sobre el propio framework BAGO
    "advisor": "framework",
    "alias-manager": "framework",
    "artifact-counter": "framework",
    "auto": "framework",
    "banner": "framework",
    "benchmark": "framework",
    "cabinet": "framework",
    "config-check": "framework",
    "db": "framework",
    "devmode": "framework",
    "env-manager": "framework",
    "health": "framework",
    "hello": "framework",
    "install": "framework",
    "launch": "framework",
    "menu": "framework",
    "neural": "framework",
    "neural-toolbox": "framework",
    "notify-bago": "framework",
    "notify-desktop": "framework",
    "notify-whatsapp": "framework",
    "npath": "framework",
    "orphans": "framework",
    "personality-panel": "framework",
    "rules": "framework",
    "scope": "framework",
    "seed": "framework",
    "setup": "framework",
    "siembra": "framework",
    "state-manager": "framework",
    "sync": "framework",
    "toolsmith": "framework",
    "validate": "framework",
    "weekly-report": "framework",
    "work_matrix": "framework",
    "workspace-select": "framework",
    # project — opera sobre el proyecto activo
    "ableton-template": "project",
    "build-clean": "project",
    "build-run": "project",
    "canon": "project",
    "code-metrics": "project",
    "code-search": "project",
    "debt": "project",
    "deps": "project",
    "doc-index": "project",
    "docs": "project",
    "git-status": "project",
    "hardcode": "project",
    "heal-paths": "project",
    "html-export": "project",
    "image-studio": "project",
    "image_gen": "project",
    "lint-runner": "project",
    "log-viewer": "project",
    "lsp": "project",
    "music": "project",
    "naming": "project",
    "orphan-shield": "project",
    "placeholder_scan": "project",
    "review": "project",
    "risk": "project",
    "script-runner": "project",
    "secrets": "project",
    "size-check": "project",
    "snapshot": "project",
    "sprite-studio": "project",
    "template-gen": "project",
    "types": "project",
    # both — opera sobre el framework Y/O proyectos
    "agent": "both",
    "ask": "both",
    "assign": "both",
    "audit": "both",
    "autonomous": "both",
    "autonomy": "both",
    "chronicle": "both",
    "context": "both",
    "dashboard": "both",
    "stats-panel": "framework",
    "demo": "framework",
    "deactivate": "both",
    "diff": "both",
    "doc-agent": "both",
    "done": "both",
    "find-tool": "both",
    "flow": "both",
    "focus-mode": "both",
    "agent-config": "both",
    "goals": "both",
    "habit": "both",
    "create": "both",
    "hub": "both",
    "ideas": "both",
    "inbox": "both",
    "insights": "both",
    "llm": "both",
    "llm-node": "both",
    "net-scan": "both",
    "next": "both",
    "orchestrate": "both",
    "peer": "both",
    "ping-server": "both",
    "preflight-check": "both",
    "project": "both",
    "publish-kit": "framework",
    "project-summary": "both",
    "recent-projects": "both",
    "recientes": "both",
    "reopen": "both",
    "repo": "both",
    "research": "both",
    "route": "both",
    "rubber-duck": "both",
    "search-history": "both",
    "select": "both",
    "session": "both",
    "skill": "both",
    "spanish": "both",
    "spiral": "both",
    "spiral-agent": "both",
    "sprint": "both",
    "start": "both",
    "status": "both",
    "task": "both",
    "version": "both",
    "why": "both",
    "workflow": "both",
    "workflow-navigator": "both",
}

# ── Agent map — qué agente interno es responsable de cada comando ──────────────
# Agentes disponibles (ver .bago/roles/):
#   ANALISTA · ARQUITECTO · GENERADOR · ORGANIZADOR · VALIDADOR (produccion)
#   AUDITOR_CANONICO · CENTINELA_SINCERIDAD · VERTICE             (supervision)
#   REVISOR_SEGURIDAD · REVISOR_PERFORMANCE · REVISOR_UX          (especialistas)
#   INTEGRADOR_REPO                                                (especialistas)
_AGENT_MAP: dict[str, str] = {
    # ANALISTA — Análisis estático, detección, métricas, búsqueda
    "artifact-counter": "ANALISTA",
    "code-metrics": "ANALISTA",
    "code-search": "ANALISTA",
    "context": "ANALISTA",
    "debt": "ANALISTA",
    "deps": "ANALISTA",
    "diff": "ANALISTA",
    "find-tool": "ANALISTA",
    "habit": "ANALISTA",
    "insights": "ANALISTA",
    "lsp": "ANALISTA",
    "naming": "ANALISTA",
    "research": "ANALISTA",
    "review": "ANALISTA",
    "risk": "ANALISTA",
    "scope": "ANALISTA",
    "search-history": "ANALISTA",
    "snapshot": "ANALISTA",
    "types": "ANALISTA",
    "why": "ANALISTA",
    "work_matrix": "ANALISTA",
    # ARQUITECTO — Flujo, automatización, planificación, clonado
    "agent": "ARQUITECTO",
    "alias-manager": "ARQUITECTO",
    "auto": "ARQUITECTO",
    "autonomous": "ARQUITECTO",
    "autonomy": "ARQUITECTO",
    "cabinet": "ARQUITECTO",
    "devmode": "ARQUITECTO",
    "env-manager": "ARQUITECTO",
    "flow": "ARQUITECTO",
    "focus-mode": "ARQUITECTO",
    "hub": "ARQUITECTO",
    "inbox": "ARQUITECTO",
    "llm": "ARQUITECTO",
    "llm-node": "ARQUITECTO",
    "music": "ARQUITECTO",
    "net-scan": "ARQUITECTO",
    "neural": "ARQUITECTO",
    "neural-toolbox": "ARQUITECTO",
    "next": "ARQUITECTO",
    "npath": "ARQUITECTO",
    "orchestrate": "ARQUITECTO",
    "peer": "ARQUITECTO",
    "route": "ARQUITECTO",
    "seed": "ARQUITECTO",
    "siembra": "ARQUITECTO",
    "spiral": "ARQUITECTO",
    "spiral-agent": "ARQUITECTO",
    "state-manager": "ARQUITECTO",
    "toolsmith": "ARQUITECTO",
    "workflow-navigator": "ARQUITECTO",
    "workspace-select": "ARQUITECTO",
    # GENERADOR — Generación de artefactos, reportes, imágenes
    "ableton-template": "GENERADOR",
    "banner": "GENERADOR",
    "chronicle": "GENERADOR",
    "doc-index": "GENERADOR",
    "docs": "GENERADOR",
    "html-export": "GENERADOR",
    "image-studio": "GENERADOR",
    "image_gen": "GENERADOR",
    "notify-bago": "GENERADOR",
    "notify-desktop": "GENERADOR",
    "notify-whatsapp": "GENERADOR",
    "sprite-studio": "GENERADOR",
    "template-gen": "GENERADOR",
    "weekly-report": "GENERADOR",
    # ORGANIZADOR — Sprint, workflow, sesión, estado, repos, DB
    "ask": "ORGANIZADOR",
    "assign": "ORGANIZADOR",
    "agent-config": "ORGANIZADOR",
    "benchmark": "ORGANIZADOR",
    "build-run": "ORGANIZADOR",
    "create": "ORGANIZADOR",
    "dashboard": "ORGANIZADOR",
    "stats-panel": "ORGANIZADOR",
    "demo": "MAESTRO_BAGO",
    "db": "ORGANIZADOR",
    "done": "ORGANIZADOR",
    "goals": "ORGANIZADOR",
    "ideas": "ORGANIZADOR",
    "log-viewer": "ORGANIZADOR",
    "menu": "ORGANIZADOR",
    "personality-panel": "ORGANIZADOR",
    "project": "ORGANIZADOR",
    "publish-kit": "DOCUMENTADOR",
    "project-summary": "ORGANIZADOR",
    "recent-projects": "ORGANIZADOR",
    "recientes": "ORGANIZADOR",
    "reopen": "ORGANIZADOR",
    "repo": "ORGANIZADOR",
    "script-runner": "ORGANIZADOR",
    "select": "ORGANIZADOR",
    "session": "ORGANIZADOR",
    "setup": "ORGANIZADOR",
    "skill": "ORGANIZADOR",
    "sprint": "ORGANIZADOR",
    "status": "ORGANIZADOR",
    "sync": "ORGANIZADOR",
    "task": "ORGANIZADOR",
    "version": "ORGANIZADOR",
    "workflow": "ORGANIZADOR",
    # VALIDADOR — Salud, validación, diagnóstico
    "audit": "VALIDADOR",
    "build-clean": "VALIDADOR",
    "canon": "VALIDADOR",
    "config-check": "VALIDADOR",
    "deactivate": "VALIDADOR",
    "doc-agent": "VALIDADOR",
    "git-status": "VALIDADOR",
    "heal-paths": "VALIDADOR",
    "health": "VALIDADOR",
    "lint-runner": "VALIDADOR",
    "orphan-shield": "VALIDADOR",
    "orphans": "VALIDADOR",
    "ping-server": "VALIDADOR",
    "placeholder_scan": "VALIDADOR",
    "preflight-check": "VALIDADOR",
    "size-check": "VALIDADOR",
    "validate": "VALIDADOR",
    # CENTINELA_SINCERIDAD — Integridad de commits y sinceridad
    "hardcode": "CENTINELA_SINCERIDAD",
    "rubber-duck": "CENTINELA_SINCERIDAD",
    "spanish": "CENTINELA_SINCERIDAD",
    # AUDITOR_CANONICO — Reglas y auditoría canónica
    "rules": "AUDITOR_CANONICO",
    # REVISOR_SEGURIDAD — Seguridad y secretos
    "secrets": "REVISOR_SEGURIDAD",
    # REVISOR_PERFORMANCE — Rendimiento y experiencia operativa
    "advisor": "REVISOR_PERFORMANCE",
    "launch": "REVISOR_PERFORMANCE",
    # VERTICE — Gobierno del sistema, entrada, instalación
    "hello": "VERTICE",
    "install": "VERTICE",
    "start": "VERTICE",
}

# ── Inject layer + scope + agent into each REGISTRY entry ─────────────────────

for _cmd, _entry in REGISTRY.items():
    # Layer: _LAYER_MAP always wins; fallback to existing value or "motor"
    _entry.layer = _LAYER_MAP.get(_cmd) or _entry.layer or "motor"
    if not _entry.scope:
        _entry.scope = _SCOPE_MAP.get(_cmd, "both")
    if not _entry.agent:
        _entry.agent = _AGENT_MAP.get(_cmd, "ORGANIZADOR")

# ── Kernel Lockdown classification (v3.2) ─────────────────────────────────────

_CORE_CMDS: frozenset[str] = frozenset({
    # Contrato estable original
    "health", "audit", "status", "task", "session", "flow",
    "project", "sync", "scope", "secrets", "validate", "context",
    # Graduados de experimental — bucle cognitivo esencial
    "ask",       # CONSUMO: router lenguaje natural → BAGO
    "ideas",     # MEMORIA: núcleo del loop de trabajo
    "sprint",    # MEMORIA: gestión de sprints
    "goals",     # MEMORIA: objetivos del proyecto
    "dashboard", # MEMORIA: estado del pack
    "stats-panel", # MEMORIA: panel estadístico de BAGO
    "route",     # MOTOR: routing LLM híbrido
    "review",    # GENERACIÓN: code review automatizado
    "docs",      # GENERACIÓN: genera documentación
    "version",   # MEMORIA: gestión de versiones
    "workflow",  # MOTOR: selector de flujo
    "next",      # MOTOR: meta-ciclo mínimo
    "advisor",   # GENERACIÓN: LLM adaptativo
    "snapshot",  # MEMORIA: comparación de estados
    "why",       # GENERACIÓN: explica comandos
    "diff",      # CONSUMO: cambios entre sesiones
    "risk",      # MEMORIA: matriz de riesgo
    # Promovidos tras audit de estabilidad no destructivo (2026-05-26)
    "ableton-template",
    "alias-manager",
    "artifact-counter",
    "assign",
    "autonomy",
    "backup-vault",
    "benchmark",
    "boot",
    "build-clean",
    "build-run",
    "chronicle",
    "code-metrics",
    "code-search",
    "config-check",
    "contract",
    "create",
    "debt",
    "deps",
    "doc-index",
    "env-manager",
    "find-tool",
    "focus-mode",
    "git-status",
    "habit",
    "hardcode",
    "heal-paths",
    "html-export",
    "image_gen",
    "inbox",
    "insights",
    "llm",
    "llm-node",
    "log-viewer",
    "lsp",
    "naming",
    "neural",
    "neural-toolbox",
    "notify-bago",
    "notify-desktop",
    "npath",
    "orphan-shield",
    "personality-panel",
    "ping-server",
    "placeholder_scan",
    "portable",
    "preflight-check",
    "preset",
    "project-summary",
    "publish-kit",
    "recientes",
    "reopen",
    "repo",
    "research",
    "restart",
    "route-graph",
    "rubber-duck",
    "rules",
    "safeguard",
    "search-history",
    "seed",
    "select",
    "siembra",
    "size-check",
    "skill",
    "spanish",
    "spiral-agent",
    "state-manager",
    "template-gen",
    "types",
    "update",
    "visual-studio",
    "weekly-report",
    "work_matrix",
    "workflow-navigator",
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
    "stats-panel": "ui",
    "demo": "ui",
    "peer": "ui",
    "publish-kit": "ui",
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
