# BAGO Model Orchestrator — Aprendizaje

## Qué es
El orquestador de modelos de BAGO selecciona automaticamente el modelo
optimo segun:
1. **Tarea del usuario** (keywords → tipo → preferencia de modelo)
2. **Modo de operacion** (offline, economico, estandar, full)
3. **Disponibilidad de proveedores** (health checks en tiempo real)
4. **Coste** (free > included > subscription > openai_credits)
5. **Tamaño del contexto** (32K, 128K, 500K, 1M tokens)

## Modos
| Modo | Proveedores | Uso |
|---|---|---|
| offline | ollama-local | Sin internet, gratis |
| economico | local + copilot | Sin créditos OpenAI |
| estandar | local + cloud + copilot | Sin Codex |
| full | todos | Todo permitido |

## Seleccion automatica de modo
BAGO detecta proveedores disponibles y elige el modo mas restrictivo posible.

## Tareas y modelos preferidos
| Tarea | Modelo preferido | Alternativas |
|---|---|---|
| transponer partitura | qwen25-coder | llama32, gpt-5.3-codex |
| revisar codigo | claude-sonnet-4.6 | gpt-5.4-mini |
| brainstorm | qwen25-coder | llama32, qwen25-mini |
| explicar error | qwen25-coder | llama32 |
| render preview | qwen25-coder | qwen25-mini |
| auditoria profunda | claude-opus-4.7 | gpt-5.5 |
| contexto masivo | kimi-k2-1t | gpt-5.2 |

## Comandos
```bash
BAGO launch                              # Orquestador interactivo
BAGO launch qwen25-coder                 # Modelo específico
BAGO launch --auto "transponer partitura" # Orquesta directamente
python .bago/tools/bago_orchestrator.py --check  # Ver disponibilidad
```

## Archivos
- `.bago/state/model_orchestrator.json` — política de orquestación
- `.bago/tools/bago_orchestrator.py` — implementación
- `.bago/state/model_providers.json` — catálogo de modelos
- `.bago/state/model_routing.json` — reglas por tarea

## Fecha
2026-05-14
