---
agent: 'agent'
description: 'BAGO workpack: 06 workspace'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Workspace en profundidad

Usa `bago-architecture-auditor` con apoyo de `bago-code-mapper`.

Audita específicamente el dominio Workspace: file explorer, lectura/escritura, tabs, editor, dirty state, save,
diagnostics, diff, context menu, search, ignored files, vendor, filtros, patterns, analysis, selection, context tree,
GitHub, chat, contexto, sources, acciones, shortcuts y persistencia.

Determina si existe UNA sola fuente de verdad.
Busca estados paralelos, bridges legacy, implementaciones sustituidas aún activas y ownership ambiguo.
Distingue estado canónico, derivado, legacy, duplicado y adaptación legítima.
