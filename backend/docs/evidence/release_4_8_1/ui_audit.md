# Auditoria UI de cierre 4.8.1

## Superficie activa

- Entry: `frontend/src/main.tsx` -> `app/ControlPlane.tsx`.
- Navegacion: estado local tipado, sin router externo.
- Backend: autoridad HTTP mediante `frontend/src/api/client.ts`.
- Artefacto servido: `backend/ui-react/dist`.

## Problemas cerrados

- P0: composer y selector de modelos visibles en Inicio/Chat.
- P0: Pipeline con estados vacio, edicion y accion principal.
- P0: Contexto editable sin titulos repetidos.
- P1: recorrido inicial real con proveedor, workspace y proyecto demo.
- P1: scroll y responsive del recorrido a 500x700 y 1440x900.
- P1: catalogo completo visible; 36 modelos de cuatro providers disponibles.

## Navegacion validada

`Inicio -> Chat`, `Pipeline`, `Contexto`, `Evidencia`, `Grafo` y `Operacion`.
El recorrido inicial se abre automaticamente hasta completarlo y puede reabrirse desde Ayuda.

## Integraciones reales

- `POST /providers/configure`
- `POST /project/demo`
- `POST /project/init`, `/project/link`, `/project/seed`
- `GET /providers`, `/router/list`, `/ui/bootstrap`

No se anadieron botones decorativos ni APIs simuladas.
