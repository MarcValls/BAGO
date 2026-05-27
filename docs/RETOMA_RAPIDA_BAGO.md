# Retoma Rápida BAGO

Este documento es un mapa mental práctico para volver al trabajo sin reconstruir toda la conversación.

## Estado actual

- `validate_pack` pasa.
- `health_score` está en `100 green`.
- `bago smoke` existe y valida:
  - `validate_pack`
  - `health_score`
  - última cosecha cerrada
- El instalador ahora llama a `validate` y `smoke`.
- El flujo de cosecha guarda sesión, cambio y evidencia.
- Se corrigió el import roto de `bago.ui` para `_stdin_prompt`.

## Mapa mental

### 1. Base del runtime

Qué cubre:

- `bago_core/launcher.py`
- `bago_core/installer.py`
- `install.ps1`
- `smoke-test.ps1`
- `.bago/tools/smoke_runner.py`
- `.bago/tools/validate_pack.py`

Estado:

- Funciona.
- Hay mejoras recientes en validación y smoke.

Riesgo:

- El instalador debe seguir comportándose igual en una instalación real de Windows, no solo en el checkout local.

Siguiente paso útil:

- Probar una instalación limpia en una VM o en un perfil nuevo.
- Confirmar que `bago validate` y `bago smoke` pasan desde la ruta instalada real.

### 2. Cosecha y salud

Qué cubre:

- `.bago/tools/cosecha.py`
- `.bago/tools/health_score.py`
- `.bago/state/global_state.json`
- `.bago/state/sessions/`
- `.bago/state/changes/`
- `.bago/state/evidences/`

Estado:

- Ya hay una cosecha cerrada.
- La salud subió a `100 green`.

Riesgo:

- `global_state.json` y los artefactos de estado cambian mucho y no conviene mezclarlos con cambios de código si vas a preparar commit.

Siguiente paso útil:

- Decidir si el objetivo es solo retomar trabajo o preparar un commit limpio.
- Si quieres limpiar, separar estado generado de cambios de código.

### 3. Smoke y verificación

Qué cubre:

- `.bago/tools/smoke_runner.py`
- `smoke-test.ps1`

Estado:

- `bago smoke` ya existe.
- El smoke de instalación lo invoca.

Riesgo:

- El smoke puede quedarse corto si cambian los artefactos de estado o la forma de instalar.

Siguiente paso útil:

- Añadir un caso de smoke de instalación real, no solo del checkout.
- Mantener el smoke pequeño y estable.

### 4. Documentación canónica

Qué cubre:

- `docs/BAGO_CANON.md`
- `docs/operation/INSTALACION.md`
- `docs/operation/GUIA_DE_USO.md`
- `docs/governance/PROTOCOLO_CIERRE_SESION.md`
- `docs/governance/REGLA_INMUTABILIDAD_VALIDACION.md`
- `docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md`
- las copias equivalentes dentro de `.bago/docs/`

Estado:

- Hay duplicación entre `docs/` y `.bago/docs/`.

Riesgo:

- Dos fuentes de verdad para documentos canónicos generan drift.

Siguiente paso útil:

- Elegir una fuente principal.
- Si la validación lee `.bago/docs/`, mantener ahí lo canónico y tratar `docs/` como espejo o material de lectura.

### 5. Instalación y distribución

Qué cubre:

- `install.ps1`
- `bago_core/installer.py`
- `bago.cmd`
- `bago.ps1`

Estado:

- La instalación local ya está enlazada con `validate` y `smoke`.

Riesgo:

- Falta confirmar el flujo completo en una instalación limpia real.
- En Windows hay que vigilar encoding, rutas y `Program Files`.

Siguiente paso útil:

- Ejecutar el instalador en una ruta limpia.
- Confirmar que no se rompe por encoding ni por permisos.

## Qué tocar ahora mismo

Si vienes cansado, no intentes abarcar todo. Haz solo una de estas rutas:

1. `Ruta estabilidad`
   - Ejecutar `bago validate`
   - Ejecutar `bago smoke`
   - Ejecutar `smoke-test.ps1`
   - Ver si hay regresión de instalación

2. `Ruta limpieza`
   - Separar código de estado generado
   - Dejar listo un commit limpio
   - No mezclar `global_state.json` con cambios funcionales

3. `Ruta producto`
   - Volver a `projects/music`
   - Volver a `projects/image_generation`
   - Trabajar una feature concreta por proyecto

## Orden recomendado

1. Deja claro si quieres cerrar estabilidad o seguir producto.
2. Si buscas estabilidad, valida instalación limpia primero.
3. Si buscas continuar producto, ignora estado generado y vuelve a un solo frente.
4. Si no sabes por dónde empezar, elige una sola tarea de menos de 30 minutos.

## Regla práctica para no perderte

- Un comando para comprobar.
- Un archivo para tocar.
- Un frente abierto por sesión.

## Comandos de reentrada

```powershell
python .bago\tools\validate_pack.py
python .bago\tools\health_score.py --score-only
python .bago\tools\smoke_runner.py
python bago_core\launcher.py smoke
powershell -ExecutionPolicy Bypass -File .\smoke-test.ps1
```

## Resumen corto

- El runtime funciona.
- El smoke funciona.
- La salud está verde.
- Lo que queda ahora es decidir entre:
  - validar instalación limpia
  - limpiar el árbol para commit
  - volver a un proyecto concreto
