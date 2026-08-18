# Arquitectura real y God Components

Usa `bago_architecture_auditor` como agente principal. Puede apoyarse en `bago_code_mapper` para trazas concretas.

Reconstruye la arquitectura real desde el código.
Analiza fronteras frontend/backend, flujo UI->cliente->API->handler->dominio->persistencia, ownership de estado,
dirección de dependencias, contratos, adapters, runtime y persistencia.

Busca God Components, God Hooks, God Modules, God Services, God Clients y concentraciones CSS,
pero distingue: grande pero cohesivo / fachada legítima / orquestador legítimo / concentración problemática / God real.

Genera además un MAPA DE AUTORIDADES para navegación, paneles, workspace, conversación, chat, providers,
routing, GitHub, Agents, Interpreter, contexto, evidencia y jobs.
Marca CONFLICTO DE AUTORIDAD cuando existan dos fuentes de verdad.
