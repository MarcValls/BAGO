# Herramientas · BAGO

Este directorio (`\.bago\tools\`) contiene **357 herramientas Python**.
Para evitar duplicidades y solapamientos, toda herramienta nueva debe consultar
este índice antes de crearse.

## Índice por clusters funcionales

### Validación (`validate*`)
| Tool | Rol | Estado |
|------|-----|--------|
| `validate.py` | **Central** — dispatcher de validaciones (manifest, state, pack, roles) | Activo |
| `validate_pack.py` | Validación completa de pack distribuible (ZIP + manifest + estado + roles) | Activo |
| `validate_pack_contents.py` | Validación de contenido interno de un ZIP distribuible | Activo |
| `validate_workflows.py` | Helpers de validación de workflows (desync check) | Activo |
| `validate_sessions.py` | Helpers de compatibilidad de sesiones legacy | Activo |
| `validate_manifest.py` | **DEPRECATED** — shim a `validate.py manifest` | Obsoleto (BAGO 3.6) |
| `validate_state.py` | **DEPRECATED** — shim a `validate.py state` | Obsoleto (BAGO 3.6) |

> **Regla**: Si necesitas validar algo nuevo, extiende `validate.py` antes de crear un `validate_*` adicional.

### Backup (`backup*`)
| Tool | Rol |
|------|-----|
| `backup_manager.py` | Gestor de backups con política de retención |
| `bago_backup_vault.py` | Vault de backups con encriptación/comparación |

> **Nota**: `backup_manager.py` y `bago_backup_vault.py` tienen funciones superpuestas.
> Considerar fusión futura.

### Auditoría (`audit*`)
| Tool | Rol |
|------|-----|
| `audit_state_pointers.py` | Detecta punteros rotos en estado global |
| `audit_utf8_boilerplate.py` | Detecta y migra boilerplate UTF-8 duplicado |
| `audit_v2.py` | Auditoría de compatibilidad con V2 (legacy) |

### Búsqueda (`*search*`)
| Tool | Rol |
|------|-----|
| `code_search.py` | Búsqueda de código en el repositorio |
| `tool_search.py` | Búsqueda de herramientas por palabra clave |
| `search_history.py` | Histórico de búsquedas CLI |
| `research_orchestrator.py` | Orquestación de búsquedas multi-fuente |

### Utilidades compartidas
| Tool | Rol |
|------|-----|
| `bago_utils.py` | **Fuente única de verdad** para I/O JSON, paths, timestamps, UTF-8 bootstrap, reporte de tests |

> **Regla**: Todo archivo `.py` nuevo debe importar `bago_utils.py` en vez de reimplementar
> `load_json`, `save_json`, `timestamp_iso`, `print_test_results`, o el bloque UTF-8.

## Convención de self-tests (`--test`)

Toda herramienta debe implementar autotests invocables con `--test`:

```python
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
```

La función `run_tests()` debe devolver `0` si todos pasan, `1` si alguno falla.
**No copies el boilerplate de reporte** — usa `print_test_results(results)` desde `bago_utils.py`:

```python
from bago_utils import print_test_results

def run_tests():
    results = []
    # ... tus tests ...
    results.append(("nombre_test", ok, f"detalle={valor}"))
    return print_test_results(results)
```

> **Nota**: Se migraron 5 herramientas a este patrón centralizado. El boilerplate
> anterior (`passed = sum(...)`, `failed = sum(...)`, bucle de impresión) está
> obsoleto. Si encuentras una herramienta con el bloque antiguo, migrala.

## Reglas de contribución

1. **No duplicar funciones ya en `bago_utils.py`** (load_json, save_json, etc.).
2. **No crear `validate_*` sin justificar** por qué no cabe en `validate.py`.
3. **No duplicar clusters** — si un cluster ya existe, añadir funcionalidad al existente.
4. **Documentar en este README** cualquier nueva herramienta que cree un cluster.
