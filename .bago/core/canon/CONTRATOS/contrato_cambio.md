# CONTRATO DE CAMBIO · BAGO AMTEC línea canónica previa

## Objeto

Regular el formato mínimo de un cambio estructural aceptado o preservado dentro del sistema.

## Campos obligatorios

- `change_id`
- `title`
- `type`
- `severity`
- `status`
- `created_at`
- `updated_at`

## Campos recomendados

- `normalized_status`
- `legacy_status`
- `motivation`
- `scope`
- `impacts`
- `requires_migration`
- `validation_result`
- `source_path`
- `raw_markdown_preserved`

## Regla de dualización histórica

Cuando un cambio proviene de una versión previa o de una fuente histórica no normalizada, deben coexistir:

- `legacy_status`: conserva el estado o formulación original.
- `normalized_status`: traduce ese estado a la taxonomía operativa actual.

En estos casos, `status` debe adoptar el valor de `normalized_status` para que el ecosistema actual pueda operar sobre el registro sin perder el matiz histórico.

## Estados permitidos

- proposed
- approved
- approved_with_conditions
- applied
- validated
- rejected
- unknown

## Reglas

- El id debe ser único.
- El título debe describir la mutación real.
- La severidad debe estar justificada.
- Si el cambio es histórico, debe conservar referencia al origen.
- Si el cambio es actual, no debe usar `legacy_status` salvo necesidad explícita de transición.

## Criterio de calidad

Un cambio es de buena calidad si puede ser:

1. leído por humano,
2. comprobado por herramienta,
3. relacionado con una sesión, evidencia o migración.
