# Auditoria brutal de distribucion BAGO - 2026-05-21

## Veredicto

- `C:\Program Files\BAGO`: GO como runtime limpio instalado.
- `C:\Program Files\BAGO\.bago`: GO como framework runtime segun contrato.
- `C:\ProgramData\BAGO\user`: GO como estado mutable externo a Program Files.
- `C:\Users\AMTEC_Terminal_1º\bago-knowledge`: GO como repo de conocimiento sincronizable.
- `E:\.bago`: GO parcial como memoria ligera de workspace.
- `E:\bago_fw`: GO como runtime limpio reconstruido con destino parametrizado.

## Bloqueantes encontrados y corregidos

1. El instalador limpiaba solo la raiz de `C:\Program Files\BAGO`, no el primer nivel de `.bago`.
2. `validate.py` exigia `docs/` y `state.example/` aunque el contrato limpio los expulsaba del runtime.
3. `runtime_contract.json` generado no incluia `tree`, por lo que el runtime no era auto-verificable.
4. PowerShell generaba `runtime_contract.json` con BOM UTF-8 y Python ignoraba el contrato.
5. Ejecutar BAGO generaba `__pycache__` dentro de `Program Files`.
6. El launcher instalado enlazaba la carpeta de desarrollo como secundaria.
7. La suite tenia 3 fallos reales: safety warning de `autonomous`, drift README-registry y metrica README rota.
8. `E:\bago_fw` ejecutaba contra `E:\.bago` por prioridad USB; ahora ejecuta contra `E:\bago_fw\.bago`.

## Estado validado

Instaladores:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-without-knowledge.ps1
& "C:\Program Files\BAGO\bago.cmd" validate
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1
& "C:\Program Files\BAGO\bago.cmd" validate
```

Resultado:

```text
GO manifest
GO state
GO pack
```

Knowledge:

```text
Canonical entries: 17
Runtime files:     19
Repo files:        19
Missing in repo:   0
Missing in runtime:0
```

Tests:

```text
425 passed, 4 skipped, 18 xfailed, 5 xpassed
```

Auditoria de comandos sobre `C:\Program Files\BAGO`:

```text
Registry total:          170
Core:                     44
Dangerous:                 8
Experimental:             85
Legacy:                   28
Internal:                  5
Safe:                    146
Mutating:                 16
Dangerous risk:            8
Preflight error cmds:      0
Preflight warning cmds:    0
Menu dispatch OK:        170/170
```

Nota: `Menu dispatch OK` valida que todos los comandos mostrados por el menu
`Todos los comandos` despachan a `bago <cmd>` sin caer en handlers internos ni
en `Desconocido`. No ejecuta acciones destructivas; dangerous/mutating se
validan por registry/preflight y por ruta de despacho, no por ejecucion real.

Sandbox de comandos `dangerous` / `mutating`:

```text
Sandbox runtime: E:\tmp\bago_danger_sandbox\BAGO
Sandbox user:    E:\tmp\bago_danger_sandbox\user
Sandbox cwd:     E:\tmp\bago_danger_sandbox\project

Risk commands total:          24
Preflight errors:              0
Launcher preflight failures:   0
Dangerous guard failures:      0
Dry-run failures:              0
```

Hallazgo corregido durante esta prueba: algunos comandos con rama especial
podian saltarse la tuberia comun de `tool_registry` para `--preflight` y guardia
de riesgo. El launcher ahora enruta cualquier comando `mutating` o `dangerous`
por `_dispatch` antes de ramas especiales, garantizando preflight, risk guard y
propagacion de exit code.

## Evidencia de limpieza

- Perfil final: `with-knowledge`.
- `knowledge_included`: `true`.
- `C:\Program Files\BAGO` no contiene entradas fuera de `runtime_contract.json/root.keep`.
- `C:\Program Files\BAGO\.bago` no contiene entradas fuera de `runtime_contract.json/tree.keep`.
- No quedan `__pycache__`, `.pytest_cache`, `.ruff_cache` ni `.mypy_cache` en el runtime instalado tras ejecutar comandos.
- `status` en runtime instalado solo muestra primaria `C:\Program Files\BAGO\.bago`; no engancha el repo de desarrollo como secundaria.

## Estado de E:

Medicion:

```text
C:\Program Files\BAGO              892 items   46.11 MB
C:\Program Files\BAGO\.bago        875 items   45.89 MB
C:\Users\AMTEC_Terminal_1º\BAGO   3066 items 135.28 MB
E:\bago_fw                         892 items  46.11 MB
E:\.bago                           200 items   1.61 MB
E:\.models                          28 items   8.39 GB
E:\tmp                            1698 items  71.64 MB
```

Estado anterior de `E:\bago_fw` preservado en backups:

- `E:\bago_fw.backup.20260521-194300`: arbol viejo con residuos.
- `E:\bago_fw.backup.20260521-194417`: primera reconstruccion limpia antes del fix de prioridad launcher.

Validacion actual de `E:\bago_fw`:

```text
Fuente de verdad: E:\bago_fw\.bago (INSTALADO)
GO manifest
GO state
GO pack
```

## Dictamen arquitectonico

La arquitectura abstracta correcta queda asi:

```text
C:\Program Files\BAGO\        runtime instalado limpio
C:\ProgramData\BAGO\user\     estado mutable local
C:\Users\...\BAGO\            fuente/desarrollo
C:\Users\...\bago-knowledge\  memoria versionable remota
E:\.models\                   modelos LM locales
E:\.bago\                     memoria/indexacion del workspace E:
E:\bago_fw\                   framework limpio en E:
```

`E:\bago_fw` ya cumple el contrato limpio. `E:\.bago` queda como memoria/indexacion separada del workspace E:.

## Comandos de instalacion

Runtime principal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1
```

Runtime principal sin knowledge:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-without-knowledge.ps1
```

Runtime limpio en E: sin tocar PATH global:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1 -TargetRoot "E:\bago_fw" -NoPathUpdate
```

Validacion:

```powershell
& "C:\Program Files\BAGO\bago.cmd" validate
& "E:\bago_fw\bago.cmd" validate
```
