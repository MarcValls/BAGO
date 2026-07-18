# FRONTEND_REFACTORIZADO_BAGO_UI_v2

Refactor aplicado sobre el frontend entregado en `FRONTEND.zip`.

## Cambios principales

1. Carga inicial canónica mediante `GET /api/v1/ui/bootstrap`, con fallback automático al bootstrap legacy paralelo si el endpoint no existe.
2. Sidebar jerárquico por grupos: Principal, Trabajo y Sistema.
3. Chat convertido en toggle de panel, no en destino normal del sidebar.
4. Fusión visual de Proveedores dentro de Operación/Sistema para evitar duplicidad de destinos.
5. Header reducido: estado, modelo, comandos, workspace, revisión, focus, ayuda y configuración.
6. Inspector convertido en drawer lateral derecho redimensionable, sin quitar altura al workspace.
7. StatusBar inferior eliminado del layout activo.
8. Composer del chat con label visible y contador de caracteres.
9. Overlay de ayuda con atajos: Ctrl K, Ctrl B, ?, Esc, Enter, Shift Enter.
10. Indicador global de carga en el header durante bootstrap, comandos y chat.

## Validación ejecutada

- `npm ci`
- `npm run build`

Build correcto con Vite.

## Endpoints usados como criterio

El frontend queda alineado con el inventario recibido: bootstrap canónico, SSE en `/api/v1/events`, chat normal en `/chat`, streaming en `/chat/stream`, comandos en `/api/v1/commands`, router en `/router/*`, evidencia en `/evidence/*`, jobs en `/jobs/*`, workspace en `/workspace/*` y archivos en `/files/*`.
