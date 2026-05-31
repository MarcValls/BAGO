# Contrato de evidencia de BAGO v4

## Propósito

Una evidencia válida en BAGO v4 no es una nota libre: es un bundle reproducible que demuestra que el runtime asistió al usuario y dejó artefactos reutilizables.

## Campos obligatorios

Toda evidencia debe incluir en `manifest.json`:

- `bundle_id`
- `contract_version`
- `related_to`
- `summary`
- `details`
- `status`
- `recorded_at`
- `validation_commands`
- `checks`
- `artifacts`
- `files`

## Tipos de evidencia

| Tipo | Qué demuestra |
|------|----------------|
| `session-runtime` | El runtime creó y guardó una sesión real. |
| `direct-assistance` | Hubo una respuesta útil al usuario. |
| `knowledge-persistence` | El aprendizaje quedó recuperable. |
| `plan-generation` | El sistema produjo un plan reutilizable. |
| `live-provider-health` | Un provider real respondió con salud positiva. |

## Entornos demostrables

### 1. Simulated

**Definición:** ejecución en entorno temporal, sin dependencia de provider externo, usando el runtime real de `SessionManager`, `KnowledgeBase` y parser REPL.

**Comando contractual:**

```powershell
python bago_core\cli.py evidence --mode simulated --objective community-knowledge --output docs\evidence\example_bundle --overwrite
```

**Objetivos mínimos:**

1. Crear una sesión persistente con `context.jsonl`, `timeline.jsonl`, `tokens.json`, `meta.json`.
2. Emitir una respuesta útil al objetivo planteado.
3. Generar un plan mediante `/plan`.
4. Persistir una memoria recuperable mediante `/memory add` y `/memory search`.
5. Guardar un bundle con `manifest.json`, `report.md` y `checksums.sha256`.

### 2. Real

**Definición:** ejecución con provider y modelo reales ya configurados en el repo.

**Comando contractual:**

```powershell
python bago_core\cli.py evidence --mode real --provider <provider> --model "<modelo>" --output <directorio>
```

**Objetivos mínimos:**

1. Confirmar salud positiva del provider.
2. Obtener una respuesta viva no vacía.
3. Añadir y recuperar memoria vinculada a la sesión.
4. Guardar el estado de la sesión y exportar el bundle.

## Regla de aceptación

Una evidencia falla si cualquiera de sus `checks` queda en `fail` o si el bundle no puede regenerarse con el mismo comando declarado.

## Validación del generador

```powershell
python bago_core\cli.py evidence --test
```

