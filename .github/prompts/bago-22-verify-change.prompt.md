---
agent: 'agent'
description: 'BAGO workpack: 22 verify change'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Verificación independiente

Usa `bago-final-verifier`.

Revisa de forma independiente el cambio descrito en EXTRA_INSTRUCTIONS y el diff actual.
Comprueba alcance, contratos, regresiones, tests, seguridad relevante y evidencia.

Devuelve exactamente uno de:
PASS
FAIL
BLOCKED

Después justifica con evidencias y determina si el cambio puede llamarse VERIFIED.
No edites archivos.
