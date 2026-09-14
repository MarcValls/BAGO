# Qwen Code — BAGO Operating Guide

> Monorepo **BAGO** (current candidate 4.10.x). Windows-first. Backend Python 3.14+, frontend React+TS+Vite, visor Electron con ciclo de vida automático. El runtime de contexto del proyecto es **`.bago/`** (no `.qwen-context/`). Verifica siempre la versión canónica con `bago doctor` o leyendo `release_version.txt`; no confíes en números hard-coded aquí.

## 1. Modo de entrada

Al arrancar una sesión con `qwen-core`, lee en este orden y **para**:

1. `.bago/context/PROJECT_CONTEXT.md` — plan de remediación vigente.
2. `.bago/audits/remediation-closure-contract-*.md` — contrato de cierre (si existe).
3. `.bago/audits/remediation-handoff-*.md` — atribución y vedas.
4. `.bago/decisions/DECISIONS.md` y `.bago/conflicts/CONFLICTS.md` — placeholders canónicos.
5. `.bago/state/` y `.bago/runtime/` — si están vacíos, el canon se reconstituye desde los docs arriba.

No leas el canon completo en cascada. No actives roles hasta tener tarea.

## 2. Piel y tono

- Banner ASCII con logo BAGO + status block enmarcado (versión, provider/model, cwd, tips).
- Tool-call boxes con `╭─╮ │ ╰─╯`. Prefijos: `✓` ok, `✗` fail, `x` rejected, `●` in-flight.
- Tablas con box-drawing `┌─┬─┐ │ ├─┤ └─┴─┘`. Scrollback bordeado `▄▄▄` / `▀▀▀`.
- Interjecciones `✦`, avisos `ℹ️`, safety blocks literales.
- **Nunca** imitar widgets de sistema ("Current tasks", "Status Dashboard"). Memoria `feedback/no-fake-system-panels.md`.
- Verificar ASCII art leyéndolo como texto antes de declararlo bueno. Memoria `feedback/read-rendered-output-literally.md`.

## 3. Settings canónicos del repo

| Settings | Ruta | Quién lo lee | Cómo se edita |
|---|---|---|---|
| UI (versión + nav) | `frontend/public/ui_config.json` | React UI + `bago doctor` cheque `#1` | Manual; `version` debe coincidir con 7 fuentes |
| Selector de runtime | `%LOCALAPPDATA%\BAGO\install_selection.json` | `bago doctor` `#2` + `#3`, `bago.ps1`, launchers | Solo vía `install-v4.ps1` / `global-install-shell.ps1`; no editar a mano |
| Selector legacy | `~\.bago\install_selection.json` | `bago doctor` `#2b` (backward-compat) | Conservar para diagnósticos |

Formas aceptadas de `install_selection.json`: `{active:{path:...}}` o `{roles:{active:{path:...}}}`. UTF-8 con BOM de PowerShell es válido (test cubre).

## 4. Comandos operativos

| Acción | Comando |
|---|---|
| Arrancar dev (backend + frontend + electron) | `npm run dev` (Windows) / `npm run sh:dev` (POSIX) |
| Parar / reiniciar / estado / logs | `npm run stop` `restart` `status` `logs` |
| Build frontend + sincronizar a backend | `npm run build` |
| Typecheck frontend | `npm run typecheck` |
| Tests frontend | `npm run test:frontend` |
| Tests backend | `pytest -q` (raíz backend) |
| Doctor (versiones + selector + bridge) | `bago doctor` / `bago doctor --json` |
| Paquete de remediación (auditoría cerrada) | `python scripts/record_remediation_gate.py` → `verify_remediation_audit.py` → `package_remediation_audit.py` |

## 5. Convenciones de edición

- **Indentación es contrato** (memoria `feedback/bago-indentation-is-load-bearing.md`). Re-leer 5–10 líneas antes de cualquier `edit`. En `bago_core/launcher.py`, `.bago/api/api_dispatch.py`, `bago_core/commands/__init__.py` la alineación por columnas y comas colgantes son obligatorias.
- **Cambios mínimos y defendibles**. Preservar arquitectura salvo que el cambio la pida explícitamente.
- **Estados canónicos** (memoria `qwen-clear-templates`):
  - `EXECUTED` — escrito en disco, sin evidencia de verificación.
  - `VERIFIED` — gates crudos firmados y reproducibles.
  - `VALIDATED` — además, hash de candidato ligado a la baseline.
  - **Nunca** llamar `VERIFIED`/`VALIDATED` a algo que solo es `EXECUTED`.
- **Endpoints del bridge**: handler + ruta introspección + CLI subcomando, juntos. Memoria `feedback/bago-bridge-introspection-endpoint.md`. `api_prefixes` siempre desde `api_dispatch.API_PREFIXES`, nunca literal en `bridge.py`. Memoria `feedback/bridge-api-prefixes-hardcoded.md`.
- **Auth del bridge**: header `X-Bago-Token`, nunca `Authorization: Bearer`. Memoria `feedback/bridge-auth-uses-x-bago-token.md`.
- **Modelos locales**: ante 404 o "not configured", enumerar `where`, `ollama list`, `tasklist` antes de declarar nada. Memoria `feedback/exhaust-local-options-before-404.md`.
- **Inventarios**: distinguir LLM-invocable (OpenAI schema) vs CLI (subprocess) vs scripts (`ScriptRegistry`). Memoria `feedback/bago-inventory-honest-counts.md`.
- **Reescrituras React**: re-renderizar y verificar que el árbol vive antes de declarar hecho. Memoria `feedback/verify-render-after-rewrite.md`.
- **Commits**: el usuario no entrega credenciales. Pedir OK explícito para `git commit` y nunca para `git push`. Memoria `feedback/never-accept-user-credentials.md`.
- **Working directory de Electron**: `Start-Electron` debe usar `$ElectronDir` como cwd. `electron-viewer/package.json` declara `main: main.cjs`; el del frontend no tiene `main`. Cambiar el cwd rompe `npm run dev`. Memoria `feedback/qwen-cwd-is-load-bearing.md`.

## 6. Diagnóstico estándar

- `bago doctor` cubre: coherencia de versión en 7 fuentes, `install_selection.json` canónico y legacy, versión del runtime activo, importabilidad del bridge.
- `bago status` — snapshot de sesión.
- `python -c "from api_dispatch import API_PREFIXES; ..."` — fuente de verdad de rutas del bridge.
- Logs: `backend/.run/backend.log`, `backend/.run/electron.log`, `backend/.run/frontend-build.log`. PowerShell 5.1 colapsa CRLF si se pasa por array → `Get-Content -Raw` + `[System.Text.UTF8Encoding]$false`. Memoria `feedback/replicate-css-with-raw-readfile.md`.
- Lanzador fallback en copia distinta a la editada: comprobar `install_selection.json` no accesible por PowerShell 5.1 (paths con `º`, `ñ`, acentos). Memoria `feedback/bago-multi-copy-grep-divergence.md` y `feedback/multi-copy-bago-edit.md`.

## 7. Reglas duras de iteración

Memoria `feedback/qwen-iteration-budget.md`:

1. Paro por inactividad tras N turnos sin avance verificable.
2. Límite de lecturas consecutivas antes de sintetizar.
3. Hard-cap por tamaño de JSONL acumulado.
4. Freeze por pregunta reformulada — el usuario está corrigiendo dirección.

## 8. Estado de remediación al cierre de esta sesión

- **Remediación BAGO-AUD-001..010**: `EXECUTED` (canon en `PROJECT_CONTEXT.md` + `remediation-closure-contract-20260824.md` + `remediation-handoff-20260824.md`). **No** llamar `VERIFIED` ni `VALIDATED` sin gates crudos reproducibles y bundle de evidencia (`bago-provenance.json` + ZIP).
- **Conflicto abierto**: la baseline inicial solo guardó SHA-256 del diff dirty, no los bytes. Los seis edits pre-remediación en `backend/.bago/api/handlers_jobs.py`, `backend/.bago/core/config_manager.py`, `backend/.bago/core/plan_engine.py`, `backend/.bago/core/session_turn_mixin.py`, `backend/tests/integrations/pi/test_negatives.py`, `backend/tests/test_plan_engine_contract.py` no son reconstruibles. Esto bloquea `VALIDATED` global hasta que se regeneren.
- **Tag `v4.9.1`**: si el tag es annotated, `git rev-parse v4.9.1` devuelve el SHA del **objeto tag**, no del commit target. Para ver a qué commit apunta el tag usa `git show <tag> --no-patch`. El comando `git rev-parse <tag>^{}` también devuelve el commit target directamente.
- **Working tree**: el estado real se consulta con `git status` y `git log origin/main..HEAD --oneline` en cada sesión. No guardes aquí "N commits ahead" ni "tree limpio al cierre"; eso cambia entre checkouts y entre runs.
- **Follow-up `PROPOSED`**: evaluación modular de `frontend/src/app/ControlPlane.tsx` (en `remediation-followups.md`). No parte del cierre de remediación.

## 9. Quick reference de skills cargadas en esta sesión

| Skill | Propósito |
|---|---|
| `qwen-core` | Protocolo base, contexto, evidencia, cierre |
| `qwen-skin-and-tone` | Banner ASCII, tool-call boxes, tono Qwen |
| `qwen-iteration-budget` | 4 reglas duras anti-iteración |
| `qwen-clear-templates` | Plantillas comunicación canon-vs-inferencia |
| `qwen-audit` | Pipeline auditoría 00→14 + 20/21/22 |
| `bago-core` (no cargada; disponible) | Lifecycle, state, evidence-first, closure |
| `bago-auditors` (no cargada; disponible) | Swarm read-only por modo |
| `bago-final-verifier` (no cargada; disponible) | Verificación independiente |

## 10. Plantilla de anuncio al usuario

Antes de la primera tool call: una línea declarando qué voy a hacer.
Tras evidencia: distinguir canon / verificado / inferencia / propuesta.
Sin chit-chat. Sin resúmenes trailing. Cita evidencia con `path:line` o comando literal.
