# Cierre de instalacion global BAGO 4.8.4

Fecha: 2026-08-13

## Veredicto

Instalacion global cerrada y coherente. El runtime, CLI, Electron, accesos directos,
registro y selector de roles usan BAGO 4.8.4.

## Rutas canonicas

- Runtime activo: `C:\Program Files\BAGO`
- Arranque principal: `C:\Program Files\BAGO`
- Desarrollo: `C:\Users\<USER>\BAGO\backend`
- Estado de usuario: `C:\Users\<USER>\AppData\Local\BAGO`
- Selector: `C:\Users\<USER>\AppData\Local\BAGO\install_selection.json`

## Correcciones

- Electron resuelve tanto el monorepo como el runtime instalado plano.
- El runtime instalado dispone de `scripts\runtime-service.ps1` para iniciar y
  detener el backend sin depender del arbol fuente.
- `bago dev` selecciona el backend BAGO 4.8.4 y no cae silenciosamente en
  `bago_fw` 4.8.0.
- El instalador conserva roles separados para `active`, `launch` y `dev`.
- Los fallos de providers no invalidan una instalacion estructural correcta.
- Las pruebas que requieren fuentes frontend se omiten explicitamente en el
  runtime distribuido.
- Se anadio un validador del payload global para detectar Electron incompleto,
  versiones divergentes o archivos esenciales ausentes.

## Evidencia

- `bago --version`: 4.8.4
- `bago dev --version`: 4.8.4
- `bago ign --version`: 4.8.4
- `bago validate`: 11 checks OK
- Runtime instalado: 54 pruebas pasadas, 3 omitidas, 9 subtests pasados
- Frontend: 30 archivos y 88 pruebas pasadas
- Electron real: codigo de salida 0
- Electron resolvio `C:\Program Files\BAGO`, cargo `ui-react\dist`, inicio el
  backend mediante `runtime-service.ps1` y lo detuvo al cerrar.
- Puerto 8080 libre tras el smoke.
- Payload: 9 archivos requeridos, version 4.8.4 y ejecutable 4.8.4.0.
- No existe el ejecutable obsoleto de AppData.
- No existe el selector heredado `~\.bago\install_selection.json`.
- Los accesos directos de Escritorio y Menu Inicio apuntan al Electron global.
- El desinstalador y HKCU apuntan a `C:\Program Files\BAGO`.

## Hashes SHA256

- `electron-viewer\BAGO.exe`: `4241DC416CB9DC98BF46F72F2231C25CDA800D595AA4798BB16B23FD2F88FCDB`
- `electron-viewer\resources\app.asar`: `C7B763B956A285E160BE926ED9389F4D9DFFD4E6198226A556345A41D8D31900`
- `scripts\runtime-service.ps1`: `4EC601F6C733C508C0C8697D755EA38BB7506FF18E8624C486CD918F90E58DAA`
- `bago.ps1`: `3CC26319EC925EE93E7CE9C06936E3EB1CA547D37F07F4F5E8603063043E5806`
- `install_selection.json`: `5BB628D30D2DEEF1DE139F2B9FF8B7751A5AECFE6188F18DD83A3A475CD47BE4`

## Respaldo

`C:\Users\<USER>\Documents\ARQUITECTURA_DE_CONTEXTO\BAGO-global-closure-backup-20260813-223223`

## Advertencias no bloqueantes

- Ollama local esta apagado. Codex y Copilot fueron detectados como saludables.
- BAGO Installation Manager y BAGO Control Plane son productos separados y no
  se eliminaron durante este cierre.
- El repositorio ya contenia cambios de trabajo ajenos a este cierre; no se
  revirtieron ni se mezclaron deliberadamente.
