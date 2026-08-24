# Follow-ups posteriores al baseline de remediación

Estado: `PROPOSED` (no forma parte del cierre AUD-001..010).

## Evaluación modular de `frontend/src/app/ControlPlane.tsx`

Evaluar con el protocolo de modularidad antes de implementar. Fronteras candidatas:

- shell, navegación y persistencia de UI;
- coordinación de chat, visión y portapapeles;
- overlays, confirmaciones e inspector;
- carga/refresh de contratos backend;
- contexto, workspace y pipeline;
- lifecycle de Electron y paneles de sistema.

Criterio previo: mapa de ownership y contratos, pruebas de caracterización y una
extracción incremental por PR sin cambiar comportamiento ni autoridad backend.
