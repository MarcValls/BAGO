# Mapa Mental Detallado de BAGO

Este documento describe la verdad operativa actual del ÃƒÂ¡rbol `E:\`, separando lo que es repo, runtime, estado generado y proyecto real.

## 0. Verdad base

### RaÃƒÂ­ces reales en `E:\`

- `E:\bago_fw`
  - Checkout principal del runtime BAGO.
  - AquÃƒÂ­ viven `bago_core/`, `.bago/`, `install.ps1`, `smoke-test.ps1` y la documentaciÃƒÂ³n del runtime.
- `E:\bago_projects\task_manager`
  - ÃƒÅ¡nico proyecto real visible ahora mismo fuera del checkout.
  - Contiene `task_manager.py` y `tasks.json`.
- `E:\bago_fw\proyectos`
  - Existe como carpeta, pero estÃƒÂ¡ vacÃƒÂ­a.
- `E:\bago_fw\projects`
  - No existe en este ÃƒÂ¡rbol.
- `E:\bago_fw\launcher`
  - No existe en este ÃƒÂ¡rbol.

### Consecuencia prÃƒÂ¡ctica

- Si un documento dice `projects/music` o `projects/image_generation`, eso no describe el ÃƒÂ¡rbol actual de `E:\bago_fw`.
- La verdad operativa para retomar trabajo hoy estÃƒÂ¡ en `E:\bago_fw` y `E:\bago_projects\task_manager`.

## 1. Mapa General

```text
BAGO en E:/
Ã¢â€Å“Ã¢â€â‚¬ checkout/runtime: E:\bago_fw
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ arranque Windows
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ launcher Python
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ runtime .bago
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ docs canÃƒÂ³nicos
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ smoke / validate / cosecha
Ã¢â€â€š  Ã¢â€â€Ã¢â€â‚¬ estado generado
Ã¢â€â€Ã¢â€â‚¬ proyecto real visible: E:\bago_projects\task_manager
   Ã¢â€Å“Ã¢â€â‚¬ task_manager.py
   Ã¢â€â€Ã¢â€â‚¬ tasks.json
```

## 2. Frente A: Runtime y arranque

### QuÃƒÂ© incluye

- `bago_core/launcher.py`
- `bago_core/installer.py`
- `install.ps1`
- `smoke-test.ps1`
- `E:\START.bat`
- `.bago/tools/tool_registry.py`
- `.bago/tools/smoke_runner.py`
- `.bago/tools/validate_pack.py`

### QuÃƒÂ© pasÃƒÂ³ aquÃƒÂ­

- Se corrigiÃƒÂ³ el import roto de `bago.ui` para `_stdin_prompt`.
- Se aÃƒÂ±adiÃƒÂ³ `bago smoke`.
- `smoke_runner.py` valida:
  - `validate_pack`
  - `health_score`
  - ÃƒÂºltima cosecha cerrada
- El instalador ahora ejecuta `validate` y `smoke`.
- `smoke-test.ps1` tambiÃƒÂ©n comprueba `bago smoke`.

### Estado actual

- Funciona en el checkout local.
- Necesita confirmaciÃƒÂ³n final en instalaciÃƒÂ³n limpia real si quieres cerrar completamente este frente.

### Riesgo principal

- El instalador y el launcher pueden comportarse distinto en `C:\Program Files\BAGO`, en el perfil del usuario o en una copia portable.

### CÃƒÂ³mo continuar

- Si quieres cerrar estabilidad:
  - validar instalaciÃƒÂ³n limpia
  - ejecutar `bago validate`
  - ejecutar `bago smoke`
  - revisar que el alias `default` no caiga en una ruta vieja

## 3. Frente B: Estado y memoria

### QuÃƒÂ© incluye

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

### QuÃƒÂ© pasÃƒÂ³ aquÃƒÂ­

- Se cerrÃƒÂ³ una cosecha real.
- El estado global quedÃƒÂ³ persistido.
- `health_score` estÃƒÂ¡ en `100 green`.
- Pero el ÃƒÂ¡rbol estÃƒÂ¡ lleno de artefactos generados y temporales.

### Estado actual

- Operativamente verde.
- Git estÃƒÂ¡ sucio por estado generado y cambios de runtime.

### Riesgo principal

- Mezclar memoria generada con cambios de cÃƒÂ³digo hace muy difÃƒÂ­cil distinguir quÃƒÂ© es funcional y quÃƒÂ© es solo histÃƒÂ³rico.

### CÃƒÂ³mo continuar

- Si quieres un commit limpio:
  - separar estado generado de cambios de cÃƒÂ³digo
  - decidir quÃƒÂ© se conserva y quÃƒÂ© se regenera
- Si quieres seguir trabajando:
  - no toques `global_state.json` salvo que sea parte del objetivo

## 4. Frente C: Cosecha y salud

### QuÃƒÂ© incluye

- `.bago/tools/cosecha.py`
- `.bago/tools/health_score.py`
- `.bago/tools/health/_score.py`
- `.bago/tools/validate.py`

### QuÃƒÂ© pasÃƒÂ³ aquÃƒÂ­

- `cosecha.py` guardaba mal en Windows por encoding y se corrigiÃƒÂ³ a UTF-8.
- Se creÃƒÂ³ una sesiÃƒÂ³n cerrada real.
- La salud pasÃƒÂ³ a `100 green`.

### Estado actual

- El flujo estÃƒÂ¡ vivo y cerrado correctamente.
- La salud actual no es una promesa: ya estÃƒÂ¡ calculada sobre historial real.

### Riesgo principal

- El score puede bajar de nuevo si se rompe `validate_pack`, si cambia el estado o si aparecen desajustes de inventario.

### CÃƒÂ³mo continuar

- No perseguir la salud por sÃƒÂ­ sola.
- Usarla como semÃƒÂ¡foro, no como objetivo abstracto.

## 5. Frente D: DocumentaciÃƒÂ³n canÃƒÂ³nica

### QuÃƒÂ© incluye

- `docs/BAGO_CANON.md`
- `docs/operation/GUIA_DE_USO.md`
- `docs/operation/INSTALACION.md`
- `docs/governance/PROTOCOLO_CIERRE_SESION.md`
- `docs/governance/REGLA_INMUTABILIDAD_VALIDACION.md`
- `docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md`
- las copias equivalentes dentro de `.bago/docs/`

### QuÃƒÂ© pasÃƒÂ³ aquÃƒÂ­

- Se crearon documentos para cerrar validaciÃƒÂ³n.
- Hay duplicaciÃƒÂ³n entre `docs/` y `.bago/docs/`.

### Estado actual

- El contenido existe.
- La fuente principal todavÃƒÂ­a no estÃƒÂ¡ unificada del todo.

### Riesgo principal

- Dos copias de la verdad documental pueden divergir.

### CÃƒÂ³mo continuar

- Elegir una fuente canÃƒÂ³nica:
  - `docs/` como lectura humana
  - `.bago/docs/` como fuente de validaciÃƒÂ³n
- O viceversa, pero no ambas sin sincronizaciÃƒÂ³n clara.

## 6. Frente E: Proyectos reales

### QuÃƒÂ© existe de verdad

- `E:\bago_projects\task_manager`
  - `task_manager.py`
  - `tasks.json`

### QuÃƒÂ© no existe ahora

- No hay `E:\bago_fw\projects`.
- No hay `E:\bago_fw\proyectos` con contenido.
- No se ven `music` ni `image_generation` en este checkout.

### InterpretaciÃƒÂ³n

- La conversaciÃƒÂ³n anterior sobre ejemplos de proyecto venÃƒÂ­a de otro ÃƒÂ¡rbol o de una copia distinta.
- En este ÃƒÂ¡rbol, el proyecto real visible es `task_manager`.

### CÃƒÂ³mo continuar

- Si quieres trabajar producto:
  - o vuelves a `task_manager`
  - o localizas el ÃƒÂ¡rbol correcto donde estÃƒÂ©n los ejemplos esperados

## 7. Frente F: InstalaciÃƒÂ³n y distribuciÃƒÂ³n

### QuÃƒÂ© incluye

- `install.ps1`
- `bago_core/installer.py`
- `E:\START.bat`
- `bago.cmd`
- `bago.ps1`

### QuÃƒÂ© pasÃƒÂ³ aquÃƒÂ­

- El instalador ahora valida y hace smoke.
- `START.bat` apunta al arranque portÃƒÂ¡til de `E:\bago_fw`.
- Se reforzÃƒÂ³ el flujo postinstalaciÃƒÂ³n.

### Estado actual

- El camino local es coherente.
- La ruta `Program Files` ya no es el ÃƒÂºnico relato operativo.

### Riesgo principal

- Distintas copias del runtime pueden coexistir:
  - install limpio
  - portable
  - user active install
  - backup

### CÃƒÂ³mo continuar

- Decidir cuÃƒÂ¡l es la instalaciÃƒÂ³n de verdad para la sesiÃƒÂ³n actual.
- No saltar entre copias sin etiquetarlas.

## 8. Frente G: Git y suciedad de trabajo

### Estado

- Hay muchas modificaciones en:
  - cÃƒÂ³digo
  - runtime
  - docs
  - estado generado
- Hay archivos no rastreados que no deberÃƒÂ­an entrar al mismo commit sin criterio.

### QuÃƒÂ© significa

- El ÃƒÂ¡rbol no estÃƒÂ¡ listo para un commit limpio sin una fase de separaciÃƒÂ³n.

### CÃƒÂ³mo continuar

- Hacer una de estas dos cosas:
  - limpieza de commit
  - seguir iterando sin intentar empaquetar todavÃƒÂ­a

## 9. Frentes abiertos de verdad, ordenados por prioridad

### Prioridad 1

- Decidir quÃƒÂ© ÃƒÂ¡rbol es el de verdad para continuar:
  - `E:\bago_fw`
  - o el ÃƒÂ¡rbol de otra instalaciÃƒÂ³n/copia

### Prioridad 2

- Separar cÃƒÂ³digo de estado generado.

### Prioridad 3

- Confirmar instalaciÃƒÂ³n limpia con `validate` + `smoke`.

### Prioridad 4

- Unificar documentaciÃƒÂ³n canÃƒÂ³nica.

### Prioridad 5

- Volver a un proyecto real concreto, hoy visible solo como `E:\bago_projects\task_manager`.

## 10. Mapa de decisiÃƒÂ³n para seguir

### Si estÃƒÂ¡s cansado y quieres avanzar poco

- Ejecuta solo:
  - `bago validate`
  - `bago smoke`
  - `git status --short`

### Si quieres limpiar el ÃƒÂ¡rbol

- Decide quÃƒÂ© de `.bago/state/` es estado histÃƒÂ³rico y quÃƒÂ© es ruido.
- MantÃƒÂ©n fuera del commit lo regenerable.

### Si quieres retomar trabajo funcional

- Elige un frente:
  - runtime
  - instalaciÃƒÂ³n
  - documentaciÃƒÂ³n
  - proyecto real

### Si quieres volver a producto

- Trabaja sobre `E:\bago_projects\task_manager`.
- No mezcles esa tarea con la limpieza del runtime.

## 11. Regla simple para no perderte otra vez

Un frente = un ÃƒÂ¡rbol = una salida.

Si mezclas:

- runtime
- instalaciÃƒÂ³n
- estado
- documentaciÃƒÂ³n
- proyecto

...acabas reconstruyendo contexto en vez de avanzar.

## 12. Resumen ejecutivo

- `E:\bago_fw` es el checkout/runtime principal.
- `E:\bago_projects\task_manager` es el ÃƒÂºnico proyecto real visible ahora.
- `proyectos/` dentro del checkout estÃƒÂ¡ vacÃƒÂ­o.
- `projects/` no existe en este ÃƒÂ¡rbol.
- `validate_pack` y `bago smoke` estÃƒÂ¡n en verde.
- La salud estÃƒÂ¡ en `100 green`.
- El ÃƒÂ¡rbol estÃƒÂ¡ funcional, pero sucio por estado generado y cambios acumulados.
- Lo siguiente no es Ã¢â‚¬Å“seguir tocando cosasÃ¢â‚¬Â, sino elegir una lÃƒÂ­nea:
  - estabilidad
  - limpieza
  - producto
