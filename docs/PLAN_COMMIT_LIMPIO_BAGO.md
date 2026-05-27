# Plan Commit Limpio BAGO

Objetivo: separar lo que conviene conservar, ignorar y preparar para commit.

## 1. Preparar para commit

Estos cambios son funcionales y coherentes entre sí. Forman un commit razonable de runtime:

```text
.gitignore
.bago/tools/bago/ui.py
.bago/tools/cosecha.py
.bago/tools/validate_pack.py
.bago/tools/smoke_runner.py
.bago/tools/_registry_entries_core.py
bago_core/installer.py
bago_core/launcher.py
install.ps1
smoke-test.ps1
```

Tema del commit:

```text
fix(runtime): validate smoke and chat startup on Windows
```

Qué incluye:

- reexportar `_stdin_prompt` desde `bago.ui`
- guardar cosechas en UTF-8 en Windows
- hacer ejecutable `validate_pack.py`
- añadir `bago smoke`
- enganchar `smoke` al instalador y al smoke postinstalación
- ignorar estado runtime generado

## 2. Revisar antes de commit

Estos archivos necesitan decisión explícita:

```text
docs/runtime_contract.json
runtime_contract.json
.bago/state/global_state.json
.bago/docs/
docs/BAGO_CANON.md
docs/PLANTILLA_EVALUACION_BRUTAL_BAGO.md
docs/governance/
docs/operation/
state.example/
```

Motivo:

- `runtime_contract.json` y `docs/runtime_contract.json` ahora no pasan `python -m json.tool` por BOM/encoding y rutas `E:\...`.
- `.bago/state/global_state.json` es estado runtime mutable.
- `.bago/docs/` parece necesario para la validación, pero duplica `docs/`.
- `state.example/` puede ser plantilla publicable, pero debe revisarse antes.

## 3. No preparar para commit

Estos son soporte local, notas de retoma o artefactos portables. Solo entrarían en un commit documental separado:

```text
docs/MAPA_MENTAL_BAGO_ASCII.md
docs/MAPA_MENTAL_BAGO_DETALLADO.md
docs/RETOMA_15_MIN_BRUTAL.md
docs/RETOMA_HOY_3_PASOS.md
docs/RETOMA_RAPIDA_BAGO.md
docs/SEPARACION_CAMBIOS_BAGO.md
INICIO_RAPIDO_PORTABLE.md
SIMULACION_MAC.md
SIMULACION_WINDOWS.md
make-portable.ps1
bago.sh
```

## 4. Ya ignorado

Tras actualizar `.gitignore`, estos quedan clasificados como estado generado:

```text
.bago/sandbox/
.bago/state/benchmark_last.json
.bago/state/canon_log.json
.bago/state/pending_w2_task.json
.bago/state/recent_projects.json
.bago/state/sac_locks/
.bago/state/self_state.json
.bago/state/sprint_plan.json
.bago/state/sprint_summary_*.md
.bago/state/changes/*.json
.bago/state/evidences/*.json
.bago/state/sessions/*.json
.bago/state/sessions/*.md
```

## 5. Secuencia recomendada

1. Commit runtime:

```powershell
git add .gitignore .bago/tools/bago/ui.py .bago/tools/cosecha.py .bago/tools/validate_pack.py .bago/tools/smoke_runner.py .bago/tools/_registry_entries_core.py bago_core/installer.py bago_core/launcher.py install.ps1 smoke-test.ps1
git commit -m "fix(runtime): validate smoke and chat startup on Windows"
```

2. Después revisar documentos canónicos:

```powershell
python -m json.tool docs\runtime_contract.json
python -m json.tool runtime_contract.json
python .bago\tools\validate_pack.py
```

3. Crear un commit documental solo si queda claro qué copia es fuente de verdad:

```text
docs/
.bago/docs/
state.example/
```

## 6. Decisión pendiente

La decisión que falta no es técnica, es de fuente de verdad:

```text
¿La documentación canónica vive en docs/, en .bago/docs/, o se mantiene sincronizada en ambas?
```
