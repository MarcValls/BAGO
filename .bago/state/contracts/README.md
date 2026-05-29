# Directorio de contratos operativos · BAGO

Este directorio (`\.bago\state\contracts\`) aloja los contratos operativos verificables del framework.

## Formato

Cada contrato es un archivo `CONTRACT-NNN.json` con la siguiente estructura:

```json
{
  "contract_id": "CONTRACT-001",
  "title": "Mantenimiento de salud del framework",
  "type": "active",
  "deadline": "2026-12-31T23:59:59Z",
  "conditions": [
    {
      "id": "C1",
      "description": "Health score >= 90",
      "type": "health_score",
      "params": {"min": 90},
      "critical": true
    }
  ]
}
```

## Tipos de checker disponibles

Véase `\.bago\state\config\contracts_config.json` para el catálogo completo de checkers.

Los principales son:
- `test_count` — verifica tests pasados.
- `file_exists` — verifica existencia de archivos.
- `health_score` — verifica puntuación de salud.
- `validate_go` — verifica que `bago validate` devuelva GO.
- `tools_count` — verifica número de tools.
- `routing_count` — verifica comandos registrados.

## Comandos

```
bago contract list
bago contract check
bago contract check CONTRACT-001
bago contract status
```
