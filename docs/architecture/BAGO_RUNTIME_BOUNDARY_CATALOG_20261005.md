# Catálogo de la frontera del runtime de BAGO

**Fecha:** 2026-10-05
**Repo/candidato inspeccionado:** rama `publish/worktree-groups-20261003-7f5d47a6`, HEAD `62e6189c3cdd4bf058253b1179f8ecb08ec1dd62`
**Versión fuente:** `release_version.txt` = `4.11.3`
**Estado:** `EXECUTED` como inspección estática; arranque de la aplicación `NOT_RUN`.

## Criterio

La frontera se traza desde el acceso de inicio hasta el backend y la interfaz que sirven esa sesión. Los ficheros recorridos por ese flujo se clasifican como **runtime directo** o **runtime condicional**. Todo lo demás queda catalogado por función —build, distribución, soporte, pruebas, documentación, estado local o histórico—; estar fuera del arranque no significa automáticamente que sea obsoleto ni que deba borrarse.

Este catálogo no movió ni eliminó ficheros. La inspección encontró un worktree con cambios locales: 30 rutas rastreadas modificadas en el recuento sin untracked y miles de artefactos locales. Se conservaron. Los directorios locales con acceso denegado se catalogan por su raíz y función aparente, sin afirmar que se inspeccionó cada elemento interno.

## Arranque que se encuentra en el repo

### Acceso `ARRANCAR_BAGO.bat`

```text
ARRANCAR_BAGO.bat
  -> scripts/bago-launcher.ps1
       -> scripts/dev.ps1 start
            -> backend/scripts/build_ui_dist.py
                 frontend/src/** -> frontend/dist/** -> backend/ui-react/dist/**
            -> electron-viewer: npm run dist (prepara el viewer)
            -> backend: python -m bago_core.launcher serve --host 127.0.0.1 --port 8080
            -> electron-viewer: electron .
       -> Electron se vuelve a invocar desde bago-launcher.ps1
```

Evidencia: el `.bat` invoca `bago-launcher.ps1` ([ARRANCAR_BAGO.bat:9](../../ARRANCAR_BAGO.bat#L9)); el wrapper ejecuta `dev.ps1 start` y luego inicia su propio `electron.exe` ([bago-launcher.ps1:18](../../scripts/bago-launcher.ps1#L18), [bago-launcher.ps1:41](../../scripts/bago-launcher.ps1#L41)). `dev.ps1 start` ya construye/sincroniza UI, prepara el viewer, inicia backend y Electron ([dev.ps1:232](../../scripts/dev.ps1#L232)); el backend se lanza desde `backend/` con `bago_core.launcher serve` ([dev.ps1:59](../../scripts/dev.ps1#L59)).

El segundo Electron usa el mismo `electron-viewer/main.cjs`, que solicita un single-instance lock y termina si no lo obtiene ([main.cjs:162](../../electron-viewer/main.cjs#L162)). **Conflicto estático:** el `.bat` solicita dos inicios de Electron. Además, el `before-quit` del viewer solo detiene el backend en modo empaquetado; en desarrollo sale sin pararlo ([main.cjs:440](../../electron-viewer/main.cjs#L440)), mientras el wrapper afirma esperar al cierre y detener BAGO. No ejecuté la UI, así que el resultado del doble inicio y el ciclo real de cierre quedan como `NOT_RUN`; el conflicto de llamadas sí está confirmado en el código.

### Entrada `npm start`

El script `start` de la raíz invoca directamente `scripts/dev.ps1 start` ([package.json:8](../../package.json#L8)). Esa ruta evita el segundo inicio del wrapper `bago-launcher.ps1`, aunque conserva las limitaciones de ciclo de vida de `dev.ps1`/`main.cjs` indicadas arriba.

### Backend, sesión e interfaz

`bago_core.launcher` registra el resolver y las rutas de `core`, `chat` y `providers` ([launcher.py:29](../../backend/bago_core/launcher.py#L29)). `cmd_serve` añade `core` y `api`, restaura o crea `SessionManager`, restaura el modelo, registra la sesión y levanta `BagoAPIServer` ([cmd_content.py:128](../../backend/bago_core/commands/cmd_content.py#L128)). Si no se pasa `--ui-dist`, sirve `backend/ui-react/dist` cuando existe ([cmd_content.py:172](../../backend/bago_core/commands/cmd_content.py#L172)).

La fuente React entra por `frontend/src/main.tsx` y monta `ControlPlane` ([main.tsx:1](../../frontend/src/main.tsx#L1)). `backend/scripts/build_ui_dist.py` construye `frontend` y copia su `dist` a `backend/ui-react/dist` ([build_ui_dist.py:57](../../backend/scripts/build_ui_dist.py#L57)). Electron apunta a ese `uiDist`, espera `/health` y carga el HTML local cuando está disponible ([main.cjs:52](../../electron-viewer/main.cjs#L52), [main.cjs:277](../../electron-viewer/main.cjs#L277)).

El contrato de resolver está en `backend/docs/contracts/resolver_contract.json`, cargado por `backend/bago_core/resolver/manifest.py` ([manifest.py:9](../../backend/bago_core/resolver/manifest.py#L9)). Define roots y paquetes bajo `backend/.bago` y permite fallback a `backend/bago_core`; por eso ese JSON, aunque esté bajo `docs/contracts`, es dependencia de runtime.

## Qué debe permanecer junto a su función actual

| Ruta o patrón | Clasificación | Motivo y evidencia |
|---|---|---|
| `ARRANCAR_BAGO.bat`, `DETENER_BAGO.bat` | Entrada/salida de escritorio | El primero enlaza con el flujo detallado arriba; el segundo llama `scripts/dev.ps1 stop` ([DETENER_BAGO.bat:17](../../DETENER_BAGO.bat#L17)). |
| `scripts/dev.ps1` | Runtime de desarrollo | Orquesta el build, backend y Electron. El comando `start` está en las líneas 232–245. |
| `scripts/bago-launcher.ps1` | Runtime de desarrollo, con conflicto | El `.bat` lo invoca hoy; su segundo lanzamiento debe resolverse antes de retirarlo o renombrarlo. |
| `backend/bago_core/**` | Código backend/runtime | Incluye CLI, resolver, comandos y launcher. Los módulos concretos se cargan según comando y petición. |
| `backend/{bago,bago.cmd,bago.ps1,bago.sh,protocol.py,ir_types.py,registry.py,version.py,versions.json}` | Entradas y módulos compartidos de CLI/Framework | No todos se cargan al servir la UI; los shims translator/IR y los builders de release los referencian y los empaquetan. |
| `backend/.bago/{api,chat,core,knowledge,providers,tools,integrations}/**` | Paquetes runtime y capacidades condicionales | El contrato del resolver, los cargadores y el empaquetado incluyen estos paquetes. No cada módulo se importa al abrir la ventana. |
| `backend/.bago/{agents,context,contracts,extensions,mcp,prompts,roles,state.example,templates,workflows}/**`, `backend/.bago/bin/**`, `backend/.bago/*.json` | Capacidades, contratos, plantillas, ejemplos de estado y helpers | Parte del producto ampliado o de su configuración; no se ha demostrado que participe en el primer render. Clasificar por consumo de cada capacidad, no como arranque directo. |
| `backend/.bago/tools.manifest.json` | Registro de capacidades | Declara herramientas que el runtime descubre; ejecución bajo demanda, no todas en el arranque. |
| `backend/docs/contracts/resolver_contract.json` | Contrato runtime | Se lee desde el resolver; no es documentación prescindible. |
| `frontend/src/**`, `frontend/index.html`, `frontend/package.json` y configuración Vite/TS | Fuente UI/build | El bundle canónico se genera desde este workspace; `main.tsx` monta `ControlPlane`. |
| `backend/scripts/build_ui_dist.py` | Puente de build a runtime | Construye frontend y sincroniza el bundle servido por el backend. |
| `backend/ui-react/dist/**` | Salida generada consumida por runtime | El backend/Electron la sirven. No editarla como fuente: se regenera desde `frontend`. |
| `electron-viewer/{main.cjs,preload.cjs,diagnostic-log-client.cjs,package.json}` | Shell desktop fuente | Es el viewer de la entrada raíz. El `dist/` de Electron es generado. |
| `package.json`, `package-lock.json`, `frontend/package.json`, `electron-viewer/package.json`, `.node-version`, `.nvmrc` y dependencias instaladas | Resolución/build de dependencias | No son lógica de negocio, pero el arranque de desarrollo depende de los paquetes instalados y manifiestos. |
| `release_version.txt`, `versions.json`, shims de versión | Identidad de versión fuente/derivada | La autoridad actual de versión es `release_version.txt`; las demás apariciones se deben mantener alineadas. |

**No conservar como segunda fuente de UI:** `frontend/dist/**` y el `ui-react/dist/**` de raíz ignorado son resultados locales. El destino de runtime trazado es `backend/ui-react/dist/**`.

## Catálogo del resto del árbol

“Fuera del arranque” significa que no aparece en la cadena principal anterior. Mantener estos grupos en su carpeta funcional hasta comprobar consumidores adicionales; no marcarlos como obsoletos solo por no arrancar con la UI.

| Ruta/patrón | Clasificación | Tratamiento en este catálogo |
|---|---|---|
| `backend/electron/**`, `backend/manager/**`, `backend/electron/runtime-service.cjs`, `backend/package.json`, `backend/package-lock.json` | Superficie de producto secundaria: BAGO Installation Manager | Separada del viewer raíz `electron-viewer/`. Se usa por `backend/open-ui-bago.cmd` o el árbol de release; requiere su propia línea de vida. |
| `backend/open-ui-bago.cmd` | Entrada secundaria de manager desde fuente | Ejecuta `python -m bago_core.launcher manager --port 0`. No es el launcher del viewer raíz. |
| `backend/scripts/runtime-service.ps1` | Lifecycle de runtime empaquetado | Se usa cuando `electron-viewer/main.cjs` resuelve una raíz instalada/empaquetada. Distinto de `scripts/dev.ps1`. |
| `backend/open-electron-bago.cmd` | Entrada secundaria al release tree | Apunta explícitamente a `backend/release/v4/current` ([open-electron-bago.cmd:3](../../backend/open-electron-bago.cmd#L3)). |
| `backend/release/v4/current/**` | Release tree local generado; desalineado | Los archivos actuales dicen `4.9.3`; `release_version.txt` de raíz dice `4.11.3`. El manifiesto local declara fecha 2026-09-02, 734 ficheros y SHA de árbol `c38401e…`; el sidecar repite ese hash. Como el launcher secundario lo abre, clasificar como **conflicto activo**, no como archivo muerto. No se reconstruyó ni movió. |
| `backend/index.html` | Entrada HTML duplicada incluida por el script de release | Apunta a `/src/main.tsx`, mientras el launcher principal genera desde `frontend/` y sirve `backend/ui-react/dist`. `package_v4.py` incluye este `index.html` ([package_v4.py:38](../../backend/scripts/package_v4.py#L38)); marcar como **candidato a reconciliar**, no como runtime raíz confirmado. |
| `backend/lista-bago.html` | Página auxiliar independiente | No aparece en la ruta de arranque raíz inspeccionada; conservar como auxiliar hasta comprobar su consumidor. |
| `backend/scripts/package_v4.py`, `bootstrap/**`, `install-remote.ps1`, instaladores y scripts de release | Build, bootstrap e instalación | Forman la entrega/instalación de BAGO; no se ejecutan en cada arranque de desarrollo. |
| `scripts/**` excepto `dev.ps1` y `bago-launcher.ps1` | Build, publicación, inventario y mantenimiento | No son parte del camino de apertura ordinario por lo observado; conservar como tooling hasta rastrear cada invocación de CI, release y soporte. |
| `backend/tools/**`, `backend/contracts/**`, `backend/assets/**`, `backend/root/plan.txt` | Herramientas, contratos generados, recursos y propuesta | Fuera del arranque raíz. Mantener cada subgrupo según su función; `plan.txt` es material de plan y no módulo ejecutable. |
| `backend/tests/**`, `backend/tests_local/**`, `backend/test_*.py`, `backend/pytest.ini`, `backend/requirements-*.txt`, `frontend/tests/**`, `frontend/capture_screenshots.mjs`, configuración de CI, `.github/**`, `.githooks/**` | Ingeniería, calidad y automatización | No runtime de usuario; necesarios para construir, revisar o mantener el producto. |
| `backend/docs/**` excepto `contracts/resolver_contract.json`; `docs/**`; `README*`, `DOCUMENTATION.md`, `TASK_COMPLETION_SUMMARY.md`, `QWEN.md`, `CODEX_SESSION_RESUME.md`, `AGENTS.md`, `frontend/*.md`, `frontend/fuentes/**` | Documentación, contratos explicativos y evidencia | No cargados por la ruta de UI; algunas instrucciones son para instalación, operación, auditoría o decisiones. Históricos y propuestas se mantienen identificados como tales. |
| `backend/bago_core/tags/v4.*.json` | Metadatos históricos/versionados | No encontré importadores Python dentro de `backend/bago_core`; quedan como `NO_REFERENCIA_ESTÁTICA_EN_ESE_ÁMBITO`, no como borrables. |
| `docs/archive/frontend-ui/**`, `docs/archive/releases/**`, `releases/archive/**` | Archivo histórico separado | Incluye documentación de versiones anteriores y payloads ya reubicados. Es material histórico; no se usa en el arranque raíz. |
| `releases/archive/v4.8.4/update-release-v4.8.4.ps1` y `.sh` | Actualizadores antiguos archivados | Se sacaron de raíz para evitar confundirlos con el actualizador vigente; no ejecutar desde su carpeta histórica. |
| `examples/**` | Ejemplos y paquetes de muestra | Material de demostración/desarrollo, no requisito para abrir la UI. Puede tener consumidores de pruebas/documentación. |
| `plugins/**`, `.agents/**`, `.codex/**`, `.pi/**`, `manager/android/**` | Extensiones y herramientas de agentes/consumidores | Integraciones o superficies auxiliares; fuera del arranque raíz. Mantener clasificados, no mezclar con los módulos de runtime. |
| `.goals/**`, `.impeccable/**`, `.qwen/**`, `QWEN.md`, `CODEX_SESSION_RESUME.md` | Contexto local, planificación o configuración de herramientas | No código de la aplicación. Conservar separado del runtime; los directorios ignorados pueden contener estado de usuario. |
| `third_party_notices/**`, `LICENSE`, `backend`/root manifests | Avisos y metadata legal/build | Acompañan la distribución o el desarrollo; no son módulos cargados al arrancar. |
| `.gitattributes`, `.gitignore`, `.git/**`, `.worktrees/**`, `vercel.json` | Control de versiones y despliegue externo | Configuración Git/worktree o hosting; no la app local. No mezclar con el código usado al abrir el viewer. |
| `.run/debug.log`, `debug.log`, `nul` (si existe localmente) | Log generado y entrada anómala local | El nombre `nul` produjo un error de lectura en `rg`; contenido/uso `UNRESOLVED`, no clasificarlo como fuente. |
| `releases/**`, `backend/dist/**`, `electron-viewer/dist/**`, `frontend/dist/**` | Payloads y salidas de publicación/build | No son fuente canónica. La carpeta `releases/archive/**` conserva artefactos históricos separados de candidatos actuales. |
| raíz `ui-react/**` ignorada | Duplicado local generado | Ninguna referencia en la ruta trazada; el build canónico escribe `backend/ui-react/dist`. Catálogo como salida local no consumida por el arranque principal. |
| `.run/**`, `.pytest-*`, `.pytest_cache/**`, `output/**`, `artifacts/**`, `.vs/**`, `.playwright-cli/**`, `node_modules/**` | Estado temporal, evidencia local, dependencias o herramientas | No forman parte del código fuente canónico. Algunas salidas alimentan diagnóstico/evidencia; no asumir que son basura. |
| `.worktrees/**` | Checkouts de trabajo Git | No son parte del árbol de producto que abre BAGO; sus cambios/ramas son trabajo aparte y deben conservarse según su estado. |
| `.bago/**` en la raíz del repo y `.gabo/**` local | Contexto/estado de repositorio y workspace | No confundir con `backend/.bago/**`, que contiene paquetes ejecutables del producto. No mover el contexto de la raíz como si fuera código sobrante. |

## Inventario local observado y límites

El recuento de Git dio 1.885 ficheros rastreados. Había 16.068 untracked visibles para Git con exclusiones habituales, más directorios ignorados de gran tamaño. En una pasada recursiva anterior a este catálogo, los mayores fueron `.worktrees` (59.233 ficheros), `.run` (47.900), `output` (12.998), `node_modules` (12.140), `artifacts` (9.482) y `releases` (4.837). Son recuentos de ese momento, no cantidades garantizadas del estado final; Git/PowerShell no pudieron leer algunos `.pytest-bago-*` y `backend/.pytest-tmp-bago-final-20260929` por permisos.

Cobertura alcanzada: todos los grupos rastreados quedan asignados por raíz/patrón y se enumeran excepciones que sí participan en runtime aunque estén dentro de `docs` o `backend`. Los contenidos generados y worktrees quedan catalogados por directorio, no descritos fila a fila; los elementos inaccesibles permanecen `UNRESOLVED` hasta tener lectura. No se cambió su ubicación.

## Cierre de esta inspección

- **Confirmado estáticamente:** dependencias del arranque raíz, frontera de fuente UI y bundle consumido, backend de sesión/API, contrato del resolver y dos conflictos de entrada/ciclo de vida.
- **NOT_RUN:** iniciar BAGO, observar ventanas/procesos, probar el cierre del backend, ejecutar pruebas o compilar.
- **Pendiente para limpieza física:** resolver cuál launcher debe ser canónico; reconciliar `backend/release/v4/current` con la versión fuente antes de usar o retirar el acceso que lo invoca; revisar consumidores dinámicos de los grupos `SIN_REFERENCIA_ESTÁTICA`.
- **Resultado:** catálogo `PREPARED` para una decisión de reubicación. No declara ningún otro archivo obsoleto ni autoriza borrados.
