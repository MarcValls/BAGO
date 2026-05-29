# Dashboard · BAGO

Este directorio raíz (`\.bago\`) contiene los archivos del dashboard visual del framework.

## Archivos

| Archivo | Propósito |
|---------|-----------|
| `dashboard.html` | Interfaz visual del dashboard (estático, navegable) |
| `dashboard_data.json` | Datos estructurados que alimenta el dashboard |

## Uso

Abrir `dashboard.html` en un navegador. Lee `dashboard_data.json` vía fetch local.

## Regeneración

El dashboard se regenera con:

```bash
bago dashboard
```

Esto ejecuta `pack_dashboard.py` y actualiza `dashboard_data.json`.

## Regla

`dashboard_data.json` es **generado automáticamente**. No editar manualmente. La fuente de verdad está en el estado real del framework (`pack.json`, `roles/`, `tools/`, etc.).
