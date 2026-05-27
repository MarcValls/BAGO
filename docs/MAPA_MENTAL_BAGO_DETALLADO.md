# Mapa Mental Detallado de BAGO

Este documento describe la verdad operativa actual del Ã¡rbol `E:\`, separando lo que es repo, runtime, estado generado y proyecto real.

## 0. Verdad base

### RaÃ­ces reales en `E:\`

- `E:\bago_fw`
  - Checkout principal del runtime BAGO.
  - AquÃ­ viven `bago_core/`, `.bago/`, `install.ps1`, `smoke-test.ps1` y la documentaciÃ³n del runtime.
- `E:\bago_projects\task_manager`
  - Ãšnico proyecto real visible ahora mismo fuera del checkout.
  - Contiene `task_manager.py` y `tasks.json`.
- `E:\bago_fw\proyectos`
  - Existe como carpeta, pero estÃ¡ vacÃ­a.
- `E:\bago_fw\projects`
  - No existe en este Ã¡rbol.
- `E:\bago_fw\launcher`
  - No existe en este Ã¡rbol.

### Consecuencia prÃ¡ctica

- Si un documento dice `projects/music` o `projects/image_generation`, eso no describe el Ã¡rbol actual de `E:\bago_fw`.
- La verdad operativa para retomar trabajo hoy estÃ¡ en `E:\bago_fw` y `E:\bago_projects\task_manager`.

## 1. Mapa General

```text
BAGO en E:/
â”œâ”€ checkout/runtime: E:\bago_fw
â”‚  â”œâ”€ arranque Windows
â”‚  â”œâ”€ launcher Python
â”‚  â”œâ”€ runtime .bago
â”‚  â”œâ”€ docs canÃ³nicos
â”‚  â”œâ”€ smoke / validate / cosecha
â”‚  â””â”€ estado generado
â””â”€ proyecto real visible: E:\bago_projects\task_manager
   â”œâ”€ task_manager.py
   â””â”€ tasks.json
```

## 2. Frente A: Runtime y arranque

### QuÃ© incluye

- `bago_core/launcher.py`
- `bago_core/installer.py`
- `install.ps1`
- `smoke-test.ps1`
- `E:\START.bat`
- `.bago/tools/tool_registry.py`
- `.bago/tools/smoke_runner.py`
- `.bago/tools/validate_pack.py`

### QuÃ© pasÃ³ aquÃ­

- Se corrigiÃ³ el import roto de `bago.ui` para `_stdin_prompt`.
- Se aÃ±adiÃ³ `bago smoke`.
- `smoke_runner.py` valida:
  - `validate_pack`
  - `health_score`
  - Ãºltima cosecha cerrada
- El instalador ahora ejecuta `validate` y `smoke`.
- `smoke-test.ps1` tambiÃ©n comprueba `bago smoke`.

### Estado actual

- Funciona en el checkout local.
- Necesita confirmaciÃ³n final en instalaciÃ³n limpia real si quieres cerrar completamente este frente.

### Riesgo principal

- El instalador y el launcher pueden comportarse distinto en `C:\Program Files\BAGO`, en el perfil del usuario o en una copia portable.

### CÃ³mo continuar

- Si quieres cerrar estabilidad:
  - validar instalaciÃ³n limpia
  - ejecutar `bago validate`
  - ejecutar `bago smoke`
  - revisar que el alias `default` no caiga en una ruta vieja

## 3. Frente B: Estado y memoria

### QuÃ© incluye

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

### QuÃ© pasÃ³ aquÃ­

- Se cerrÃ³ una cosecha real.
- El estado global quedÃ³ persistido.
- `health_score` estÃ¡ en `100 green`.
- Pero el Ã¡rbol estÃ¡ lleno de artefactos generados y temporales.

### Estado actual

- Operativamente verde.
- Git estÃ¡ sucio por estado generado y cambios de runtime.

### Riesgo principal

- Mezclar memoria generada con cambios de cÃ³digo hace muy difÃ­cil distinguir quÃ© es funcional y quÃ© es solo histÃ³rico.

### CÃ³mo continuar

- Si quieres un commit limpio:
  - separar estado generado de cambios de cÃ³digo
  - decidir quÃ© se conserva y quÃ© se regenera
- Si quieres seguir trabajando:
  - no toques `global_state.json` salvo que sea parte del objetivo

## 4. Frente C: Cosecha y salud

### QuÃ© incluye

- `.bago/tools/cosecha.py`
- `.bago/tools/health_score.py`
- `.bago/tools/health/_score.py`
- `.bago/tools/validate.py`

### QuÃ© pasÃ³ aquÃ­

- `cosecha.py` guardaba mal en Windows por encoding y se corrigiÃ³ a UTF-8.
- Se creÃ³ una sesiÃ³n cerrada real.
- La salud pasÃ³ a `100 green`.

### Estado actual

- El flujo estÃ¡ vivo y cerrado correctamente.
- La salud actual no es una promesa: ya estÃ¡ calculada sobre historial real.

### Riesgo principal

- El score puede bajar de nuevo si se rompe `validate_pack`, si cambia el estado o si aparecen desajustes de inventario.

### CÃ³mo continuar

- No perseguir la salud por sÃ­ sola.
- Usarla como semÃ¡foro, no como objetivo abstracto.

## 5. Frente D: DocumentaciÃ³n canÃ³nica

### QuÃ© incluye

- `docs/BAGO_CANON.md`
- `docs/operation/GUIA_DE_USO.md`
- `docs/operation/INSTALACION.md`
- `docs/governance/PROTOCOLO_CIERRE_SESION.md`
- `docs/governance/REGLA_INMUTABILIDAD_VALIDACION.md`
- `docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md`
- las copias equivalentes dentro de `.bago/docs/`

### QuÃ© pasÃ³ aquÃ­

- Se crearon documentos para cerrar validaciÃ³n.
- Hay duplicaciÃ³n entre `docs/` y `.bago/docs/`.

### Estado actual

- El contenido existe.
- La fuente principal todavÃ­a no estÃ¡ unificada del todo.

### Riesgo principal

- Dos copias de la verdad documental pueden divergir.

### CÃ³mo continuar

- Elegir una fuente canÃ³nica:
  - `docs/` como lectura humana
  - `.bago/docs/` como fuente de validaciÃ³n
- O viceversa, pero no ambas sin sincronizaciÃ³n clara.

## 6. Frente E: Proyectos reales

### QuÃ© existe de verdad

- `E:\bago_projects\task_manager`
  - `task_manager.py`
  - `tasks.json`

### QuÃ© no existe ahora

- No hay `E:\bago_fw\projects`.
- No hay `E:\bago_fw\proyectos` con contenido.
- No se ven `music` ni `image_generation` en este checkout.

### InterpretaciÃ³n

- La conversaciÃ³n anterior sobre ejemplos de proyecto venÃ­a de otro Ã¡rbol o de una copia distinta.
- En este Ã¡rbol, el proyecto real visible es `task_manager`.

### CÃ³mo continuar

- Si quieres trabajar producto:
  - o vuelves a `task_manager`
  - o localizas el Ã¡rbol correcto donde estÃ©n los ejemplos esperados

## 7. Frente F: InstalaciÃ³n y distribuciÃ³n

### QuÃ© incluye

- `install.ps1`
- `bago_core/installer.py`
- `E:\START.bat`
- `bago.cmd`
- `bago.ps1`

### QuÃ© pasÃ³ aquÃ­

- El instalador ahora valida y hace smoke.
- `START.bat` apunta al arranque portÃ¡til de `E:\bago_fw`.
- Se reforzÃ³ el flujo postinstalaciÃ³n.

### Estado actual

- El camino local es coherente.
- La ruta `Program Files` ya no es el Ãºnico relato operativo.

### Riesgo principal

- Distintas copias del runtime pueden coexistir:
  - install limpio
  - portable
  - user active install
  - backup

### CÃ³mo continuar

- Decidir cuÃ¡l es la instalaciÃ³n de verdad para la sesiÃ³n actual.
- No saltar entre copias sin etiquetarlas.

## 8. Frente G: Git y suciedad de trabajo

### Estado

- Hay muchas modificaciones en:
  - cÃ³digo
  - runtime
  - docs
  - estado generado
- Hay archivos no rastreados que no deberÃ­an entrar al mismo commit sin criterio.

### QuÃ© significa

- El Ã¡rbol no estÃ¡ listo para un commit limpio sin una fase de separaciÃ³n.

### CÃ³mo continuar

- Hacer una de estas dos cosas:
  - limpieza de commit
  - seguir iterando sin intentar empaquetar todavÃ­a

## 9. Frentes abiertos de verdad, ordenados por prioridad

### Prioridad 1

- Decidir quÃ© Ã¡rbol es el de verdad para continuar:
  - `E:\bago_fw`
  - o el Ã¡rbol de otra instalaciÃ³n/copia

### Prioridad 2

- Separar cÃ³digo de estado generado.

### Prioridad 3

- Confirmar instalaciÃ³n limpia con `validate` + `smoke`.

### Prioridad 4

- Unificar documentaciÃ³n canÃ³nica.

### Prioridad 5

- Volver a un proyecto real concreto, hoy visible solo como `E:\bago_projects\task_manager`.

## 10. Mapa de decisiÃ³n para seguir

### Si estÃ¡s cansado y quieres avanzar poco

- Ejecuta solo:
  - `bago validate`
  - `bago smoke`
  - `git status --short`

### Si quieres limpiar el Ã¡rbol

- Decide quÃ© de `.bago/state/` es estado histÃ³rico y quÃ© es ruido.
- MantÃ©n fuera del commit lo regenerable.

### Si quieres retomar trabajo funcional

- Elige un frente:
  - runtime
  - instalaciÃ³n
  - documentaciÃ³n
  - proyecto real

### Si quieres volver a producto

- Trabaja sobre `E:\bago_projects\task_manager`.
- No mezcles esa tarea con la limpieza del runtime.

## 11. Regla simple para no perderte otra vez

Un frente = un Ã¡rbol = una salida.

Si mezclas:

- runtime
- instalaciÃ³n
- estado
- documentaciÃ³n
- proyecto

...acabas reconstruyendo contexto en vez de avanzar.

## 12. Resumen ejecutivo

- `E:\bago_fw` es el checkout/runtime principal.
- `E:\bago_projects\task_manager` es el Ãºnico proyecto real visible ahora.
- `proyectos/` dentro del checkout estÃ¡ vacÃ­o.
- `projects/` no existe en este Ã¡rbol.
- `validate_pack` y `bago smoke` estÃ¡n en verde.
- La salud estÃ¡ en `100 green`.
- El Ã¡rbol estÃ¡ funcional, pero sucio por estado generado y cambios acumulados.
- Lo siguiente no es â€œseguir tocando cosasâ€, sino elegir una lÃ­nea:
  - estabilidad
  - limpieza
  - producto
