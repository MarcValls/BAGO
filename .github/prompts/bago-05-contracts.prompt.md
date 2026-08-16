---
agent: 'agent'
description: 'BAGO workpack: 05 contracts'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Contratos frontend-backend

Usa `bago-contracts-auditor` y apóyate en `bago-code-mapper` cuando haga falta.

Construye la trazabilidad:
FRONTEND CALL -> ENDPOINT -> HANDLER -> RESULTADO -> TEST -> ESTADO.

Audita transporte, timeout, cancelación, retries, serialización, parsing, errores, tipos, GET/POST/PUT/DELETE,
streaming y compatibilidad de versiones.

Señala métodos obsoletos, endpoints sin consumidor, UI llamando rutas inexistentes, tipos duplicados
y respuestas asumidas sin validación.
