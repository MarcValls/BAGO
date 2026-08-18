---
agent: 'agent'
description: 'BAGO workpack: 21 mechanical approved'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Cambio mecánico aprobado

Usa `bago-mechanical-worker`.

Ejecuta sólo el cambio mecánico totalmente especificado en EXTRA_INSTRUCTIONS.
Si aparece cualquier decisión de arquitectura, diseño, compatibilidad o seguridad no resuelta, devuelve BLOCKED sin improvisar.
Incluye diff, checks y estado final.
