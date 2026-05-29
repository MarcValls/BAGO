# Configuración · BAGO

Este directorio (`\.bago\config\`) aloja la configuración declarativa del framework.

## Archivos actuales

| Archivo | Propósito |
|---------|-----------|
| `harmonic_scales.json` | Configuración de escalas musicales (módulo music) |
| `contracts_config.json` | Catálogo de checkers para contratos operativos |

> **Nota**: `workflow_guidance.json` está documentado en `config/README.md` histórico
> pero **no existe actualmente** en este directorio. Se mantiene la referencia como
> recordatorio de deuda técnica.

## Configuración dispersa conocida (deuda técnica)

La configuración de modelos LLM está actualmente fragmentada en múltiples archivos
de código en vez de residir aquí como JSON declarativo:

| Aspecto | Archivos involucrados | Fuente de verdad temporal |
|---------|----------------------|---------------------------|
| Asignación modelo → agente | `tools/agent_model_manager.py` | `state/llm_config.json` |
| Setup y descubrimiento de providers | `tools/bago_llm_setup.py` | `state/llm_config.json` |
| Registro de modelos accesibles | `tools/bago_models.py` (delega en `bago.model_registry`) | `model_registry` (core) |
| Fallback modelo-a-modelo | `tools/model_gate.py` | `state/model_gate_log.jsonl` |

> **Recomendación de consolidación (futuro)**: Migrar la configuración de
> `state/llm_config.json` a archivos JSON canónicos en este directorio
> (`providers.json`, `models.json`) y hacer que los módulos anteriores lean
> desde aquí en vez de contener lógica de config embebida.

## Configuraciones esperadas

Este directorio debería centralizar configuraciones actualmente dispersas:

- `providers.json` — Configuración de LLM providers.
- `models.json` — Modelos disponibles por provider.
- `gate_config.json` — Umbrales de health score, tests, etc.
- `notification_channels.json` — Canales de alerta (telegram, whatsapp, etc.).

## Regla

Toda configuración en este directorio debe ser JSON válido y versionable. No se admiten archivos de configuración binaria o propietaria.
