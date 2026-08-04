# BAGO Pending Integrations Audit

Fecha: 2026-07-17
Alcance: arbol principal del repo `backend/` + `frontend/`

## Resumen

La parte de estado canonico de la UI ya esta cableada. `menuState` entra por backend y se consume en Inicio, Sidebar y Header. El backlog real ya no es "falta menuState", sino:

1. drift de rutas en tests de release,
2. normalizacion de autoridad `.bago` / `.gabo`,
3. promocion controlada del puente PI,
4. cierre de superficies legacy que siguen siendo compatibles pero no canonicas.

## Integrado

- `frontend/src/contracts/backend.ts`: contrato UI con `menuState` ampliado.
- `frontend/src/app/ControlPlane.tsx`: mapeo del `menu_state` del backend al snapshot de UI.
- `frontend/src/features/sections.tsx`: Inicio consume la accion recomendada.
- `frontend/src/layout/MainSidebar.tsx`: resaltado guiado de la accion/centro recomendado.
- `frontend/src/layout/GlobalHeader.tsx`: expone el contexto operativo global.
- `backend/.bago/api/handlers_session.py`: `/session` devuelve `menu_state`.
- `backend/.bago/api/handlers_ui_bootstrap.py`: `/api/v1/ui/bootstrap` agrega `menu_state`, workspace, jobs, evidence y audit.
- `backend/.bago/api/handlers_workspace.py`: estado de workspace con acciones permitidas, bloqueadas y recomendadas.
- `backend/.bago/core/contract_state.py`: generacion canonical de menu/workspace/welcome state.
- `backend/.bago/integrations/pi/`: bridge PI presente y protegido por fases.

## Pendientes de integracion

### P0 - drift de ruta en tests de release

Evidencia:
- `backend/tests/test_security_release.py` y `backend/tests/test_e2e.py` leen `release_version.txt` desde `backend/tests/`.
- El archivo real vive en `backend/release_version.txt`.
- Resultado: error de coleccion antes de ejecutar la suite.

Impacto:
- rompe validacion de release,
- oculta fallos reales detras de un fallo de filesystem,
- dificulta CI y smoke tests.

### P1 - normalizacion de autoridad de estado

Evidencia:
- runtime actual usa `.gabo` como workspace state root,
- sigue habiendo mucha superficie legacy `.bago` en tools, docs y handlers compatibles,
- la compatibilidad existe, pero la autoridad debe quedar declarada por una sola via por superficie.

Impacto:
- ambiguedad sobre donde vive el estado canonico,
- riesgo de discrepancia entre docs, tests y runtime,
- mas coste de mantenimiento al integrar nuevas features.

### P1 - promocion del bridge PI

Evidencia:
- el bridge existe, pero su propia documentacion lo mantiene en cuarentena y por fases,
- falta pasar de "presente" a "promovido" con smoke test y canary reales,
- mutaciones siguen bloqueadas por diseno.

Impacto:
- no es un bug; es una integracion incompleta por politica,
- no debe mezclarse con features de usuario hasta validar attestation/receipts.

### P2 - superficies legacy compatibles pero no canonicas

Evidencia:
- `/menu`, `/session`, `/workspace/status` y `/api/v1/ui/bootstrap` coexisten,
- `ui-react` ya consume el bootstrap, pero aun hay rutas de compatibilidad y lecturas redundantes.

Impacto:
- la UI puede seguir funcionando,
- pero el contrato de entrada debe converger para reducir ramas de logica.

## Plan de integracion

### Fase 1 - cerrar el drift de tests

Objetivo:
- hacer que la suite de release arranque y mida el estado real.

Acciones:
1. fijar la raiz correcta en `test_security_release.py` y `test_e2e.py`.
2. ejecutar coleccion/pytest de esas superficies.
3. revisar si hay mas tests con `parent` cuando necesitan `parents[1]`.

Validacion:
- coleccion sin FileNotFoundError,
- release tests verdes o fallando ya por logica real.

### Fase 2 - declarar una sola autoridad de estado por superficie

Objetivo:
- que docs, tests y runtime hablen el mismo idioma.

Acciones:
1. revisar `.bago` vs `.gabo` en docs activas y tests.
2. mantener `.bago` como runtime/framework y `.gabo` como estado de workspace donde aplique.
3. documentar compatibilidad legacy solo cuando exista camino activo.

Validacion:
- una ruta canonica por tipo de estado,
- menos heuristicas duplicadas en handlers y tests.

### Fase 3 - promocion del puente PI

Objetivo:
- pasar de cuarentena a canary controlado.

Acciones:
1. smoke test real en el bridge.
2. canary con workspace explicitamente controlado.
3. comprobar receipts, WAL y rechazo de mutaciones.

Validacion:
- attestation estable,
- resultados reproducibles,
- rollback posible sin contaminar la sesion.

### Fase 4 - converger bootstrap UI

Objetivo:
- que la UI use una entrada principal y deje las demas como compatibilidad.

Acciones:
1. mantener `/api/v1/ui/bootstrap` como fuente principal para frontend moderno.
2. reducir lecturas duplicadas de `session` y `workspace` en la UI.
3. dejar `menuState` como contrato estable de guia operativa.

Validacion:
- Inicio/Trabajo/Workspace/Control/Sistema muestran el mismo estado base,
- la accion recomendada ilumina el camino sin depender de rutas duplicadas.

## Prioridad real

1. corregir tests rotos por ruta.
2. normalizar autoridad de estado.
3. promover PI con canary.
4. limpiar compatibilidad legacy de la UI.

