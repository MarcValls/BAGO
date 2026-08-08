# BAGO 4.8.2 Release Manifest

**Release Date:** 2026-08-06  
**Version:** 4.8.2  
**Tag:** `v4.8.2`

## Artifacts

1. `bago-4.8.2-setup.exe` (362,245,017 bytes)  
2. `bago-4.8.2-backend.zip` (214,569,936 bytes)  
3. `bago-4.8.2-frontend.zip` (178,546 bytes)  
4. `bago-4.8.2-electron-viewer.zip` (13,097 bytes)  
5. `bago-4.8.2-installer.ps1` (3,611 bytes)

## Distribution guarantees in 4.8.2

- NSIS is fail-closed: every critical command aborts on non-zero exit.
- `bago-4.8.2-setup.exe` is offline-first: embeds `bago-4.8.2-distribution.zip` as payload.
- Installer source is pinned to immutable tag+commit (`APP_GIT_REF` + `APP_GIT_SHA`).
- Final gate verifies `BAGO.exe` exists before writing registry/shortcuts.
- Electron app startup validates backend readiness (`/health`) before opening UI.
- CI includes packaged smoke for `BAGO.exe` lifecycle on Windows.

## Install paths and shortcuts

- Install root: `%LOCALAPPDATA%\\BAGO`
- Start Menu and Desktop shortcuts target:
  - `%LOCALAPPDATA%\\BAGO\\electron-viewer\\BAGO.exe` (layout actual)
  - `%LOCALAPPDATA%\\BAGO\\electron-viewer\\dist\\win-unpacked\\BAGO.exe` (legacy layout)
- Registry traceability keys:
  - `HKCU\\Software\\BAGO\\InstallPath`
  - `HKCU\\Software\\BAGO\\InstallRef`

## Notes

- The installer and release assets are version-locked to `4.8.2`.
- Release generation must use a tagged immutable ref, never mutable `main`.
