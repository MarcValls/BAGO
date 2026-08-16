---
agent: 'agent'
description: 'BAGO workpack: 13 synthesis'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Síntesis integral

Usa `bago-architecture-auditor`.

Lee todos los informes previos del MISMO RunId en el directorio de reports indicado por el runner.
No aceptes automáticamente sus conclusiones: verifica en el código los hallazgos CRITICAL/HIGH y las afirmaciones arquitectónicas clave.

Entrega:
1. Resumen ejecutivo.
2. Commit y estado auditado.
3. Mapa arquitectónico real.
4. Inventario de subsistemas.
5. Hallazgos CRITICAL/HIGH/MEDIUM/LOW.
6. God Components/Modules reales.
7. Conflictos de autoridad.
8. Código muerto/legacy.
9. Contratos frontend-backend.
10. Seguridad.
11. Tests/CI/runtime.
12. Documentación vs implementación.
13. Deuda técnica.
14. Bloqueos y puntos no verificables.
15. Dictamen final.

No propongas todavía una reescritura ni ejecutes cambios.
