# Auditoría de artifact sprawl y retention creep

## Alcance y estado

Auditoría READ-ONLY del checkout local de `MarcValls/BAGO`. El inventario se congeló el **2026-10-06 12:47 UTC** y las conclusiones se ligan a:

| Campo | Valor |
|---|---|
| Repository | `https://github.com/MarcValls/BAGO` (remote local `origin`) |
| Branch | `publish/worktree-groups-20261003-7f5d47a6` |
| HEAD | `3978de3404584f93697208063aef621a83522ba2` |
| Versión declarada | `4.11.10` (`release_version.txt`) |
| Checkout | Modificado; NO es snapshot limpio |
| Tracked | 1.993 archivos; 6 archivos modificados; diff observado: +414/-69 |
| Untracked no ignorados | 135 archivos |
| Ignorados enumerados | 61.411 archivos; 195 errores de acceso/recorrido |
| Huellas del freeze | porcelain SHA-256 `ca7d5a29b911abf883869bcc753162e021586dd0a02876997398242bc0c31df4`; diff SHA-256 `6a5889fc3befd850f2bdfcd3856cc27602d3cca8eec05dfcbdb8d383ac8edf2a`; inventario-stat SHA-256 `212f51f06147531a703eed88401a1ba2c84ba64cec97c20c97356550461157c5` |

Los 6 cambios tracked en el freeze son `backend/.bago/api/chat_turns.py`, `backend/.bago/api/handlers_chat.py`, `backend/.bago/core/execution_adapters/network.py`, `backend/.bago/core/execution_gateway.py`, `backend/.bago/core/filesystem_effects.py` y `backend/.bago/core/session_turn_mixin.py`. Los archivos nuevos de observabilidad y los demás untracked forman parte del estado encontrado; no se atribuyen a HEAD. Los entregables de esta auditoría se crearon después del freeze y están excluidos de sus conteos.

El conteo de ignorados no equivale a espacio físico recuperable: hay junctions, posibles hardlinks y rutas con ACL que no se pudieron recorrer. La suma de tamaños lógicos observada fue 52.901.148 B tracked + 12.471.363 B untracked + 12.108.031.176 B ignorados. Es una estimación de superficie, no de bytes de disco liberables. El traversal incompleto impide afirmar ausencia global de consumidores y excluye `SAFE_PRUNE`.

## Resumen de clasificación

Unidad de clasificación: **familia/paquete generado o archivo untracked con indicios de retención**, agrupando árboles que son una sola unidad operacional. No se asigna falsamente una clasificación individual a los 63.539 ficheros mezclados de producto, dependencias y datos locales. El JSON adjunto contiene los registros auditados; los agregados de directorios incluyen los tamaños/counts medidos. Estados conservadores:

| Clasificación | Registros |
|---|---:|
| KEEP_REQUIRED | 0 |
| KEEP_CANONICAL | 0 |
| KEEP_EVIDENCE | 2 |
| KEEP_HISTORICAL | 1 |
| KEEP_REGENERABLE_BUT_USEFUL | 3 |
| REVIEW | 14 |
| CANDIDATE_PRUNE | 2 |
| SAFE_PRUNE | 0 |
| DUPLICATE | 0 |
| SUPERSEDED_ARTIFACT | 0 |
| GENERATED_SPRAWL | 1 |
| TEMPORARY_OR_CACHE | 2 |

Las categorías ausentes no significan que no haya tales archivos en todo el repositorio: significan que este pase no reunió evidencia suficiente para asignarlas a un artefacto concreto.

## Candidatos prioritarios

Scores orientativos, no autorización de borrado. `CANDIDATE_PRUNE` es presunción revisable, no decisión.

| Prioridad | Familia | Tamaño lógico | Score | Clasificación/confianza | Evidencia y límite |
|---:|---|---:|---:|---|---|
| 1 | `.run/offline-fix-*` y `.run/offline-refresh` | ~2.17 GB en seis EXE/sidecars | 82 | CANDIDATE_PRUNE / MEDIUM | Seis builds del instalador 4.8.2 con nombres secuenciales y hashes distintos. No se encontró consumidor actual por nombre. Falta demostrar irrelevancia para recuperación/historia y recorrer ACL completa. No son duplicados exactos. |
| 2 | `.run/nsis-final-e2e` | 819.226.661 B | 78 | REVIEW / MEDIUM | Árbol grande de ejecución E2E ignorado. Parece output reproducible; faltan manifiesto, vínculo de claim y consumidores externos. |
| 3 | `.run/install-e2e-backups` | 819.742.561 B | 78 | REVIEW / MEDIUM | Backups de pruebas de instalación; nombre sugiere recuperación, pero no se halló política con TTL/owner en evidencia consultada. |
| 4 | `.run/BAGO-audit-bundle-20260822-173024.zip` | 708.830.834 B | 72 | REVIEW / LOW | Bundle de auditoría potencialmente único. Falta inspeccionar íntegramente su manifiesto/claim y comparar su contenido con otras fuentes. |
| 5 | `releases/compiled` | 399.208.012 B | 38 | KEEP_REGENERABLE_BUT_USEFUL / HIGH | Ignorado y documentado como payload generado por workflows de release; regenerable desde código, pero útil como staging de build/publicación. No se justificó cada versión individual. |
| 6 | `.run/global-closure-20260813-223105` | 394.793.207 B | 74 | REVIEW / MEDIUM | Árbol de evidencia/ejecución de cierre potencialmente único. La relación con claims y política de retención no está demostrada. |
| 7 | `.run/installer-payload-smoke` | 376.902.329 B | 76 | REVIEW / MEDIUM | Output de smoke grande, probablemente reproducible, pero podría sustentar evidencia de instalador. Relación exacta sin resolver. |
| 8 | `.run/offline-fix-v2..v4/final-*` | incluido arriba | 82 | CANDIDATE_PRUNE / MEDIUM | Los SHA-256 observados para refresh/v2/v3/v4 difieren; esto es una secuencia de artefactos distintos, no duplicado exacto. |
| 9 | `backend/node_modules` | 316.560.803 B | 25 | KEEP_REGENERABLE_BUT_USEFUL / HIGH | Dependencias locales reconstruibles desde `backend/package-lock.json` y npm; no fuente ni evidencia independiente. Útil para ejecución local y coste de reinstalación. |
| 10 | `output/BAGO_paquete_conducta_para_codex` y ZIP hermano | 148.258.102 B combinados aprox. | 69 | REVIEW / MEDIUM | Directorio extraído más ZIP del paquete. No se calculó manifiesto comparativo, por lo que no se declara duplicado. |
| 11 | `.vs/` | ~174.5 MB | 70 | TEMPORARY_OR_CACHE / MEDIUM | Ignorado explícitamente como estado de IDE; archivos locales de Visual Studio. No es artefacto runtime demostrado; conservar podría retener preferencias/sesión del desarrollador. |
| 12 | `electron-viewer/dist` / junction `node_modules/bago-ui-viewer` | ~374 MB logical, no sumar dos veces | 35 | KEEP_REGENERABLE_BUT_USEFUL / HIGH | Output generado y junction al mismo target, no dos copias físicas demostradas. `.gitignore` excluye dist; comprobar consumidores del empaquetado antes de limpiar. |
| 13 | `.run/electron-tour-profile-*` | incluido en ignorados | 66 | REVIEW / LOW | Múltiples perfiles de ejecución/screenshots/db posiblemente repetidos. Falta inventario completo por ACL y vínculo con evidencias de aceptación. |
| 14 | `backend/.gabo` | ~109 MB | 20 | REVIEW / LOW | Estado/contexto local protegido; consumidores y contenido bajo ACL no quedaron auditados. No tratar como basura. |
| 15 | `.bago/runtime` | ~42.8 MB | 18 | REVIEW / MEDIUM | Estado generado/canon local ignorado con mapas y runtime state. Hace falta distinguir proyecciones regenerables de evidencia/estado activo. |
| 16 | `backend/inventory_report.json` | 1.677.914 B | 68 | GENERATED_SPRAWL / MEDIUM | Untracked; parece output del inventario de sinks. Hay script productor (`backend/.bago/tools/effect_sink_inventory.py`), pero no se confirmó comando exacto ni todos los consumidores/claims. No recomendar retirar hasta cerrar la auditoría asociada. |
| 17 | `codex-session-01a10722-3263-7cd3-b0fd-884724d671ef.md` | 5.872.025 B | 58 | REVIEW / LOW | Transcript local grande; no se encontró consumidor operativo. Puede tener valor histórico/contextual no especificado. |
| 18 | `.goals/backend-audit-remediation-b10178bf/*` | ~4.55 MB | 25 | KEEP_EVIDENCE / MEDIUM | Logs y JSONL baseline/candidate de goal/auditoría. Vínculo de claim es plausible por ubicación, pero la vigencia del candidate debe verificarse antes de retener como evidencia actual. |
| 19 | `nul` | 0 B | 80 | CANDIDATE_PRUNE / LOW | Archivo untracked de cero bytes y nombre anómalo; búsqueda por referencias limitada por semántica del nombre reservado en Windows. Requiere verificación negativa por ruta y por consumidor antes de eventual decisión. |
| 20 | `releases/archive/**` | 2.434.044.109 B | 0 | KEEP_HISTORICAL / HIGH | `releases/archive/README.md` establece que son payloads locales históricos retenidos por versión e indica que presencia no certifica publicación. La política es explícita; respetarla. |
| 21 | `artifacts/msix-ui-close-20260930/**` | ~98 MB ignorados + recibos visibles | 0 | KEEP_EVIDENCE / MEDIUM | Artefactos asociados a una línea de cierre/estabilidad aún abierta; no asumir obsolescencia por fecha. Falta verificar identidad de candidate y claim vigentes. |

En los instaladores 4.8.2 se calcularon hashes SHA-256 y los valores observados fueron diferentes en los seis builds; no hay duplicación byte-identical demostrada. Hashes completos: refresh `9a733114bce84ddde167ee0be2b105a289adeb154b80256940a216971317997b`; v2 `59e9ad152f01668f9b099635b76c28dc0f9863c27d4d6140810ffb2a5673984f`; v3 `cdcbd2291fa02831e2f2ea8167efd28b30b894485c51774903d65715f2bf3059`; v4 `b012dd55306db74d28133693de5dfefb8389a074e719a66ae5606a29cf6946a9`; final-31279126239 `57dbb51fc34dc573a3122cfa649678da07cdd5eb1ac7e90ac3302db3cd033068`; final-31285286126 `3540ca3a1e57e1bf0ac028d1010dd1c83ecfaadb5f7e0d3028ce0bc893cfd84d`. No comparar solo sidecars sin revalidar los binarios.

## Familias de retention creep

1. **Instaladores offline 4.8.2**: seis directorios versionados por iteración bajo `.run/`, cada uno con EXE/sidecar. Consumidor de producción actual no localizado; productor exacto debe reconstruirse desde logs/scripts históricos. Alta prioridad de revisión, no borrado.
2. **Snapshots E2E y backups de instalación**: `.run/nsis-final-e2e`, `install-e2e-backups`, `installer-payload-smoke`, `global-closure-*`. Cada árbol puede ser output regenerable o prueba única; no hay retención/TTL/claim indexado visible en esta pasada.
3. **Paquetes/renders de auditoría**: ZIPs con timestamp/commit en `output/` y `.run/`. No se compararon exhaustivamente manifiestos ni evidencia source-of-truth. Sin vínculo explícito al claim, `REVIEW`.
4. **Proyecciones de build**: `releases/compiled`, `electron-viewer/dist`, `backend/dist`, `backend/node_modules`. Hay fuente/generación desde código/dependencias; conservar localmente aporta ejecución/staging, pero no constituye canon ni evidencia.
5. **Perfiles de navegador/Electron**: secuencias `electron-tour-profile-*` en `.run/`; probable persistencia de perfiles de prueba. Necesitan política de TTL y export selectivo de evidencia antes de limpieza.
6. **Contexto del desarrollador**: `.vs`, `.gabo`, `.bago/runtime`, transcript. Mezcla cache y estado local; clasificación no se debe uniformar por extensión ni ubicación.

## Estimación

- Superficie ignorada lógica medida: **12.108.031.176 B** (~11,27 GiB decimal/binario aproximado), con recorrido incompleto.
- Familia offline 4.8.2: **~2,17 GB lógicos**; suma como candidato de revisión, no espacio recuperable confirmado.
- Mayor concentración pendiente: E2E/backups/audit bundles, >2,7 GB lógicos en las familias citadas.
- Registros explícitos en JSON: **25**; el registro consolidado clasifica familias, no los 63.539 archivos del checkout uno por uno.
- Porcentaje del repositorio en bytes: **UNKNOWN**, ya que el universo medido combina checkout lógico, junctions, ACL denegadas, hardlinks potenciales y dependencias locales; tampoco existe tamaño físico autoritativo de `.git` incluido en la suma. Proporción simple de las familias ignoradas respecto a ignorados medidos tampoco expresa espacio recuperable.

## Plan de limpieza gobernada (NO ejecutado)

| Lote | Alcance | Precondiciones y pruebas antes/después |
|---|---|---|
| PRUNE-01 | Caches temporales demostrados (`.vs`, perfiles de navegador caducados) | Antes: cerrar procesos IDE/browser; inventariar usuario/claims; probar rebuild limpio y smoke UI. Después: rebuild/reopen IDE y repetir smoke; confirmar sin pérdida de perfil o evidencia. |
| PRUNE-02 | Duplicados exactos de ZIP/árbol de paquete y copias de release | Antes: generar manifiestos SHA-256 recursivos; confirmar un ejemplar preservado y consumidores apuntan a él; validar sidecars. Después: comparar extracción/build y verificar publicación/instalación si aplica. |
| PRUNE-03 | Iteraciones offline 4.8.2 superseded | Antes: confirmar que no hay rollback/recovery pendiente, claim de distribución ni uso histórico obligatorio; guardar un artefacto canónico y registrar hashes en decision record. Después: smoke de instalador conservado y hash verificado. |
| PRUNE-04 | Outputs E2E/smoke y perfiles `.run` | Antes: asociar cada carpeta a run/claim; exportar receipts únicos; determinar TTL y reejecución reproducible. Después: repetir escenario en workspace temporal y contrastar resultado/receipt. |
| PRUNE-05 | ZIPs de auditoría y backups | Antes: inspeccionar manifests completos, consumidores, uniqueness, introducción Git/goal claim, recovery y retención contractual; decisión humana explícita. Después: comprobar claims/links y recuperación del backup retenido. |
| PRUNE-06 | Proyecciones de build/release | Antes: build desde fuentes con lockfiles/toolchain exactos; confirmar workflow y staging no los consume. Después: verificar artefactos por SHA, empaquetado, smoke y gates de release sobre candidate correcto. |

No se recomienda un lote `SAFE_PRUNE`: traversal incompleto, rutas protegidas y mecanismos dinámicos dejan sin demostrar la ausencia global de consumidores.

## Límites y enlaces

La navegación web directa a GitHub fue rechazada por el conector (`restricted URL`), así que no puedo afirmar que este SHA esté publicado ni que enlaces remotos a archivos no tracked sean resolubles. El enlace de commit queda como referencia de snapshot, sujeto a existencia remota: [snapshot `3978de3`](https://github.com/MarcValls/BAGO/tree/3978de3404584f93697208063aef621a83522ba2). El README histórico es navegable localmente como [releases/archive/README.md](../../releases/archive/README.md); el productor del inventario está en [effect_sink_inventory.py](../../backend/.bago/tools/effect_sink_inventory.py). Para familias ignoradas, la ruta no puede ser link de blob del SHA porque no pertenece al árbol Git; los enlaces al código/productor se deben resolver contra este checkout antes de limpiar.

**Conclusión:** el coste más prometedor de retención está en iteraciones de instaladores y árboles E2E/smoke bajo `.run`, seguido por outputs locales de build y perfiles de navegador. Solo `releases/archive` tiene una política explícita de retención encontrada en esta pasada. Prescindibilidad alta no equivale a autorización de borrar; se requiere cerrar los vínculos con claims/recovery y completar los 195 fallos de recorrido.

## Ejecución solicitada de los lotes

Revalidé antes de limpiar: HEAD sigue siendo `3978de3404584f93697208063aef621a83522ba2`; el estado tracked/untracked sigue incluyendo los mismos archivos del freeze y los dos entregables de auditoría. En la auditoría inicial no se ejecutaron borrados. Tras la instrucción de retención del usuario, se completó una familia concreta:

- `.run/offline-refresh`, `.run/offline-fix-v2`, `v3`, `v4`, `offline-fix-final-31279126239` y el directorio vacío `offline-fix-v5`: retiradas las cinco iteraciones anteriores y el directorio vacío; se conserva únicamente `offline-fix-final-31285286126/bago-4.8.2-setup.exe` más su sidecar SHA-256. El artefacto restante mide 362.232.913 B y su SHA-256 verificado tras la operación es `3540ca3a1e57e1bf0ac028d1010dd1c83ecfaadb5f7e0d3028ce0bc893cfd84d`.
- Se eliminaron 5 EXE (1.811.209.296 B) y 5 sidecars (330 B): **1.811.209.626 B lógicos retirados**. El espacio físico liberado no se midió.
- El respaldo remoto de `v4.8.2` está visible en [GitHub Releases](https://github.com/MarcValls/BAGO/releases/tag/v4.8.2). La release `v4.9.2` declara que reemplaza `v4.9.1`; `v4.9.3` y `v4.10.0` también tienen páginas de release públicas. Las páginas verifican publicación de releases, no igualdad hash de cada archivo local con cada asset remoto.

Los demás lotes se mantienen bloqueados hasta cerrar el alcance de “solo online” para los payloads locales de `releases/archive` frente a conservar una copia local por versión y verificar qué outputs repetidos son el mismo tipo de artefacto. Además:

- `PRUNE-01`: **BLOCKED**. El proceso `Code` tiene instancias abiertas y no se pudo enumerar de forma verificable el contenido de `.vs`; no se pudo excluir estado activo de IDE/perfil.
- `PRUNE-02`: **PARTIAL**. Limpieza de las cinco iteraciones locales 4.8.2 anteriores; las copias de release 4.9.x/4.10.0 y de output aún no se comparan/limpian.
- `PRUNE-03`: **PARTIAL**. Se preservó el build local más nuevo de 4.8.2; otras familias antiguas necesitan alcance de retención y cotejo de assets.
- `PRUNE-04` y `PRUNE-05`: **BLOCKED**. No se pudo asignar owner/claim y política de retención a cada output E2E, ZIP o backup; siguen existiendo errores de traversal.
- `PRUNE-06`: **BLOCKED**. No se ejecutó reconstrucción candidata/toolchain ni se verificó que cada staging output no esté en uso por empaquetado.
- Hallazgo nuevo: `backend/inventory.err` está citado por el consumidor documental/herramienta `docs/architecture/capability-history-20261004/collect.py` y por freezes JSON; queda en `REVIEW`, no candidato a borrar.
- `nul` no tiene referencias confirmadas, pero la búsqueda negativa es incompleta por semántica Windows del nombre reservado; no se borró.

Resultado acumulado: **10 archivos eliminados, 0 movidos, 0 renombrados**; se conservó el build local más nuevo de 4.8.2. No se realizaron pruebas funcionales porque solo se retiraron builds offline históricos tras verificar la release online y conservar el build local más reciente. La comprobación posterior confirmó que el hash del artefacto conservado no cambió.
