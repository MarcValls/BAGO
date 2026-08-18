# BAGO 4.8.7 - Release Notes

**Release Date:** 2026-08-16
**Version:** 4.8.7
**Status:** Production Ready

## Installation

Download the artifacts from [GitHub Releases v4.8.7](https://github.com/MarcValls/BAGO/releases/tag/v4.8.7):

| Archivo | Tamano | SHA256 |
|---|---|---|
| BAGO-Installation-Manager-4.8.7-win-x64.exe | 97.63 MB | C8C341CE4A483025A856BEF919EAB40D286D8E3887E86720BC2A9E8373F76269 |
| bago-v4.8.7.zip | 1.72 MB | 6174cb17bd91a2beadb9e4bc9bda5b745ff90e43b5676f3f883520e931e27f2f |

Run the installer or extract the ZIP and launch the backend with:

```powershell
bago serve --base-path "C:\ruta\a\proyecto"
```

To start without resuming the previous workspace, set:

```powershell
$env:BAGO_RESUME_SESSION=0
bago serve --base-path "C:\ruta\a\proyecto"
```

## What's New in 4.8.7

### Correcciones
- **GitHub:** el panel de autenticacion vuelve a detectar correctamente si `gh` esta instalado. Se corrige el enrutamiento en `backend/.bago/api/api_dispatch.py` para usar los handlers que exponen el campo `installed`.
- **Sidebar:** los botones inferiores de **Capabilities**, **Pipeline** y **Tools** ahora abren sus paneles en el drawer; estaban sin registrar en `frontend/src/components/ui/PanelHost.tsx`.

### Coherencia de version
- Todos los manifiestos, `release_version.txt`, `versions.json`, README y lockfiles estan alineados a 4.8.7.

### Verificacion
- Backend tests: 928 passed / 13 skipped
- Frontend tests: 99 passed
- CI: Validate source, validate, CodeQL y Packaged Electron smoke completados correctamente

## Components Versioned

- Backend: 4.8.7
- Frontend: 4.8.7
- Electron viewer: 4.8.7
- Installer: 4.8.7

## Upgrade Notes

This release fixes the runtime regressions introduced in 4.8.6 that prevented the GitHub panel from detecting the `gh` CLI and left several sidebar buttons unresponsive. Users on 4.8.6 should upgrade directly to 4.8.7.
