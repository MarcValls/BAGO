# BAGO UI v2.3.2 · Hotfix ergonomía Workspace/Pipeline

## Objetivo

Corregir la fricción visual señalada en Workspace: zona contextual redundante, controles de estado mal ubicados y toolbar/fuentes poco ergonómicas. La corrección se aplica como patrón global para todas las ventanas porque `WorkspaceShell` envuelve todas las secciones principales.

## Cambios

- Eliminada la cabecera contextual redundante bajo el topbar. La sección activa ya se comunica en el topbar y en el sidebar.
- Conservados los chips verdes de estado, pero reubicados en una barra compacta coherente junto a la preparación operativa.
- Convertida la zona de Workspace en una `workspace-commandbar` compacta:
  - búsqueda,
  - filtros de tipo,
  - acciones de workspace.
- Eliminado el texto de repertorio que ocupaba espacio sin aportar acción directa.
- Compactado el panel de fuentes y reforzado estilo de inputs/botones.
- Reforzado el estilo de botones y cards en Pipeline para evitar apariencia nativa o desalineada.
- No se tocaron contratos backend ni rutas.

## Validación local

- `npm ci`: OK
- `npm run build`: OK
- `npx tsc --noEmit`: OK
- `npm audit`: falla no bloqueante por Vite/esbuild heredado.

## Estado

DRAFT_VALIDADO_LOCALMENTE. Pendiente de validación con backend BAGO real.
