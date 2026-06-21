# BAGO v4.7 — Notas de Release

**Fecha de publicacion:** 2026-06-21

## Resumen

BAGO v4.7 incorpora **BAGO Code Forge 3B**, el primer pipeline
determinista de generacion de codigo controlado por BAGO. El modelo
local (por defecto `llama3.2:3b`) propone parches, y BAGO se mantiene
como autoridad unica de aceptacion, validacion y aplicacion.

## Cambios principales

- **Code Forge 3B** (`bago_core/codegen/` + `bago_core/validation/` +
  `bago_core/execution/`): pipeline classifier → task compiler → context
  builder → patch parser → validation pipeline → repair loop → code
  verdict → atomic patch → evidence bundle. 121 tests cubren cada paso
  y la integracion de extremo a extremo.
- **Cuatro modos operativos** declarados en el codigo:
  `SAFE` (no aplicar), `STAGED` (stagear), `APPLY` (aplicar si pasa la
  validacion) y `AUTONOMOUS` (aplicar sin confirmacion). El modo lo
  decide el validador, nunca el modelo.
- **Aplicacion atomica con snapshot**: cada parche aplicado deja un
  snapshot en `.bago/snapshots/<ts>_<pid>_<rand>.bago-snap/` y hace
  rollback automatico si la siguiente operacion falla.
- **Evidence bundle JSON-safe** para auditoria externa: incluye
  `task_id`, `CodeVerdict`, historial de intentos, resumen de
  validacion y codigos `LIMIT_*` para que los auditores puedan
  reproducir la decision sin acceso al modelo.
- **Version bump 4.6.4 → 4.7** consolidado en `release_version.txt`,
  `versions.json`, `bago_core/__init__.py`, `pyproject.toml`,
  `package.json`/`package-lock.json`, `README.md`, `MANUAL.md` y los
  contratos publicos.

## Artefactos

- `BAGO-Installation-Manager-4.7-win-x64.exe`
- `bago-v4.7.zip`
- `bago-user-v4.7.zip`
- `bago-audit-v4.7.zip`

## Compatibilidad

- Modelos: cualquier modelo local que el clasificador determinista
  pueda enrutar. Por defecto `llama3.2:3b` en `ollama-local`.
- Sistema: Windows / Linux / macOS. Sin dependencias nuevas en runtime.
- Contratos publicos: el `bago_v4_runtime_contract.json` queda en
  `4.7`. Los presets de routing (`balanced`, `cheap`, `quality`) son
  compatibles hacia atras.

## Estado

- 238 tests passed (8 skipped, 16 subtests passed) en la suite completa.
- Code Forge pasa de "diseno" a "runtime estable" en modo
  `APPLY`/`AUTONOMOUS`. Los modos `SAFE` y `STAGED` siguen siendo el
  camino por defecto para revision humana.
- La limpieza del arbol `.bago/` y la migracion de `test_security_release`
  se documentan como trabajo pendiente fuera de Code Forge.
