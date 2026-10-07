# Validación crítica UI BAGO v2.3.2 → v2.3.3

## Método

Se descomprimió `FRONTEND_REFACTORIZADO_BAGO_UI_v2.3.2.zip`, se ejecutó build/typecheck y se renderizó la UI real del bundle `dist` con un bootstrap mock compatible. No se usó la captura enviada por el usuario como prueba única; se generaron capturas nuevas desde el artefacto.

## Validación técnica v2.3.2

- `npm run build`: OK
- `npx tsc --noEmit`: OK
- Capturas generadas: OK
- Backend real BAGO: no validado en este entorno

## Lo que dije que estaba hecho y sí estaba hecho

### Zona roja

La cabecera contextual redundante bajo el topbar ya no existe en v2.3.2.

Prueba DOM:

```json
{
  "hasShellTitle": false
}
```

En la captura nueva de Workspace, el título `Workspace` aparece solo en el topbar. Debajo queda la barra de preparación, no la cabecera grande duplicada.

### Botones sin estilo en Workspace

En v2.3.2 los botones principales de Workspace ya tienen clases de sistema (`toolbar-button`, `filter-chip`, etc.). No quedan botones nativos sin clase dentro de Workspace.

Prueba DOM:

```json
{
  "countNativeButtonsInsideWorkspace": 0,
  "countToolbarButtons": 7
}
```

### Zona verde

Los chips de estado se conservan y están reubicados en la franja compacta de preparación operativa.

## Lo que dije que estaba hecho y no estaba del todo bien

### 1. Pipeline tenía una contradicción de contenido

La captura nueva de v2.3.2 mostraba:

- Badge: `Running`
- Timeline: 4 pasos visibles
- Título: `No hay un flujo activo`

Eso era incorrecto. Aunque los botones ya estaban estilizados, el resumen del pipeline mentía visualmente. La causa era que el título solo leía `planData.task` o `snapshot.system.objective`, ignorando `execution_id` y el hecho de que ya había pasos.

Corrección aplicada en v2.3.3:

```ts
const pipelineTitle = String(
  planData?.task
  || planData?.objective
  || planData?.execution_id
  || snapshot?.system.objective
  || (steps.length ? 'Flujo en ejecución' : 'No hay un flujo activo')
);
```

Resultado visual: el título pasa a `job-ui-232` en la captura mock, y en backend real usará `task`, `objective`, `execution_id` o `Flujo en ejecución` según datos disponibles.

### 2. La barra decía `PREPARACIÓN OP...`

La barra compacta funcionaba, pero el texto `Preparación operativa` se truncaba en algunas anchuras. Eso no era suficientemente ergonómico.

Corrección aplicada en v2.3.3:

- Texto visible reducido a `Preparación`.
- `aria-label` conserva el significado completo: `Preparación operativa XX%`.

## Estado de v2.3.3

- `npm run build`: OK
- `npx tsc --noEmit`: OK
- Capturas generadas: OK

## Veredicto

v2.3.2 no debía aceptarse como cierre visual porque Pipeline aún contenía una contradicción de estado. v2.3.3 corrige esa contradicción y reduce el truncado de la barra de preparación.

Aún no debe marcarse CANON porque no se ha validado con backend BAGO real.

## Capturas v2.3.3 generadas

Se generaron 11 pantallas:

1. Home
2. Workspace
3. Pipeline
4. Contexto
5. Evidencia
6. Grafo
7. Operación
8. Chat split
9. Command palette
10. Help overlay
11. Inspector drawer

