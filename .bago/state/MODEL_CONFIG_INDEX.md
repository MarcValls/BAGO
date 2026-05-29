# Índice de Configuración de Modelos (INC-004)

La configuración de modelos está dispersa en 4 archivos JSON dentro de
`.bago/state/`. Este documento explica la función de cada uno y la razón de la
dispersión.

## Archivos

| Archivo | Propósito | Razón de existencia independiente |
|---------|-----------|-----------------------------------|
| `model_providers.json` | Catálogo de providers y modelos (ollama-local, copilot, codex) con metadatos técnicos (tamaño, tokens, coste). | Consumido por el instalador y el doctor para verificar disponibilidad de modelos locales. |
| `model_orchestrator.json` | Modos de operación (offline, económico, estándar, full), fallback chains y thresholds de contexto. | Define la política de selección de modelo según modo de ejecución. Cambia más frecuentemente que el catálogo. |
| `model_routing.json` | Reglas de routing basadas en keywords de intención del usuario. | Permite enrutar a modelos específicos sin modificar el orquestador. Desacoplado para permitir hot-updates. |
| `field/model_field_matrix.json` | Matriz de campo magnético: poles (local, coding, reasoning, creative) y relaciones entre modelos. | Concepto experimental del "campo magnético BAGO". Puede evolucionar o consolidarse en el futuro. |

## Relación

```
user_intent ──► model_routing.json ──► candidato inicial
     │
     ▼
model_orchestrator.json ──► modo + fallback chain
     │
     ▼
model_providers.json ──► verifica disponibilidad local
     │
     ▼
model_field_matrix.json ──► ajuste contextual (experimental)
```

## Recomendación futura

Considerar consolidar `model_providers.json` + `model_orchestrator.json` en un
único archivo si la frecuencia de cambio se estabiliza. `model_routing.json`
debería mantenerse separado para permitir hot-updates sin tocar el core.
`model_field_matrix.json` es experimental: si madura, integrar su lógica en
el orquestador; si no, eliminar en BAGO 3.6.
