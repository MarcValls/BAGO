# Limpieza ejecutada · 7 de octubre de 2026

## Candidato

- Checkout: `C:\Users\AMTEC_Terminal_1º\BAGO`
- HEAD observado: `3978de3404584f93697208063aef621a83522ba2`
- Rama: `publish/worktree-groups-20261003-7f5d47a6`
- Estado previo: seis archivos tracked modificados; no se editaron durante esta limpieza.

## Eliminaciones ejecutadas

| Ruta | Bytes nominales | Archivos | Evidencia de regeneración / descarte |
|---|---:|---:|---|
| `.worktrees/pr230-repair/node_modules` | 540.711.568 | 12.218 | Worktree limpio; `package-lock.json` y `backend/package-lock.json` presentes; cero archivos tracked y ningún proceso apuntaba a la ruta. |
| `.worktrees/wss-publication-20260930/node_modules` | 540.764.062 | 12.218 | Worktree limpio; ambos lockfiles presentes; cero archivos tracked y ningún proceso apuntaba a la ruta. |
| `.worktrees/dependency-audit-20260930/node_modules` | 540.764.062 | 12.218 | Worktree limpio; ambos lockfiles presentes; cero archivos tracked y ningún proceso apuntaba a la ruta. |
| `releases/compiled/runtime` | 399.208.012 | 4.778 | Staging sin archivos tracked. `releases/build-installer.ps1` lo borra y reconstruye antes de empaquetar. Sin proceso de empaquetado activo. |
| `electron-viewer/dist` | 374.012.905 | 77 | Output sin archivos tracked; `electron-builder --dir` lo produce y el builder de release ejecuta `npm run dist --workspace electron-viewer`. Sin proceso Electron/build activo. |
| `releases/ci-artifact/bago-4.9.2-setup.exe` | 151.064.248 | 1 | No tracked ni consumidor localizado (salvo exclusión del inventario); SHA-256 `1E584A97B33E871DA134247E0364B4CE86EAA49D9AAF0000666AE31453B33C63`, distinto del instalador archivado y del release público canónico. Se conservaron sidecar y release archivado. [Release público 4.9.2](https://github.com/MarcValls/BAGO/releases/tag/v4.9.2). |
| `output/pytest-*` (23 directorios) | 13.486.633 | 6.504 | Temporales de pytest, sin archivos tracked ni proceso pytest activo. Logs, informes, recibos y demás `output/` se conservaron. |
| `output/BAGO_paquete_conducta_para_codex/integrations/ia_memoria/.venv` | 83.652.435 | 4.823 | Se retiró la copia expandida, no la archivada: el ZIP interno válido contiene exactamente esos 4.823 archivos (83.652.435 B sin comprimir; 31.835.642 B comprimidos). No figura en `MANIFEST.json`/`SHA256SUMS`, ni en el ZIP externo; el README remite al entorno externo. |
| `.git/objects/pack` (55 `.idx` huérfanos + `tmp_pack_nUr0LA`) | 84.058.255 | 56 | `git count-objects` los clasificaba como garbage; los `.idx` carecían de `.pack` homónimo. El temporal, de 2026-08-07, tenía checksum SHA-1 inválido. Se borraron esos archivos mediante la vía autorizada del entorno; sin tocar packs válidos, refs ni commits. |
| `node_modules` del checkout | 164.626.934 | 12.140 | Sin archivos tracked, con `package-lock.json`, sin proceso consumidor ni junctions entrantes. El servidor activo utiliza Python y `backend/ui-react/dist`; se conservaron ambos `dist`. |

**Total nominal retirado:** 2.892.349.114 bytes (2,69 GiB). No equivale a un delta neto de espacio libre: no hay dos lecturas comparables que permitan atribuir cambios concurrentes del disco a estas eliminaciones.

## Verificación posterior

- Las tres carpetas `node_modules` de worktrees y el `node_modules` del checkout ya no existen; los tres worktrees permanecen registrados y limpios.
- `releases/compiled/runtime`, `electron-viewer/dist` y el EXE CI ya no existen; `releases/compiled`, el sidecar del EXE y el instalador archivado permanecen.
- Los dos ZIP de comportamiento pasan `ZipFile.testzip()` y se conservan. El ZIP interno conserva el `.venv` con todos sus archivos; el ZIP externo y los manifiestos no lo incluyen.
- `git count-objects -vH` informa `garbage: 0` y `size-garbage: 0 bytes`; siguen tres packs válidos (2,16 GiB). HEAD y las seis modificaciones tracked previas siguen iguales.
- No se ejecutaron tests ni builds; fue una limpieza de artefactos.

## Inventario y retención

Medición lógica que omite junctions/reparse points: `.run` 1.055.109.899 B; `artifacts` ≈250,24 MB (incluye este registro); `.worktrees` 228.743.463 B; `releases` 2.434.150.298 B; `output` 566.440.763 B; `.git` ≈2,344 GB, con 2.321.087.833 B en sus tres packs válidos. La cifra heredada de 6,06 GiB en `.run` no coincide con esta medición.

Se conservaron `.run/validated-worktree`, los artefactos de auditoría y snapshots con valor probatorio, `artifacts/msix-ui-close-20260930`, los paquetes versionados de `releases/archive` y el sidecar histórico del instalador CI eliminado. `.run/BAGO-audit-bundle-20260822-173024.zip` permanece: contiene un snapshot de auditoría con diff/estado/historial, aunque no se puede abrir como ZIP estándar.

## Candidatos revisados y conservados

- `.run/backend-database-package`: declara el commit `7d36cd965e8490db4c6193b6da5a6553e1084b12` y hashes de bases SQLite. La comparación encontró 865 de 888 blobs exactos, 13 distintos, 10 ausentes y 960 archivos locales adicionales (58.734.912 B). No es una copia reconstruible sin perder estado/evidencia.
- `artifacts/bago-4.11.3-signpath-candidate-unsigned-v3.zip`: 151.054.955 B, SHA-256 `7F3AB039944975380B3C589792FF0E404B3B144075DA837BCD3D22439C5CE0E7`. Preparación de firma con `source_worktree_dirty: true`; no hay cierre de firma documentado.
- `artifacts/msix-ui-close-20260930`: paquete de prueba firmado y recibo ligados al candidato `b10178bf…`; alcance diagnóstico y P0 aún abierto.
- `output/BAGO_paquete_conducta_para_codex`: antes de retirar la expansión, el ZIP interno coincidió byte por byte con 6.416 archivos; el ZIP externo coincidió con 1.790. El `.venv` eliminado sigue recuperable del ZIP interno válido, con los hashes/manifest de las fuentes conservados.


## Recompactación segura de objetos Git — 2026-10-07

- Diagnóstico: los packs originales `pack-53e573…` (317.766.454 B con `.idx`/`.rev`) y `pack-c6bf73…` contenían 5.168 OID comunes; el tercero, `pack-633fe0…` (1.202.960.112 B con índices), no añadía duplicación con esos objetos. MIDX y los tres packs originales verificaban correctamente.
- Ejecución: `git multi-pack-index repack --batch-size=0 --progress` creó `pack-73e7cb…` (1.456.212.135 B con índices); `git multi-pack-index expire` retiró sólo `pack-53e573…` y `pack-633fe0…`. Se conservó `pack-c6bf73…`, que contiene 3.040 objetos ausentes del pack consolidado y está acompañado por metadatos `.mtimes` de cruft.
- Resultado: tamaño nominal de `.git/objects/pack` de 2.321.087.833 B a 2.256.573.350 B: **64.514.483 B (61,5 MiB) menos**. La disponibilidad global de C: pasó de 25.100.992.512 B a 25.159.966.720 B (+58.974.208 B entre muestras); ese delta no se atribuye íntegramente a Git por posible actividad concurrente.
- Verificación posterior: HEAD `3978de3404584f93697208063aef621a83522ba2`; 334 refs y SHA-256 del inventario de refs sin cambios (`c10f325adfdafb101159bb152ddbcccab45fe0c1ab073f0172fc969adba21757`); `git multi-pack-index verify` rc=0; `git fsck --full --no-reflogs --unreachable` rc=0, sin `missing`/`error`/`fatal`; 9.211 objetos siguen declarados unreachable/dangling, conservados; `git count-objects -vH`: 2 packs, `garbage: 0`, `size-garbage: 0`.
- Límite: `git status` cambió durante la operación: aparecieron cambios adicionales en el checkout mientras los comandos de packs corrían. No se editaron archivos del árbol de trabajo desde esta limpieza; HEAD/ref se mantuvieron iguales. No se ejecutaron tests ni builds.

## Eliminación de salida temporal pytest - 2026-10-07

- Candidato: `.run/publication-20261003`, ignorado por Git y sin rutas rastreadas ni referencias nominales localizadas en `.bago`, `.goals`, `artifacts`, `docs`, `scripts`, `releases` o `backend`.
- Evidencia: 12 subdirectorios de ejecución y fixtures pytest (`tmp_path`); 10.301 archivos regulares con 27.097.277 B, 4.301 symlinks de fixtures hacia directorios temporales hermanos o `backend/.bago`. La eliminación usó `shutil.rmtree` (desvincula symlinks; no sigue sus destinos). Se detuvo inicialmente por blobs read-only dentro de repositorios Git de fixture; se retiró ese atributo sólo dentro del árbol exacto y se completó.
- Verificación: `Test-Path` confirmó que la ruta ya no existe; `git ls-files`/`git status` no reportaban contenido rastreado. C: pasó de 25.500.602.368 B libres en la lectura previa al intento a 25.547.063.296 B tras completar: +46.460.928 B entre lecturas (variación concurrente posible, no se atribuye íntegra a este árbol). No se ejecutaron tests ni builds.

## Eliminación de basetemp de pruebas recientes - 2026-10-07

- `.run/agentic-lab-offline-tests-20261007` (21 archivos, 107.879 B) y `.run/context-handoff-tests-20261007` (31 archivos, 33.163 B) eran directorios `--basetemp` con fixtures regenerables. Ninguno estaba rastreado ni contenía symlinks; `lastfailed` no existía en ninguno. El handoff ya conserva el comando y resultado de la suite de context handoff.
- Eliminación limitada a ambas rutas exactas; se confirmó que no existen. No se ejecutaron tests ni builds durante la limpieza. C: reportó 25.545.334.784 B libres tras borrar; no se atribuye cambio de espacio por encima de los 141.042 B medidos en archivos regulares, pues puede haber variación concurrente.
- El ZIP `.run/BAGO-audit-bundle-20260822-173024.zip` sigue preservado: 708.830.834 B, SHA-256 `73378B7ED189F81943EFBDB5873C7F549AC4F7070947B18C6490B80081362D69`; su directorio ZIP no abre con `zipfile` y necesita recuperación verificable antes de sustituirlo.

## Corrección de tamaño del worktree validado y eliminación de copia duplicada - 2026-10-07

- Corrección de medición: `.run/validated-worktree` no ocupa 345 MiB propios. La estimación anterior siguió una junction NTFS en `backend/node_modules`, cuyo destino es `backend/node_modules` del checkout principal. Con symlinks y junctions omitidos, el árbol ahora mide 36.075.356 B; la junction apunta a dependencias activas del checkout y se dejó intacta. El worktree sigue registrado en Git, limpio, `HEAD=3c8b728c5f2ecbda1c59e997682062b36e44bef7`; no aparece en ramas y no es ancestro del HEAD actual.
- Duplicado demostrado: `.run/validated-worktree/.run/BAGO-third-party-audit-20260822-173517.zip` y `.run/BAGO-third-party-audit-20260822-173517.zip` tenían el mismo SHA-256 `8F92998EDBC7F815450AA246197A0B16EE68BE6AF27006CC9D523B762DA3764D`, 7.471.120 B y los dos abrieron/testearon con ZIP válido (1.547 entradas, CRC sin error). El consumidor `scripts/package_remediation_audit.py` usa la copia raíz `.run/...`; se retiró sólo la copia dentro del worktree. La raíz canónica permanece intacta.
- Verificación posterior: copia raíz presente; copia nested ausente; `HEAD` del worktree sin cambio y `git status --porcelain=v2 --untracked-files=all` vacío. Se liberan nominalmente 7.471.120 B más los metadatos de directorio; C: puede variar por actividad concurrente.
- Inventario corregido con junctions y symlinks excluidos: `.run` = 1.020.806.666 B en 37.597 archivos; 8.965 puntos de reparse se omitieron; `artifacts` = 250.247.661 B en 159 archivos. Esto sustituye las cifras infladas por seguir junctions, no el espacio real ocupado.

## Nota de corrección del inventario de tamaños - 2026-10-07

El `REPORT.md`/`inventory.json` del freeze 2026-10-06 conserva correctamente su alcance temporal y sus limitaciones declaradas, pero sus tamaños de algunos árboles ignorados siguieron junctions NTFS y no representan bytes propios del candidato. No reinterpretar esos totales como espacio recuperable. Medición actual (archivo regular, symlink/junction no seguida):

- `.run`: 1.020.806.666 B / 37.597 archivos; se omitieron 8.965 puntos de reparse.
- `artifacts`: 250.247.661 B / 159 archivos.
- `.run/global-closure-20260813-223105`: 28.729.562 B / 1.062 archivos, frente a los 394.793.207 B lógicos del freeze; la diferencia proviene del traversal de junctions.
- `.run/install-e2e-backups`: 15.992.253 B / 1.312 archivos, frente a los 819.742.561 B lógicos del freeze; el traversal anterior siguió junctions.
- `.run/validated-worktree`: 36.075.356 B / 2.582 archivos propios, omitiendo 293 puntos de reparse. `backend/node_modules` es una junction al `backend/node_modules` activo del checkout, no una copia dentro del worktree.
- Las rutas `.run/nsis-final-e2e` y los archivos `.run/offline-fix-*`/`.run/offline-refresh` no existen en el estado consultado el 2026-10-07; no se reevalúa aquí la validez histórica del freeze ni se atribuye la ausencia a una acción de esta pasada.
- `output/pr204-4e77539e-artifact.zip` y `output/v4.9.3-release-artifact.zip` son ZIP válidos, pero contienen EXE diferentes (SHA-256 `4F7102B1D6F1466E68AFD60E8C8B76213BA45C6CFF19DA464F00548F9629E47A` y `AC57B858C16E22B2D59432A12C11C1B85DA896ECA41EB599FB026BD211F1A72F`); se conservaron.

## Eliminación de ZIP interno con entorno virtual obsoleto - 2026-10-07

- Se retiró únicamente `output/BAGO_paquete_conducta_para_codex/BAGO_paquete_conducta_para_codex.zip` (40.269.741 B; SHA-256 previo `9B9207060A32B16671ABDDF05900DB9094C27D8CC1ED03D0B2DD574FF81754D`). Era una captura anterior de 6.416 entradas que incluía 4.823 archivos del `.venv` de `integrations/ia_memoria` (83.652.435 B sin comprimir; 31.835.642 B comprimidos). La fuente declara `mcp[cli]>=1.28.1,<2`; README indica instalar en una ruta estable y no distribuir dependencias instaladas.
- Retención alternativa verificada: siguen presentes las fuentes expandidas, `MANIFEST.json`, `SHA256SUMS`, y `output/BAGO_paquete_conducta_para_codex.zip` externo (7.598.490 B), con SHA-256 verificado contra sidecar `E12BA18EE5DFA7641559EEFBB57E08051247DC90B09A68F41ECA9AC79CB5DF56`. El ZIP externo pasó previamente `testzip()` (1.790 entradas, CRC correcto) y no declara `.venv`; su README dice que no contiene dependencias instaladas. No se encontraron referencias de código/estado al ZIP interno ni a su ruta.
- Verificación posterior: ZIP interno ausente; paquete externo, fuentes y manifiestos presentes. C: mostró 25.115.410.432 B libres en una lectura posterior; no se compara como delta fiable por actividad concurrente.


## Cierre de clasificación del ZIP de auditoría - 2026-10-07

- Escaneo estructural por cabeceras locales (sin descompresión) leyó 3.281 entradas completas: 696.096.218 B comprimidos / 1.176.564.946 B declarados sin comprimir; se detuvo en `BAGO/releases/bago-4.9.0-setup.exe`, offset 696.395.314, cuyo header declara CRC y tamaño comprimido 0 pero tamaño expandido 150.526.240 B. El resto del ZIP mide 12.435.520 B y no puede recuperarse con la estructura indicada.
- Se hallaron 880 grupos de mismo tamaño, CRC, método y tamaño comprimido que suman 54.246.449 B de aparente repetición. El hash SHA-256 del payload comprimido coincide en esos grupos, pero son rutas distintas del snapshot (backend, app empaquetada, release tree, copias históricas); no hay nombres de entrada repetidos. Quitarlos rompería la estructura de rutas; no se consideran basura.
- La entrada dañada no se sustituye automáticamente por `releases/archive/v4.9.0/bago-4.9.0-setup.exe`: el archivo vigente mide 303.979.891 B, frente a 150.526.240 B declarados en la entrada dañada, y tiene otro SHA-256. No se puede afirmar que sea el mismo build.
- Conclusión: conservar el ZIP completo mientras se evalúe una recuperación que preserve paths y procedencia. No crear un ZIP parcial que simule completar el bundle. El intento de verificación integral por descompresión se interrumpió por rendimiento antes de dar resultado; el original no cambió.

## Candidatos grandes de `output` cotejados - 2026-10-07

- Comparé por tamaño y SHA-256 los ZIPs grandes del inventario contra todos los archivos regulares del checkout sin seguir reparse points; no apareció ninguna segunda copia byte-idéntica de `pr204-4e77539e-artifact.zip` (151.112.539 B), `v4.9.3-release-artifact.zip` (151.109.728 B), `BAGO-backend-database-v4.11.1-7d36cd96.zip` (35.488.401 B) ni el ZIP externo del paquete de conducta (7.598.490 B). Los dos artefactos de 4.9.3 contienen instaladores con SHA distintos y ZIP íntegro; se conservan.
- `output/backup-root-gabo-before-seed-20260909` (26.924.625 B) contiene una captura histórica `.gabo` con índices de contexto/símbolos (~17,8 MB) y `evidence.jsonl` (~9 MB); no se borró por su valor de recuperación/provenance.
- No se eliminaron instaladores, datos de base ni backup histórico en esta pasada. No se ejecutaron tests/builds.


## Eliminación de expansión redundante de snapshot de base de datos - 2026-10-07

- La clasificación inicial del `.run/backend-database-package` como no reconstruible queda supersedida para la expansión: la copia válida `output/BAGO-backend-database-v4.11.1-7d36cd96.zip` contiene exactamente sus 1.850 archivos y 66.888.856 B. Cada ruta, tamaño y SHA-256 del árbol expandido coincidió; `ZipFile.testzip()` dio `None`; el sidecar SHA-256 del ZIP coincide con `3EA8B2EFBF4DFAF60B8D9DDF5915D954500823FC1C1E8D9E8C23BCAA96914203`.
- Se eliminó sólo el árbol expandido `.run/backend-database-package` (no rastreado, sin symlinks/junctions). El ZIP conserva intactos fuente y snapshots SQLite únicos, con su manifiesto de candidato y hashes; ZIP y sidecar quedan presentes.
- Verificación posterior: 1.850 entradas extraídas reprodujeron tamaño y SHA-256 del árbol antes de borrarlo; ruta expandida ausente y archivo empaquetado retenido. Reducción nominal: 66.888.856 B; no se atribuye toda variación de C: a la eliminación por actividad concurrente. No se ejecutaron tests/builds.

## Cachés de Python en el paquete de conducta expandido - 2026-10-07

- Comparación por ruta/tamaño/SHA-256 contra el ZIP externo: 1.790/1.790 archivos coinciden exactamente. La expansión conserva 16 elementos no presentes en el ZIP: 15 `.pyc` en 5 `__pycache__` (199.439 B) y `integrations/ia_memoria/memory_root/50_INDEX/memory.sqlite` (126.976 B). Ese SQLite se mantuvo porque es estado local único, no un cache demostrado.
- Retiradas sólo las 5 carpetas `__pycache__`; se verificó que no hubiera reparse points, que la ruta no tuviera contenido rastreado y que la base `memory.sqlite` y ZIP externo sigan presentes. No se ejecutaron tests/builds.

## NSIS E2E expansion retirada y ZIP retenido - 2026-10-07

- `output/nsis-tools-e2e-20260909/nsis-3.10` era la expansión exacta de `nsis-3.10.zip`: 441 de 441 archivos emparejados por ruta, tamaño y SHA-256; el ZIP pasó `testzip()`. SHA-256 `FCDCE3229717A2A148E7CDA0AB5BDB667F39D8FB33EDE1DA8DABC336BD5AD110` coincide con el pin de `releases/resolve-nsis.ps1`. El resolver vuelve a descargar/extraer el ZIP a un directorio indicado; no depende de esta expansión histórica.
- Eliminados 441 archivos expandidos (7.129.771 B); se conservaron el ZIP upstream de 2.358.406 B y el resto del snapshot E2E. Ruta ausente verificada y ZIP retenido sin cambios. No se ejecutaron tests/builds.

## Cachés Chromium purgadas de perfil Electron histórico - 2026-10-07

- En `output/playwright/electron-packaged-userdata-20260909` se retiraron seis árboles Chromium puramente cacheables (`Cache`, `Code Cache`, `GPUCache`, `DawnGraphiteCache`, `DawnWebGPUCache`, `Shared Dictionary`): 41 archivos / 4.689.838 B. El perfil es de 2026-09-09; no hay proceso de BAGO/Electron usando esa ruta.
- Se conservaron `Local Storage`, `Session Storage`, `Network`, `Preferences`, `Local State` y `boot.log` del perfil. Verificación posterior confirmó las cachés ausentes y esos datos aún presentes. No se ejecutaron tests/builds.

## Medición posterior de cleanup - 2026-10-07

- `output` quedó en 514.151.974 B / 2.783 archivos regulares; bajó 11.819.609 B entre las mediciones antes/después de retirar la expansión de NSIS (7.129.771 B) y cachés Chromium (4.689.838 B). El delta coincide exactamente con bytes de archivo retirados.
- Inventario actual sin seguir junctions: `.run` 953.917.810 B / 35.747 archivos (8.965 reparse points omitidos); `artifacts` 250.257.712 B / 159 archivos; `output` 514.151.974 B / 2.783 archivos. No usar los tamaños viejos inflados por junctions.

## Cachés Chromium eliminadas de perfiles Electron adicionales - 2026-10-07

- Se conservaron los estados distintos de `output/electron-user-data-packaged-rerun-20260909` y `output/playwright/inspect-packaged-userdata`; se retiraron sólo sus cachés Chromium estándar. Eran perfiles de 2026-09-09, sin proceso activo que los usara.
- 88 archivos de caché en 12 subdirectorios sumaban 16.644.947 B. Se verificó que Local Storage, Session Storage, Network, Preferences y demás archivos de perfil quedaran intactos. No se ejecutaron tests/builds.


## Revisión de los mayores bloques de almacenamiento - 2026-10-07

- Estado medido de nuevo, omitiendo reparse points: `.run` 928.847.684 B (34.391 archivos); `artifacts` 250.258.824 B (159); `output` 474.331.168 B (2.672); `releases` 2.434.150.298 B (58); `.worktrees` 228.743.463 B (22.621); `.git` 2.279.441.818 B (724). HEAD sigue `3978de3404584f93697208063aef621a83522ba2`; checkout sigue dirty con cambios previos ajenos a esta limpieza.
- `releases/archive` aporta 2.434.050.123 B; los 12 payloads locales de más de 100 MiB suman aproximadamente 2,26 GiB. El README local establece retención histórica por versión. Consulté los releases/asset digests actuales con `gh release view` y comparé SHA-256 de todos esos payloads locales: ninguno coincide con el asset de mismo nombre/versión consultado donde existe. En varios tags ni siquiera está publicado un asset de distribución equivalente; `v4.9.1` está como borrador/untagged. La mera existencia de release público no prueba que estas copias sean intercambiables. No se eliminó ningún payload de release.
- Mayor archivo único de `.run`: `.run/BAGO-audit-bundle-20260822-173024.zip`, 708.830.834 B (676 MiB), no rastreado, SHA-256 `73378B7ED189F81943EFBDB5873C7F549AC4F7070947B18C6490B80081362D69`. La inspección previa encontró un ZIP estructuralmente dañado, 3.281 entradas locales completas y contenido de auditoría/snapshot único; no hay prueba de equivalencia ni sustituto completo. Se conserva hasta poder reconstruir y verificar su contenido sin pérdida.
- `E_KITS_Y_HERRAMIENTAS` fuera del checkout mide 9.355.013 B / 712 archivos; no es fuente material del consumo de GB.
- Resultado de esta revisión: no se borraron estos bloques grandes porque la evidencia actual no demuestra que sean basura ni que exista sustituto equivalente. No se ejecutaron tests ni builds.


## Cachés generadas retiradas de `.run` y `output` - 2026-10-07

- Preflight dinámico identificó 113 directorios exactos de caché (`__pycache__`, `.pytest_cache`, `DawnGraphiteCache`, `DawnWebGPUCache`, `Shared Dictionary`): 827 archivos / 35.178.115 B. No estaban rastreados, no contenían reparse points y ningún proceso Python/pytest/Electron/Chrome/Edge tenía esos árboles en su línea de comandos. Se validó que cada ruta resuelta quedara bajo `.run` u `output` antes de retirarla.
- Ejecución: se borraron solo esos 113 directorios de bytecode/caché. Verificación inmediata: todas las rutas objetivo ausentes (`CacheDirsRemaining=0`). Reducción nominal 35.178.115 B (33,55 MiB); no se atribuye un delta de espacio libre de C: por posible actividad concurrente.
- No se borraron perfiles, historial, almacenamiento local, logs, snapshots ni artefactos de prueba. No se ejecutaron tests/builds.


## Duplicados grandes y consumo del almacén Git - 2026-10-07

- Se recalcularon hashes de los 16 archivos >100 MiB de `.run`, `artifacts`, `output`, `releases` y `.worktrees`: cero grupos SHA-256 duplicados. En el rango de 20-100 MiB se examinaron 3 archivos adicionales: cero duplicados. Este resultado no prueba duplicación cero para cada archivo pequeño ni equivalencia semántica de paquetes con hashes distintos.
- `.git`: `git count-objects -vH` reporta 2 packs / 2,10 GiB, 37.090 objetos en pack, 10,86 MiB loose, 0 garbage y 0 size-garbage. Lectura de ambos índices con `git verify-pack -v`: ningún blob individual >=10 MiB. No se encontró un archivo gigante suelto que retirar; el peso está distribuido por el historial empaquetado. No se reescribió ni podó el almacén Git.
- El ahorro seguro comprobado en esta tanda sigue siendo 35.178.115 B de cachés. Los bloques mayores restantes carecen de duplicado exacto probado o contienen payloads/evidencia únicos; se conservan.


## ZIP de auditoría recuperado y deduplicado sin pérdida lógica - 2026-10-07

- El archivo original de 708.830.834 B carecía de directorio central ZIP. Se leyeron y verificaron CRC/tamaño de 3.281 entradas locales válidas (3.233 archivos + directorios); la entrada siguiente, `BAGO/releases/bago-4.9.0-setup.exe`, declara 150.526.240 B expandidos pero su header da CRC/tamaño comprimido cero. Se preservaron literalmente los 12.435.520 bytes desde ese header hasta EOF como `_recovery/corrupt-tail.bin`; no se afirmó recuperar el EXE.
- El bundle contenía 1.485 rutas con payload comprimido idéntico a otra ruta (método, CRC, longitudes y SHA-256 del flujo comprimido coincidentes), 54.246.449 B de copias comprimidas. El ZIP recuperado guarda una copia canónica de cada payload y un manifest con la ruta fuente para reconstruir las demás. Incluye `restore_deduplicated.py`; no se altera el contenido lógico de las rutas recuperables.
- Recuperación temporal ejecutada: helper materializó 3.234 archivos incluyendo el tail crudo, verificó los SHA-256 y las 1.485 rutas deduplicadas; la carpeta temporal se eliminó al acabar.
- Reemplazo del archivo defectuoso solo después de validar candidato y recuperación: el ZIP final abre con `zipfile`, `testzip()==None`, SHA-256 `E12339FA2FEE64441D291374A2B6289E568D3A34AC767615D84424B3B1098EA6`, 654.890.235 B. El manifest liga la recuperación al hash original `73378B7ED189F81943EFBDB5873C7F549AC4F7070947B18C6490B80081362D69`. Se retiró el original corrupto después de la verificación. Ahorro nominal neto del artefacto: **53.940.599 B**.
- El helper de recuperación usado para producir el archivo permanece en `.run/recover_audit_bundle.py` como procedencia reproducible. No se ejecutaron tests/builds.


## Basetemps antiguos de pytest retirados - 2026-10-07

- `git ls-files -- .run` no devuelve rutas. Los 86 directorios directos `gate-*`/`pytest-*` eran basetemps de pruebas entre agosto y el 25/09; el generador actual los usa como `--basetemp=.run/gate-{stamp}-{name}`. La inspección independiente no halló referencias de esos nombres en evidencia/auditorías, scripts, docs ni CI; no había proceso activo apuntando a esos roots.
- Preflight del contenido restante antes del borrado: 54.258.924 B, 7.375 puntos de reparse, todos internos a su root; cero hardlinks y cero rutas rastreadas. Las 463 entradas de solo lectura eran fixtures, incluidas copias `.git` creadas por tests; se quitó ese atributo únicamente en esos roots. Se retiraron los 86 roots; comprobación posterior: ninguno permanece. Ahorro nominal adicional: 54.258.924 B.
- Incidente durante el primer intento: tras validar una restauración temporal de los roots, la limpieza chocó con un blob de fixture marcado solo lectura. Un error en el tratamiento de fallo eliminó el ZIP temporal después de comenzar el borrado. Antes de detenerse se retiraron 306 archivos / 925.443 B del root `.run/gate-0cc87678-backend-full`; la comparación confirma que ese root era salida generada de pytest no rastreada, sin receipt canónico ni consumidor encontrado. Esos 306 archivos ya no tienen copia en el checkout. No se tocaron archivos rastreados ni fuentes; la limpieza final retiró las salidas de test restantes.
- Total nominal retirado de los 86 roots desde el inventario inicial: 55.184.367 B (54.258.924 B en la pasada final + 925.443 B retirados en el intento interrumpido). No atribuyo el mismo delta al espacio libre de C: por actividad concurrente. No se ejecutaron tests/builds.


## Worktrees limpios redundantes retirados - 2026-10-07

- Se retiraron seis worktrees locales de rama que estaban limpios y cuyo contenido ignorado se limitaba a cachés/build reproducibles; antes de retirarlos se comprobó que ningún proceso activo apuntaba a esos paths. Se usó `git worktree remove`, sin borrar ramas ni commits.
- Rutas: `.worktrees/causal-receipt-20260930` (15.207.444 B), `nsis-inventory-20260930` (17.494.960 B), `spbe-runtime-20260930` (15.146.702 B), `dependency-audit-20260930`, `map-state-refresh-20260927` y `scanner-bootstrap-coverage-20260930` (estas tres últimas sumaban 52.040.137 B según el inventario sin reparse points). Total nominal retirado: 99.889.243 B (~95,26 MiB); el cálculo excluye reparse points y no se presenta como delta observado de C:.
- Verificación posterior: los seis paths no existen; las seis ramas permanecen y apuntan a commits existentes; `git worktree list` ya no los enumera. El espacio físico restante bajo `.worktrees` mide 128.838.093 B / 11.792 archivos regulares (sin seguir reparse points).
- Se conservaron los worktrees sucios, el worktree padre con un hijo registrado, `map-ui-interaction-20260930` y `pr230-repair` con estado `.bago`/`.gabo` local sin clasificación completa.


## Corrección de inventario y reparse points - 2026-10-07

- Corrección de método: una medición recursiva anterior contó contenido alcanzado a través de junctions de Windows. `python 3.14.5` permite detectar junctions con `os.path.isjunction`; el inventario actualizado las excluye junto con symlinks y reparse points en directorios y archivos.
- Totales físicos sin seguir reparse points: `.run` 784.588.993 B / 10.315 archivos (1.590 reparse points omitidos); `output` 474.299.331 B / 2.670 archivos; `artifacts` 250.267.555 B / 159; `releases/archive` 2.434.050.123 B / 33; `.worktrees` 128.838.093 B / 11.792 (8 omitidos). Esto supersede mediciones previas mayores que siguieron junctions.
- `.run/validated-worktree/backend/node_modules` es una junction hacia `backend/node_modules` del checkout principal (confirmado con `Get-Item.LinkType/Target` y `fsutil reparsepoint query`). Sus 316.560.803 B son compartidos: no se borraron ni se contarán como espacio recuperable al retirar el worktree. El worktree registrado permanece.
- Los bytes atribuidos antes a worktrees retirados son estimaciones del inventario previo, no un delta de espacio libre medido; al no conservarse un manifiesto por fichero con atributo de reparse, no afirmo que todo ese total se haya recuperado físicamente. Los paths sí están ausentes y sus ramas/commits siguen presentes.
- Los ZIPs de auditoría `BAGO-third-party-audit-20260822-173517.zip` y `BAGO-third-party-audit-corrected-20260822.zip` pasaron `testzip()`, pero el cotejo por ruta y SHA revela sólo 1.371 archivos idénticos, cuatro archivos comunes modificados, 146 rutas sólo en el primero y 204 sólo en el corregido. No son sustitutos completos; ambos se conservan.


## Revisión interna de los payloads de `releases/archive` - 2026-10-07

- Recorrí los 33 archivos regulares y calculé SHA-256 de cada uno. `git ls-files -- releases/archive` devuelve sólo el README y dos scripts históricos de 4.8.4; los payloads binarios son locales/ignorados. El README local los cataloga como instaladores y distribuciones versionados, no como cachés o intermediarios.
- Los binarios de 4.9.0 incluyen un setup de 303.979.891 B y una distribución ZIP de 319.407.789 B; 4.9.1, 4.9.2, 4.9.3, 4.10.0 y 4.11.1 también conservan setup/distribution separados con hashes diferentes. Los sidecars existentes ligan hashes, no reemplazan los bytes. La captura legacy adicional de 4.9.0 contiene un instalador de 102.371.750 B distinto del setup principal y un ZIP legacy de 1.800.073 B con manifest.
- La revisión anterior comparó estos payloads con los assets públicos disponibles y no halló hashes coincidentes; versiones sin asset equivalente y el borrador 4.9.1 impiden acreditar sustitución pública. Los artefactos son únicos y pueden no reconstruir los mismos bytes/firmas desde el código fuente. No hay intermediario de build identificado con evidencia suficiente para eliminar. Se conservan por ahora; eliminar estos binarios recuperaría GB, pero implicaría perder payloads históricos locales únicos, por lo que no los clasifiqué como basura.


## ZIPs de auditoría consolidados con precedencia avanzada - 2026-10-07

- Se fusionaron `.run/BAGO-third-party-audit-20260822-173517.zip` y `.run/BAGO-third-party-audit-corrected-20260822.zip` en `.run/BAGO-third-party-audit-merged-20260822-advanced.zip`. La política conserva la estructura estable del baseline y delta; el bundle avanzado corregido gana en 13 conflictos por ruta normalizada. Las dos versiones antiguas de cada conflicto se guardan bajo `_merge/superseded/old/`; permanecen además 2 rutas sólo antiguas y 60 sólo avanzadas.
- SHA-256 de entradas: antiguo `8f92998edbc7f815450aa246197a0b16ee68be6af27006cc9d523b762da3764d`; avanzado `704cf860071b5219fb10be8311ef690a18528b21e838ca8668996779736c5e56`. El ZIP final conserva `MERGE-MANIFEST.json` con hashes/procedencia de cada ruta. SHA-256 final `8082c918c2282dbeb558a58630175c2a37618115de481af07111c23be00674be`, 7.992.040 B; sidecar `.sha256` presente.
- Verificación: `ZipFile.testzip()` PASS antes y después de eliminar fuentes; los hashes de todos los miembros concuerdan con la variante seleccionada o su copia `superseded`; ambas fuentes originales ausentes. Reducción nominal: 2.856.085 B frente a la suma de los ZIP iniciales. No se ejecutaron tests/builds del proyecto.
