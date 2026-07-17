# ROUTER DE ROLES · BAGO AMTEC línea canónica previa CORREGIDO

## Objetivo

Traducir tipo de tarea, alcance, riesgo y necesidad de trazabilidad en un conjunto de roles. Esta versión corrige la ambigüedad anterior reforzando un caso específico: el de migración histórica fiel.

## Variables

- tipo de tarea,
- alcance,
- impacto estructural,
- riesgo canónico,
- necesidad de empaquetado,
- necesidad de preservación histórica.

## Rutas principales

### Diagnóstico

- Orquestador
- Analista
- Validador

### Diseño

- Orquestador
- Analista
- Arquitecto
- Validador

### Ejecución simple

- Orquestador
- Generador
- Validador

### Ejecución estructural

- Orquestador
- Arquitecto
- Generador
- Validador

### Organización y empaquetado

- Orquestador
- Organizador
- Validador

### Migración histórica fiel

- Orquestador
- Analista
- Auditor Canónico
- Validador

Añadir Arquitecto si la migración requiere rediseñar estructura.
Añadir Organizador si la salida final es un pack o ZIP.
Añadir role_vertice solo si la migración revela deuda evolutiva repetida.

## Señales de mal enrutado

- se pierde el origen del dato,
- se confunde migrado con inventado,
- el manifiesto no resuelve desde su propia ubicación,
- el árbol no refleja el paquete final,
- prompts y plantillas se quedan tan breves que ya no sostienen el uso real.

## Ruta 0 · Bootstrap repo-first

Se usa antes de la ruta de análisis, diseño o ejecución cuando el trabajo depende de un repo real aún no leído suficientemente.

Roles mínimos:

- `ADAPTADOR_PROYECTO`
- `INICIADOR_MAESTRO`
- `ORQUESTADOR_CENTRAL`

Objetivo:

- leer el repo,
- traducirlo a contexto BAGO,
- arrancar al maestro,
- decidir el workflow de continuación.
