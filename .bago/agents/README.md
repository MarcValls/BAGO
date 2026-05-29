# Agentes · BAGO

Este directorio (`\.bago\agents\`) contiene agentes de bootstrap, transición y operación. No son el núcleo entero del sistema ni deben invadir el gobierno canónico.

## Contenido

| Tipo | Archivos | Descripción |
|------|----------|-------------|
| **Bootstrap / transición** | `ADAPTADOR_PROYECTO.md`, `INICIADOR_MAESTRO.md` | Arranque contextualizado sobre repo real |
| **Operativos** | `ANALISTA_Contexto.md`, `ARQUITECTO_Soluciones.md`, `CENTINELA_SINCERIDAD.md`, `COPILOT_ALIADO_BAGO.md`, `GENERADOR_Contenido.md`, `GUIA_VERTICE.md`, `MAESTRO_BAGO.md`, `ORGANIZADOR_Entregables.md` | Descripciones textuales de agentes |
| **Contrato técnico** | `agent_contract.json` | Esquema JSON de AgentRequest y AgentResult |
| **Factory** | `agent_factory.py` | Generador de agentes nuevos |
| **Gateway** | `agent_gateway.py` | Punto de entrada para invocar agentes |
| **Herramientas** | `duplication_finder.py`, `logic_checker.py`, `security_analyzer.py`, `smell_detector.py` | Analizadores técnicos |

## Orden recomendado (bootstrap)

1. `ADAPTADOR_PROYECTO.md`
2. `INICIADOR_MAESTRO.md`

## Función del bootstrap

Resolver bien el paso que peor llevaba la línea canónica previa cuando se usaba sobre un repositorio real:

- mirar el proyecto,
- resumir contexto,
- arrancar al maestro con criterio,
- evitar un arranque demasiado abstracto.

## Contrato de agente (`agent_contract.json`)

Define el protocolo de comunicación entre el framework y los agentes:

- **AgentRequest**: `intent`, `context`, `payload`, `options`, `source`
- **AgentResult**: `success`, `intent`, `output`, `artifacts`, `exit_code`, `duration_ms`, `cost_hint`, `adapter`

## Regla

Los agentes en este directorio son **operativos**: realizan trabajo técnico real (análisis, generación, verificación). No deben confundirse con los agentes de **supervisión** (`.bago/supervision/agents/`), que son declarativos y solo vigilan.
