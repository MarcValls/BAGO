# Cierre UX del Control Plane — 2026-08-09

## Problemas verificados

- La cabecera y el lateral podían parecer operativos aunque el vínculo de workspace no fuese válido.
- Inicio exponía turnos técnicos y JSON como conversación normal.
- Contexto repetía acciones, mostraba rutas y títulos internos, y daba el mismo peso a cuatro vistas.
- Grafo duplicaba el flujo Mención → Tarea → Ejecución sin ser un destino de navegación útil.
- El selector de modelo mostraba todo el catálogo de una vez y el recorrido inicial reaparecía en entornos ya preparados.

## Contrato aplicado

- El bootstrap del backend decide el estado visual del proyecto; la UI no inventa disponibilidad.
- Inicio es la única conversación y pliega la actividad técnica.
- Contexto prioriza `Ahora`, `Tareas` y `Biblioteca`; la configuración queda bajo `Más`.
- Validar e iniciar tarea permanece junto a cada mención o tarea.
- El flujo accionable vive dentro de Pipeline; Capacidades vive dentro de Operación.
- La selección de workspace sigue disponible desde el navegador y aparece como acción correctiva cuando el vínculo falla.
- El selector de modelo es buscable y progresivo; `Automático` es la opción principal.

## Navegación resultante

`Inicio → Workspace → Contexto → Pipeline → Evidencia → Operación`

Pipeline contiene `Ejecución` y `Flujo`. Operación contiene `Capacidades`. No existe un destino lateral separado para Grafo.

## Validación requerida para entrega

- TypeScript sin errores.
- Suite Vitest completa.
- Build canónico en `backend/ui-react/dist`.
- Smoke visual real en claro y oscuro, incluyendo Inicio, Contexto, Pipeline y Operación.
