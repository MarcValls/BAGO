---
agent: 'agent'
description: 'BAGO workpack: 20 implement approved pr'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Implementar PR aprobado

Usa `bago-implementation-worker`.

Implementa EXCLUSIVAMENTE el PR o alcance aprobado que aparece en EXTRA_INSTRUCTIONS.
Antes de editar: registra rama, HEAD y git status; identifica tests pertinentes.
No mezcles otros hallazgos ni limpiezas.

Al terminar:
- diff resumido y archivos tocados;
- tests/checks ejecutados con resultado;
- git status;
- riesgos restantes;
- estado EXECUTED/VERIFIED según evidencia real.

No hagas commit ni push salvo instrucción explícita en EXTRA_INSTRUCTIONS.
