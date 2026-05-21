# BAGO — Contratos finales

> Estado: `3.4.0b1` · Fuente viva auditada: `.bago/tools/tool_registry.py` · Fecha: Mayo 2026

Este documento fija los contratos operativos que deben mantenerse alineados antes
de promover BAGO a release estable. Si un documento, test o launcher contradice
estos contratos, gana este orden de verdad:

1. Código ejecutable y registry vivo.
2. `.bago/pack.json` para identidad del pack.
3. `.bago/state/global_state.json` para estado runtime.
4. Documentación generada desde código.
5. Documentación histórica marcada como archivo.

## 1. Contrato de arranque y bootstrap

El dispositivo BAGO arranca desde los launchers de `/Volumes/BAGO` y aterriza en
`/Volumes/bago_core`. El entrypoint técnico recomendado dentro del repo es:

```bash
python3 bago <comando>
```

El bootstrap debe resolver rutas reales, no rutas recordadas. El estado de
arranque puede registrar snapshots, pero no debe usarse como fuente canónica de
estructura si contradice el repo actual.

Estado: implementado. Los snapshots históricos en `.bago/state/agents/` y `.bago/state/skills/` son evidencia inmutable. Se conservan como registro de ejecución. No requieren migración.

## 2. Contrato de estado y memoria

`.bago/state/global_state.json` es el estado canónico de sesión. `.bago/state/bago.db`
es runtime local. La memoria derivada puede cachearse, pero no reemplaza la fuente.

Regla: ningún test debe dejar ruido persistente en state salvo que el objetivo del
test sea validar migraciones de estado.

Estado: funcional. Los snapshots históricos en `.bago/state/` son evidencia inmutable. Se conservan como registro de ejecución. No requieren migración. Deuda abierta: `bago neural --test` aún toca estado runtime.

## 3. Contrato CLI y registry

`.bago/tools/tool_registry.py` y `_registry_entries.py` son la fuente única de
comandos. Conteo actual:

| Bucket | Conteo |
|---|---:|
| Core | 38 |
| Experimental | 80 |
| Dangerous | 8 |
| Legacy | 28 |
| Internal | 5 |
| Total registry | 159 |

La superficie pública activa es `core + experimental + dangerous`: 126 comandos.
README, `docs/COMMANDS.md`, `docs/API_CONTRACT.md`, `INSTALL.md` y `QUICKSTART.md`
deben coincidir con estos conteos.

Estado: corregido y cubierto por `tests/test_registry_contract.py`.

## 4. Contrato de seguridad y comandos dangerous

Todo comando con `risk = "dangerous"` requiere confirmación explícita antes de
ejecutarse:

```bash
python3 bago <dangerous> --yes
python3 bago <dangerous> --unsafe
```

`--dry-run` solo puede saltar el guard si el comando declara soporte explícito.
`--confirm` y flags propios no son contrato global del dispatcher.

Estado: implementado en `bago`. Deuda abierta: `bago spiral --test` queda bloqueado
por el guard aunque el self-test directo de `spiral_loop.py` pasa.

## 5. Contrato de workflows W0-W10

Los workflows activos son W0-W10 y su grafo vive en `.bago/workflows/`. `bago flow`
es la interfaz de lifecycle; `bago task` y `bago session` completan el loop.

Estado: implementado. La documentación debe decir 11 workflows operativos.

## 6. Contrato de roles y agentes

Los roles definen responsabilidades; los agentes ejecutan o asesoran. BAGO no es
un modelo ni un proveedor: BAGO enruta, coordina y registra.

La terminología oficial separa:

- `agent_router.py` / `bago route`: decisión proveedor-modelo.
- `orchestrator.py`: workflows multi-tool y memoria de routing.
- `neural_router.py`: routing sobre Neural Bus.

Estado: nomenclatura actualizada en docs operativas. Referencias históricas quedan
solo en auditorías y snapshots.

## 7. Contrato Shepard, spiral y memoria-esfera

`spiral_loop.py` implementa el bucle Shepard cromático de 12 pasos. `spiral_agent.py`
es la capa fractal de agente. `orchestrator.py` registra memoria de routing a tres
voces/esfera con schema `bago.spiral-routing.v2`.

Estado: self-tests directos pasan. Deuda abierta: integrar un modo test seguro en
el dispatcher para `bago spiral --test`.

## 8. Contrato Neural Local

`bago_neural.py` expone el Neural Bus local. `neural_toolbox.py` activa herramientas
por contexto. `neural_router.py` enruta eventos y puede degradar si no hay nodo LLM.

Estado: self-tests de bus y toolbox pasan. Mojibake de superficie corregido. Deuda
abierta: aislar tests de estado persistente.

## 9. Contrato pack/cache/DB

`.bago/pack.json` es el manifiesto canónico, versionable y auditable. SQLite es
cache de lectura para acelerar consultas:

```bash
python3 bago pack-cache sync
python3 bago pack-cache check
python3 bago pack-cache status
```

Estado: implementado y registrado como core.

## 10. Contrato docs, release y versionado

La versión debe estar alineada entre `pyproject.toml`, `.bago/pack.json` y
`.bago/state/global_state.json`. Los docs públicos no deben mantener conteos manuales
si existe generador.

Antes de release estable deben pasar:

```bash
python3 .bago/tools/generate_commands_doc.py --check
python3 .bago/tools/generate_layers_doc.py --check
python3 .bago/tools/readme_sync.py --dry-run
python3 -m pytest tests/test_registry_contract.py -q
```

Estado: corregido para `3.4.0b1`. Siguiente hito recomendado: `3.4.0b2`, no estable,
hasta cerrar deuda de tests legacy y state side effects.

## 11. Contrato de nomenclatura y rutas

Reglas:

- Comandos CLI: kebab-case (`pack-cache`, `recent-projects`).
- Módulos Python: snake_case (`pack_cache_db.py`, `agent_router.py`).
- Docs generadas: no se editan manualmente.
- Docs históricas: deben declararse históricas o archivarse, no mezclarse con contrato actual.
- State runtime: no se corrige a mano salvo migración explícita.

Estado: rutas operativas corregidas. La documentación histórica de `.bago/CLI_v3_*`,
tablet, demos y factories queda reunida en `.bago/archive/`. Exenciones actuales:
`.bago/audits/*` y algunos snapshots en `.bago/state/*` conservan nombres legacy
como evidencia histórica.

## 12. Contrato de testing y gates

El pre-push debe bloquear drift entre registry, README, docs generadas, seguridad,
validación de pack y tests críticos. Los tests legacy que importan módulos eliminados
no pueden formar parte del gate estable hasta migrarse o archivarse.

Estado: gate principal recuperado para registry/docs. Deuda abierta: migrar o retirar
tests legacy (`test_bago_framework.py`, `test_bago_brutal.py`, `test_bago_integracion.py`).

## 13. Contrato de instalación limpia, runtime y knowledge

La frontera entre runtime y residuos de desarrollo se define por
`docs/runtime_contract.json`. Ese archivo es la fuente de verdad que consume
`install.ps1` para decidir qué se conserva en una instalación limpia y qué se
pruna o se redirige fuera de `C:\Program Files\BAGO`.

Reglas:

- `C:\Program Files\BAGO` contiene bootstrap, runtime y evidencia generada del
  instalador, no el árbol de desarrollo completo.
- `C:\ProgramData\BAGO\user` contiene el estado mutable del usuario.
- `C:\Program Files\BAGO\.bago\knowledge` contiene la memoria sincronizable y
  compatible con `MarcValls/bago-knowledge`.
- El instalador se publica en dos perfiles: `install-with-knowledge.ps1` y
  `install-without-knowledge.ps1`.
- El contrato de publicación canónico vive en `docs/PUBLISH_CONTRACT.md`.
- Comandos canónicos de instalación:

  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install-without-knowledge.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NoKnowledge
  ```
- `docs/runtime_contract.json` manda sobre la lista de keep/prune del instalador.
- `C:\Program Files\BAGO\runtime_contract.json` es el manifiesto generado de la
  instalación aplicada; documenta qué se conservó y qué se eliminó.
- El layout canónico de conocimiento es `README.md`, `manifest.json`,
  `topics/`, `examples/`, `schemas/` y `assets/`.
- Si el contrato fuente no se puede leer, el instalador usa un fallback embebido,
  pero la intención contractual sigue siendo la misma.

Estado: implementado en el instalador limpio. La documentación de alto nivel y el
manifiesto generado quedan separados por diseño.

## 14. Contrato de motor limpio durante desarrollo

El motor instalado debe permanecer limpio y regenerable mientras el desarrollo
ocurre fuera de `C:\Program Files\BAGO`.

Reglas:

- `C:\Program Files\BAGO` es un artefacto reconstruible, no un workspace.
- El workspace de desarrollo vive en el repo fuente.
- `bago dev refresh-engine` reinstala el motor desde `install.ps1`.
- El perfil publicado se conserva salvo override explícito:
  `--with-knowledge` o `--without-knowledge`.
- Tras refrescar, el motor debe validarse antes de darlo por bueno.

Estado: contrato nuevo, alineado con `docs/ENGINE_CONTRACT.md`.

## Fallos auditados

Corregidos en este corte:

- README desfasado: 158/125 y 9/146/1/0 frente al registry real.
- `docs/COMMANDS.md` desfasado: 20/89 frente a 38/80.
- `docs/API_CONTRACT.md`, `docs/ARCHITECTURE.md`, `INSTALL.md` y `QUICKSTART.md` con conteos obsoletos.
- Contrato dangerous documentado con `--confirm`/`--execute` en vez de `--yes`/`--unsafe`.
- Mojibake en `_registry_entries.py`, `neural_router.py`, `agent_router.py`, `ideas_catalog.json` y `llm_config.json`.
- Referencias operativas a wrappers legacy en docs/catálogos no históricos.
- `readme_sync.py` no reconocía el formato actual del banner público.

Pendientes antes de estable:

- Permitir self-tests seguros para comandos dangerous sin abrir ejecución real.
- Aislar `bago neural --test` de state persistente.
- Migrar o archivar tests legacy que apuntan a módulos retirados.
- Decidir si los snapshots de `.bago/state/` se migran o quedan como evidencia inmutable. **Resuelto (v3.4.0): los snapshots son evidencia inmutable — se conservan, no se migran.**
