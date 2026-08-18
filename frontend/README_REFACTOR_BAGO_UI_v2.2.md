# BAGO UI v2.2 · Mejora de interfaz

Estado: DRAFT_VALIDADO_LOCALMENTE
Base: FRONTEND_REFACTORIZADO_BAGO_UI_v2.1

## Objetivo

Mejorar la experiencia de la interfaz sin cambiar los contratos backend. Esta iteración se centra en claridad visual, orientación del usuario y reducción de ambigüedad en los controles principales.

## Cambios aplicados

1. Header contextual por sección en `WorkspaceShell`.
   - Título, descripción breve y estado operativo por sección.
   - Chips de estado para backend, workspace y modelo.
   - Mantiene modo Focus sin ruido adicional.

2. Home rediseñado como cockpit operativo.
   - Sustituye tarjetas duplicadas por tres bloques: siguiente acción, señales operativas y atajos de trabajo.
   - Usa `snapshot.recommendedActions` cuando el backend las proporciona.
   - Muestra señales compactas de backend, workspace, contexto y modelo.

3. Chat como toggle explícito.
   - El botón del sidebar abre/cierra el chat.
   - Ya no cambia de split a focus de forma implícita.
   - El modo focus queda dentro del propio panel de chat.

4. Activity toast.
   - Recupera visibilidad para `lastMessage` tras haber eliminado el StatusBar inferior.
   - Muestra actividad de bootstrap, comandos, chat, eventos SSE y errores.
   - No ocupa layout permanente.

5. Pulido responsive.
   - El header contextual se pliega verticalmente en pantallas medias.
   - El toast se adapta a móvil.
   - Las nuevas tarjetas del home pasan a una columna en anchos reducidos.

## Archivos modificados

- `src/app/ControlPlane.tsx`
- `src/layout/MainSidebar.tsx`
- `src/layout/WorkspaceShell.tsx`
- `src/features/sections.tsx`
- `src/styles.css`

## Validación local

Ejecutado:

```bash
npm ci
npm run build
npx tsc --noEmit
npm audit --audit-level=moderate
```

Resultado:

- `npm ci`: OK con 2 vulnerabilidades heredadas.
- `npm run build`: OK.
- `npx tsc --noEmit`: OK.
- `npm audit`: FAIL no bloqueante por Vite/esbuild heredado. La corrección automática requiere salto mayor.

## Pendiente

- Validación funcional contra backend BAGO real.
- Prueba de `/api/v1/ui/bootstrap` y `/api/v1/events`.
- Prueba visual con datos reales de workspace, context, evidence, jobs y router.
- Ciclo separado para actualizar Vite/esbuild si se quiere cerrar `npm audit`.
