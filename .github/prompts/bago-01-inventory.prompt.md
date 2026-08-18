---
agent: 'agent'
description: 'BAGO workpack: 01 inventory'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Inventario completo

Delega el barrido inicial al agente `bago-repo-explorer` y espera su resultado.

Construye un inventario real del repositorio: frontend, backend, Electron, API, handlers, services, models,
workspace, agents, interpreter, providers, router, GitHub, tools, capabilities, jobs, scheduling, evidence,
context, memory, config, scripts, tests, CI, docs, assets, legacy y experimental.

Clasifica cada área como IMPLEMENTADO, PARCIAL, STUB, MOCK, LEGACY, EXPERIMENTAL, MUERTO o DESCONOCIDO.
No clasifiques como implementado por la mera existencia de un archivo.
Entrega un mapa de subsistemas y puntos que requieren inspección profunda.
