# BAGO 4.8.2 Manifest

Este documento fija la correspondencia entre versión, instalador y artefactos de release para evitar deriva.

- **Version:** `4.8.2`
- **Tag objetivo:** `v4.8.2`
- **Rama:** `main`
- **Instalador NSIS:** `releases/bago-4.8.2-setup.exe`
- **Manifiesto técnico:** `releases/MANIFEST.md`

## Artefactos de release

- `releases/bago-4.8.2-setup.exe`
- `releases/bago-4.8.2-backend.zip`
- `releases/bago-4.8.2-frontend.zip`
- `releases/bago-4.8.2-electron-viewer.zip`
- `releases/bago-4.8.2-installer.ps1`

## Reglas de consistencia

1. El instalador debe apuntar a `APP_VERSION 4.8.2` y `APP_GIT_REF v4.8.2`.
2. Los nombres de artefacto deben mantener prefijo `bago-4.8.2-*`.
3. La release pública de GitHub debe usar la misma tag `v4.8.2`.
