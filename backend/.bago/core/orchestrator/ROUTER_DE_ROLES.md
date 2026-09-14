# Router de roles — gabinete BAGO

## Objetivo

Traducir tipo de tarea, alcance, riesgo y necesidad de trazabilidad en un conjunto de roles.
La vista compacta canónica de combinaciones vive en `MATRIZ_DE_ENRUTADO.md`.
Este archivo solo explica el criterio y las excepciones. El router produce un
plan; un executor autorizado decide y registra cualquier activación.

## Variables

- tipo de tarea,
- alcance,
- impacto estructural,
- riesgo canónico,
- necesidad de empaquetado,
- necesidad de preservación histórica.

## Regla práctica

Usa `MATRIZ_DE_ENRUTADO.md` como vista compacta canónica.
Este archivo solo añade criterios de ajuste para casos con migración histórica o deuda repetida.

- añadir Arquitecto si la migración requiere rediseñar estructura;
- añadir Organizador si la salida final es un pack o ZIP;
- añadir role_vertice solo si la migración revela deuda evolutiva repetida.

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

Los agentes de bootstrap no se añaden automáticamente al gabinete. Después de
resolver el contexto, el gabinete se planifica desde `roles/manifest.json`.
