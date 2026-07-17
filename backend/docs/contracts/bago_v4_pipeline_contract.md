# Contrato de pipeline de BAGO v4

## Alcance

Este contrato regula el estado de ejecución de pasos, tareas y comandos del pipeline de BAGO.
Es independiente de la taxonomía de sesión y de los estados de madurez o certificación.

## Estados canónicos

- `pending`
- `running`
- `done`
- `failed`
- `blocked`

## Semántica de estados

### Pending

El paso todavía no ha comenzado.

### Running

Existe una ejecución activa.

### Done

La ejecución terminó correctamente, la salida fue validada, existe evidencia suficiente y no hay errores bloqueantes.

### Failed

La ejecución terminó con un error o produjo un resultado inválido.

### Blocked

El paso no puede continuar por una dependencia, restricción, autorización o condición no satisfecha.

## Reglas obligatorias

1. Un paso no puede pasar a `done` sin evidencia asociada.
2. Un paso no puede pasar a `done` solo porque el comando terminó sin excepción.
3. Un `blocked` debe registrar causa estructurada.
4. Un `failed` debe registrar error y punto de fallo.
5. Un estado de pipeline no certifica por sí mismo una capacidad.

## Campos mínimos del paso

- `step_id`
- `status`
- `evidence`
- `block_reason`
- `block_code`

## Transiciones canónicas

- `pending -> running`
- `pending -> blocked`
- `running -> done`
- `running -> failed`
- `running -> blocked`
- `blocked -> pending`
- `blocked -> running`
- `failed -> pending` si existe reintento autorizado

## Validación mínima

```powershell
python -m pytest tests\test_plan_engine_contract.py -q
```
