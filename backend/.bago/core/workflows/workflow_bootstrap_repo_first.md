# WORKFLOW · BOOTSTRAP REPO-FIRST

## id

`workflow_bootstrap_repo_first`

## Objetivo

Convertir un repositorio real en contexto operativo utilizable por BAGO antes de iniciar análisis, diseño, ejecución o validación sustantiva.

## Cuándo usarlo

- cuando la tarea depende de un repo real,
- cuando el contexto del proyecto no está cargado,
- cuando el repo cambió de forma relevante,
- cuando hay alta incertidumbre sobre stack, entradas o límites.

## Roles mínimos

- ADAPTADOR_PROYECTO
- INICIADOR_MAESTRO
- ORQUESTADOR_CENTRAL

## Entradas

- árbol del repositorio,
- configuración principal,
- documentación disponible,
- scripts y tests,
- objetivo inicial del usuario,
- `state/global_state.json`.

## Fases

### 1. Lectura del repo

`ADAPTADOR_PROYECTO` inspecciona estructura, stack, puntos de entrada, documentación, configuraciones sensibles y restricciones visibles.

### 2. Traducción a contexto BAGO

Produce:

- tipo de proyecto,
- stack detectado,
- módulos críticos,
- riesgos iniciales,
- objetivo de sesión sugerido,
- modo BAGO sugerido,
- roles iniciales recomendados.

### 3. Arranque del maestro

`INICIADOR_MAESTRO` transforma ese contexto en:

- objetivo operativo actual,
- modo predominante,
- roles iniciales,
- siguiente paso.

### 4. Toma de control del núcleo

`ORQUESTADOR_CENTRAL`:

- clasifica la tarea real,
- decide el workflow de continuación,
- activa los roles necesarios.

## Salidas

- contexto repo-first,
- arranque limpio del maestro,
- workflow de continuación seleccionado.

## Escalado

- `workflow_analysis` si aún falta claridad,
- `workflow_design` si ya hay rediseño,
- `workflow_execution` si el problema ya está acotado.

## Criterio de cierre

El bootstrap se considera correcto cuando puede responderse sin ambigüedad:

- qué repo se está tocando,
- qué quiere el usuario,
- qué modo BAGO domina,
- qué workflow sigue,
- qué roles entran después.
