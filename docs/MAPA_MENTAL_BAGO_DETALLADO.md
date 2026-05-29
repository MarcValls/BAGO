# Mapa Mental Detallado de BAGO

Este documento describe la verdad operativa actual del árbol `E:\`, separando lo que es repo, runtime, estado generado y proyecto real.

## 0. Verdad base

### Raíces reales en `E:\`

- `E:\bago_fw`
  - Checkout principal del runtime BAGO.
  - Aquí viven `bago_core/`, `.bago/`, `install.ps1`, `smoke-test.ps1` y la documentación del runtime.
- `E:\bago_projects\task_manager`
  - Único proyecto real visible ahora mismo fuera del checkout.
  - Contiene `task_manager.py` y `tasks.json`.
- `E:\bago_fw\proyectos`
  - Existe como carpeta, pero está vacía.
- `E:\bago_fw\projects`
  - No existe en este árbol.
- `E:\bago_fw\launcher`
  - No existe en este árbol.

### Consecuencia práctica

- Si un documento dice `projects/music` o `projects/image_generation`, eso no describe el árbol actual de `E:\bago_fw`.
- La verdad operativa para retomar trabajo hoy está en `E:\bago_fw` y `E:\bago_projects\task_manager`.

## 1. Mapa General

```text
BAGO en E:/
├─ checkout/runtime: E:\bago_fw
│  ├─ arranque Windows
│  ├─ launcher Python
│  ├─ runtime .bago
│  ├─ docs canónicos
│  ├─ smoke / validate / cosecha
│  └─ estado generado
└─ proyecto real visible: E:\bago_projects\task_manager
   ├─ task_manager.py
   └─ tasks.json
```

## 2. Frente A: Runtime y arranque

### Qué incluye

- `bago_core/launcher.py`
- `bago_core/installer.py`
- `install.ps1`
- `smoke-test.ps1`
- `E:\START.bat`
- `.bago/tools/tool_registry.py`
- `.bago/tools/smoke_runner.py`
- `.bago/tools/validate_pack.py`

### Qué pasó aquí

- Se corrigió el import roto de `bago.ui` para `_stdin_prompt`.
- Se añadió `bago smoke`.
- `smoke_runner.py` valida:
  - `validate_pack`
  - `health_score`
  - última cosecha cerrada
- El instalador ahora ejecuta `validate` y `smoke`.
- `smoke-test.ps1` también comprueba `bago smoke`.

### Estado actual

- Funciona en el checkout local.
- Necesita confirmación final en instalación limpia real si quieres cerrar completamente este frente.

### Riesgo principal

- El instalador y el launcher pueden comportarse distinto en `C:\Program Files\BAGO`, en el perfil del usuario o en una copia portable.

### Cómo continuar

- Si quieres cerrar estabilidad:
  - validar instalación limpia
  - ejecutar `bago validate`
  - ejecutar `bago smoke`
  - revisar que el alias `default` no caiga en una ruta vieja

## 3. Frente B: Estado y memoria

### Qué incluye

- `.bago/state/global_state.json`
- `.bago/state/sessions/`
- `.bago/state/changes/`
- `.bago/state/evidences/`
- `.bago/state/reports/`
- `.bago/state/sac_locks/`
- `.bago/state/benchmark_last.json`
- `.bago/state/canon_log.json`
- `.bago/state/pending_w2_task.json`
- `.bago/state/recent_projects.json`
- `.bago/state/self_state.json`
- `.bago/state/sprint_plan.json`
- `.bago/state/sprint_summary_07.md`

### Qué pasó aquí

- Se cerró una cosecha real.
- El estado global quedó persistido.
- `health_score` está en `100 green`.
- Pero el árbol está lleno de artefactos generados y temporales.

### Estado actual

- Operativamente verde.
- Git está sucio por estado generado y cambios de runtime.

### Riesgo principal

- Mezclar memoria generada con cambios de código hace muy difícil distinguir qué es funcional y qué es solo histórico.

### Cómo continuar

- Si quieres un commit limpio:
  - separar estado generado de cambios de código
  - decidir qué se conserva y qué se regenera
- Si quieres seguir trabajando:
  - no toques `global_state.json` salvo que sea parte del objetivo

## 4. Frente C: Cosecha y salud

### Qué incluye

- `.bago/tools/cosecha.py`
- `.bago/tools/health_score.py`
- `.bago/tools/health/_score.py`
- `.bago/tools/validate.py`

### Qué pasó aquí

- `cosecha.py` guardaba mal en Windows por encoding y se corrigió a UTF-8.
- Se creó una sesión cerrada real.
- La salud pasó a `100 green`.

### Estado actual

- El flujo está vivo y cerrado correctamente.
- La salud actual no es una promesa: ya está calculada sobre historial real.

### Riesgo principal

- El score puede bajar de nuevo si se rompe `validate_pack`, si cambia el estado o si aparecen desajustes de inventario.

### Cómo continuar

- No perseguir la salud por sí sola.
- Usarla como semáforo, no como objetivo abstracto.

## 5. Frente D: Documentación canónica

### Qué incluye

- `docs/BAGO_CANON.md`
- `docs/operation/GUIA_DE_USO.md`
- `docs/operation/INSTALACION.md`
- `docs/governance/PROTOCOLO_CIERRE_SESION.md`
- `docs/governance/REGLA_INMUTABILIDAD_VALIDACION.md`
- `docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md`
- las copias equivalentes dentro de `.bago/docs/`

### Qué pasó aquí

- Se crearon documentos para cerrar validación.
- Hay duplicación entre `docs/` y `.bago/docs/`.

### Estado actual

- El contenido existe.
- La fuente principal todavía no está unificada del todo.

### Riesgo principal

- Dos copias de la verdad documental pueden divergir.

### Cómo continuar

- Elegir una fuente canónica:
  - `docs/` como lectura humana
  - `.bago/docs/` como fuente de validación
- O viceversa, pero no ambas sin sincronización clara.

## 6. Frente E: Proyectos reales

### Qué existe de verdad

- `E:\bago_projects\task_manager`
  - `task_manager.py`
  - `tasks.json`

### Qué no existe ahora

- No hay `E:\bago_fw\projects`.
- No hay `E:\bago_fw\proyectos` con contenido.
- No se ven `music` ni `image_generation` en este checkout.

### Interpretación

- La conversación anterior sobre ejemplos de proyecto venía de otro árbol o de una copia distinta.
- En este árbol, el proyecto real visible es `task_manager`.

### Cómo continuar

- Si quieres trabajar producto:
  - o vuelves a `task_manager`
  - o localizas el árbol correcto donde estén los ejemplos esperados

## 7. Frente F: Instalación y distribución

### Qué incluye

- `install.ps1`
- `bago_core/installer.py`
- `E:\START.bat`
- `bago.cmd`
- `bago.ps1`

### Qué pasó aquí

- El instalador ahora valida y hace smoke.
- `START.bat` apunta al arranque portátil de `E:\bago_fw`.
- Se reforzó el flujo postinstalación.

### Estado actual

- El camino local es coherente.
- La ruta `Program Files` ya no es el único relato operativo.

### Riesgo principal

- Distintas copias del runtime pueden coexistir:
  - install limpio
  - portable
  - user active install
  - backup

### Cómo continuar

- Decidir cuál es la instalación de verdad para la sesión actual.
- No saltar entre copias sin etiquetarlas.

## 8. Frente G: Git y suciedad de trabajo

### Estado

- Hay muchas modificaciones en:
  - código
  - runtime
  - docs
  - estado generado
- Hay archivos no rastreados que no deberían entrar al mismo commit sin criterio.

### Qué significa

- El árbol no está listo para un commit limpio sin una fase de separación.

### Cómo continuar

- Hacer una de estas dos cosas:
  - limpieza de commit
  - seguir iterando sin intentar empaquetar todavía

## 9. Frentes abiertos de verdad, ordenados por prioridad

### Prioridad 1

- Decidir qué árbol es el de verdad para continuar:
  - `E:\bago_fw`
  - o el árbol de otra instalación/copia

### Prioridad 2

- Separar código de estado generado.

### Prioridad 3

- Confirmar instalación limpia con `validate` + `smoke`.

### Prioridad 4

- Unificar documentación canónica.

### Prioridad 5

- Volver a un proyecto real concreto, hoy visible solo como `E:\bago_projects\task_manager`.

## 10. Mapa de decisión para seguir

### Si estás cansado y quieres avanzar poco

- Ejecuta solo:
  - `bago validate`
  - `bago smoke`
  - `git status --short`

### Si quieres limpiar el árbol

- Decide qué de `.bago/state/` es estado histórico y qué es ruido.
- Mantén fuera del commit lo regenerable.

### Si quieres retomar trabajo funcional

- Elige un frente:
  - runtime
  - instalación
  - documentación
  - proyecto real

### Si quieres volver a producto

- Trabaja sobre `E:\bago_projects\task_manager`.
- No mezcles esa tarea con la limpieza del runtime.

## 11. Regla simple para no perderte otra vez

Un frente = un árbol = una salida.

Si mezclas:

- runtime
- instalación
- estado
- documentación
- proyecto

...acabas reconstruyendo contexto en vez de avanzar.

## 12. Resumen ejecutivo

- `E:\bago_fw` es el checkout/runtime principal.
- `E:\bago_projects\task_manager` es el único proyecto real visible ahora.
- `proyectos/` dentro del checkout está vacío.
- `projects/` no existe en este árbol.
- `validate_pack` y `bago smoke` están en verde.
- La salud está en `100 green`.
- El árbol está funcional, pero sucio por estado generado y cambios acumulados.
- Lo siguiente no es "seguir tocando cosas", sino elegir una línea:
  - estabilidad
  - limpieza
  - producto
