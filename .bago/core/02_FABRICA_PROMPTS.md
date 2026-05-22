# 02 · FÁBRICA DE PROMPTS BAGO

La FÁBRICA transforma una necesidad compleja en una lista corta de prompts bien construidos para los roles adecuados. No reemplaza al Orquestador: le da material operativo limpio.

## Propósito

Convertir una petición grande, difusa o multifase en prompts reutilizables, trazables y alineados con el estado del sistema.

## Entradas típicas

- petición del usuario,
- objetivo de sesión,
- modo BAGO predominante,
- workflow elegido,
- roles activos,
- restricciones,
- decisiones congeladas,
- contexto de repositorio,
- historial o resultados previos.

## Salidas

Una lista de prompts estructurados con `01_PLANTILLA_PROMPT.md`, por ejemplo:

- prompt para análisis,
- prompt para diseño,
- prompt para generación,
- prompt para cierre o actualización de estado.

## Proceso interno

### 1. Agrupar necesidades

Separar:

- análisis,
- diseño,
- generación,
- organización,
- revisión evolutiva.

### 2. Mapear a roles

Asignar cada grupo al rol correcto y evitar solapes.

### 3. Construir prompts

Rellenar la plantilla con entradas y formato útiles.

### 4. Priorizar

Indicar:

- qué prompts van primero,
- cuáles dependen de otros,
- cuáles se pueden omitir si ya existe contexto suficiente.

### 5. Revisar consistencia

Comprobar:

- que el modo BAGO elegido tiene sentido,
- que el prompt no contradice el workflow,
- que no se está pidiendo a un rol invadir otra frontera.

## Uso recomendado en V2.2

### Caso A · Repo nuevo o no leído

1. `00_BOOTSTRAP_PROYECTO`
2. `01_ARRANQUE_MAESTRO`
3. `02_ANALISIS_REPO`

### Caso B · Tarea concreta del proyecto

1. `03_TAREA_DE_PROYECTO`
2. prompt adicional para ARQUITECTO o GENERADOR si la tarea se complica
3. `05_ACTUALIZACION_ESTADO_BAGO`

### Caso C · Deriva o incoherencia

1. `04_REVISION_EVOLUTIVA`

## Criterio de calidad

La FÁBRICA funciona bien si:

- reduce fricción,
- reduce repetición,
- mantiene trazabilidad,
- hace más clara la secuencia de trabajo.

No funciona bien si genera más ceremonia que utilidad.
