# BAGO UI v2.3.1 · Hotfix visual

## Objetivo

Corregir controles sin estilo visibles en las pantallas Workspace y Pipeline de la versión v2.3.

## Cambios

- Se añadieron estilos para `pipeline-contract`, `contract-card`, `pipeline-contract-grid` y `contract-group`.
- Se corrigió el bloque de contrato de Pipeline que aparecía como botones nativos blancos.
- Se añadieron estilos para `workspace-sources-panel`, `workspace-source-chip`, `workspace-sources-form` y sus inputs.
- Se corrigieron los inputs blancos de Workspace en el formulario de fuentes.
- Se reforzó `toolbar-button.compact` para que los botones pequeños no parezcan texto plano.
- No se cambiaron contratos TypeScript ni endpoints.

## Validación

- `npm ci`: OK
- `npm run build`: OK
- `npx tsc --noEmit`: OK
- `npm audit`: mantiene deuda heredada de Vite/esbuild; no se corrige en este hotfix.

## Estado

DRAFT_VALIDADO_LOCALMENTE. Sigue pendiente validación con backend BAGO real.
