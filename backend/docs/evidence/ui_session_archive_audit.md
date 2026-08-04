# Auditoría UI: recuperación de sesiones archivadas

## Superficie y autoridad

- UI activa: `frontend/src/layout/ChatPanel.tsx`, integrada por `ControlPlane.tsx`.
- Autoridad: `/sessions`, `handlers_sessions.py` y `session_registry.py`.
- Navegación: el gestor sigue siendo el único punto visible para renombrar, archivar y restaurar.

## Hallazgo

- P1: archivar conservaba el historial, pero ocultaba la sesión sin una ruta visual de recuperación.
- P1: el bootstrap no transportaba el catálogo archivado y podía desincronizar la UI de `/sessions`.
- P0/P2 relacionados: ninguno abierto en este flujo.

## Decisión aplicada

- Mantener sesiones activas y archivadas como colecciones separadas del mismo contrato backend.
- Añadir búsqueda, orden y restauración dentro de `Gestionar sesión`, sin crear otro destino.
- Restaurar reactiva y abre la sesión; una sesión archivada no puede abrirse mediante `switch`.
- No ofrecer borrado definitivo para preservar recuperabilidad.

## Mapa de interacción

`Sesión activa → Gestionar sesión → Archivar → Sesión sustituta → Gestionar sesión → Buscar/ordenar archivadas → Restaurar → Sesión recuperada`

No hay datos simulados ni botones sin comportamiento en este flujo.
