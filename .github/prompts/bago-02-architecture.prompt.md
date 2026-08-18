---
agent: 'agent'
description: 'BAGO workpack: 02 architecture'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Arquitectura real y God Components

Usa `bago-architecture-auditor` como agente principal. Puede apoyarse en `bago-code-mapper` para trazas concretas.

Reconstruye la arquitectura real desde el código.
Analiza fronteras frontend/backend, flujo UI->cliente->API->handler->dominio->persistencia, ownership de estado,
dirección de dependencias, contratos, adapters, runtime y persistencia.

Busca God Components, God Hooks, God Modules, God Services, God Clients y concentraciones CSS,
pero distingue: grande pero cohesivo / fachada legítima / orquestador legítimo / concentración problemática / God real.

Genera además un MAPA DE AUTORIDADES para navegación, paneles, workspace, conversación, chat, providers,
routing, GitHub, Agents, Interpreter, contexto, evidencia y jobs.
Marca CONFLICTO DE AUTORIDAD cuando existan dos fuentes de verdad.
