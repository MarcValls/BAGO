# SignPath Foundation dependency and binary inventory

Estado de esta revisión: `EXECUTED · PRELIMINARY REVIEW`

Esta revisión comprueba la composición visible del candidato local antes de
solicitar admisión en SignPath Foundation. No es una opinión legal ni una
aceptación de SignPath.

## Alcance y reproducibilidad

Se inspeccionaron los manifiestos `package.json`, los lockfiles npm, los dos
proyectos .NET del bootstrap y los binarios rastreados bajo
`bootstrap/msix-host/HashTool/bin/Release`.

Comandos ejecutados:

```text
npm ci --ignore-scripts --no-audit --no-fund
npx --yes license-checker --start . --json
npx --yes license-checker --start frontend --json
npx --yes license-checker --start electron-viewer --json
npx --yes license-checker --start backend --json
dotnet list bootstrap/msix-host/Bago.Bootstrap.Host.csproj package --include-transitive
dotnet list bootstrap/msix-host/HashTool/HashTool.csproj package --include-transitive
```

La herramienta npm usada fue `license-checker 25.0.1`.

## Dependencias npm

| Árbol | Paquetes observados | Licencias observadas | Resultado superficial |
|---|---:|---|---|
| raíz y workspaces | 351 | MIT, ISC, BSD-2-Clause, BSD-3-Clause, Apache-2.0, MPL-2.0, 0BSD, BlueOak-1.0.0, Python-2.0, WTFPL y combinaciones permisivas | Sin `UNLICENSED`, `Proprietary` o licencia desconocida detectada |
| `frontend` | 5 instalados en el árbol local | MIT | Sin licencia sospechosa |
| `electron-viewer` | 1 propio en el árbol aislado | MIT | Sin licencia sospechosa |
| `backend` | 257 | Las mismas familias permisivas; predominan MIT/BSD/ISC/Apache | Sin licencia sospechosa |

El resultado no detectó dependencias npm con licencia `UNKNOWN`, `UNLICENSED`,
`Proprietary`, `Commercial` o `Custom`. `MPL-2.0` es una licencia OSI, pero
requiere conservar sus avisos y respetar sus condiciones de modificación del
componente cubierto.

## Bootstrap .NET y binarios

El proyecto `Bago.Bootstrap.Host` declara `pythonnet 3.1.0`. El paquete NuGet
incluye su fichero `LICENSE` MIT y el nupkg observado tiene este SHA-256:

```text
17CDBE152BA4ECE3A6F0D04A3A3C5B6459532F58DB3545DECE0CA3AD9C5B7B23
```

Los binarios rastreados fueron inspeccionados por metadatos PE:

| Binario | Editor/metadatos | Licencia/procedencia observada | SHA-256 |
|---|---|---|---|
| `Microsoft.Windows.SDK.NET.dll` | Microsoft Corporation; Windows SDK for .NET 8; 10.0.19041.55 | Licencia Microsoft enlazada desde el nuspec (`https://aka.ms/WinSDKLicenseURL`) | `0EC371D93798852E36461C8ADDDBEADCE0F963A04752F0B64E54FE19C1C834A7` |
| `Python.Runtime.dll` | Python.Runtime; 3.1.0.0 | MIT por el paquete `pythonnet` | `B6BC592D4F9CB5CCA23328BC45CC37A9E237D15FD2EDEC660B4C74DB1CED534F` |
| `WinRT.Runtime.dll` | Microsoft Corporation; C#/WinRT; 2.2.0.48161 | Componente Microsoft del Windows SDK; conservar aviso/licencia Microsoft | `BCF3A14E8712A90837FC5C8D8C8A24696AF2BD7F74E9767597EC81EDEDFB23DB` |

No se observó un binario de tercero con editor desconocido que pudiera
clasificarse como propietario a simple vista.

## Imports Python observados

Se hizo un analisis AST sobre el codigo Python activo (`backend/bago_core` y
`backend/.bago`), excluyendo `tests`, `dist`, `release`, `node_modules` y
artefactos temporales. Se distinguieron los imports de produccion de modulos
propios y de dependencias opcionales. `anthropic` es un modulo propio de
`backend/.bago/providers/anthropic.py`; no se cuenta como dependencia PyPI.

| Import | Distribucion/version observada | Licencia observada | Estado |
|---|---|---|---|
| `jsonschema` | `jsonschema 4.23.0` | MIT (`COPYING`) | Produccion; validacion de catalogos |
| `numpy` | `numpy 2.4.4` | BSD-3-Clause y avisos de componentes incluidos | Opcional; capa RL desactivable |
| `prompt_toolkit` | `prompt_toolkit 3.0.52` | BSD-3-Clause | Opcional; REPL interactivo |
| `psycopg` | `psycopg 3.3.6` | LGPL-3.0 con permisos adicionales de Psycopg | Opcional; claims PostgreSQL |
| `tzdata` | `tzdata 2026.2` | Apache-2.0 | Opcional; fallback de zonas horarias |
| `yaml` / `PyYAML` | `PyYAML 6.0.3` | MIT | Opcional; catalogos YAML |
| `tomli` | `tomli 2.4.1` | MIT | Fallback solo para Python sin `tomllib` |
| `pytest` | `pytest 9.0.3` | MIT | Solo herramienta de desarrollo/test |
| pytest-subtests | pytest-subtests 0.15.0 | MIT | Solo herramienta de desarrollo/test; instalada en workflow de validacion |

El workflow de CI declara actualmente estas versiones de validacion: `pytest==9.0.3`, `pytest-subtests==0.15.0`, `numpy==2.4.4`, `prompt_toolkit==3.0.52` y `tzdata` sin pin. Se ha incluido `pytest-subtests` en esta revision porque forma parte del entorno de validacion aunque no sea una dependencia de produccion.

El inventario instalable queda separado en `backend/requirements-runtime.txt`
(dependencias directas de runtime, incluidas las opcionales) y
`backend/requirements-ci.txt` (validacion). Los workflows de CI consumen el
segundo archivo; ambos manifiestos fijan las versiones directas observadas.

Esta tabla es un inventario de procedencia, no un lockfile. Las versiones
observadas se conservaron como evidencia de la revision, pero el backend sigue
con los manifiestos directos ya declarados.

## Hallazgos y límites

1. No hay evidencia de una dependencia propietaria incompatible en los árboles
   npm inspeccionados.
2. Los componentes Microsoft requieren que el paquete distribuido conserve sus
   avisos y términos aplicables; esta revisión no sustituye una comprobación de
   los notices incluidos en el artefacto final.
3. Los manifiestos `backend/requirements-runtime.txt` y
   `backend/requirements-ci.txt` declaran y fijan las dependencias directas
   observadas. Sus dependencias transitivas no estan fijadas mediante hashes;
   ese es el limite reproducible que queda documentado.
4. Los binarios generados rastreados bajo `bin/Release` deben excluirse del
   origen de publicación o regenerarse desde un build reproducible antes de
   enviar la solicitud a SignPath.
5. Este documento no demuestra que SignPath Foundation haya aceptado BAGO ni
   que el repositorio cumpla todavía todas sus condiciones de proyecto open
   source.

## Veredicto

`PASS_WITH_DOCUMENTED_PACKAGE_NOTICES_PENDING`

La revision superficial no encontro componentes de terceros claramente
propietarios o incompatibles. La solicitud a SignPath puede pasar a revision de
elegibilidad desde el punto de vista de licencias directas. Antes de publicar
un candidato debe cerrarse la politica de notices de Microsoft/terceros y
excluir binarios generados no reproducibles.
