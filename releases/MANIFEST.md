# BAGO 4.9.0 Historical Release Manifest (obsolete snapshot)

> This manifest is preserved as historical input only. Its commit/tag claims
> are not authoritative for the current candidate and conflict with the tag
> identity verified in `releases/INDEX.md`.

**Release Date:** 2026-08-18  
**Version:** 4.9.0  
**Tag:** `v4.9.0` (`f1dcd765f63989e1a66a774c8fba9805fdfef3ee`)  
**Commit `main`:** `4ad27a0a4a154d20740d62bfbc20c888a0f2f3cc`

## Official Artifacts

1. `BAGO-Installation-Manager-4.9.0-win-x64.exe` (102,371,750 bytes) — official NSIS installer
2. `BAGO-Installation-Manager-4.9.0-win-x64.exe.sha256` (66 bytes)
3. `bago-v4.9.0.zip` (1,800,073 bytes) — thin update package
4. `bago-v4.9.0.zip.sha256` (83 bytes)
5. `bago-v4.9.0.zip.manifest.json` (122,275 bytes)
6. `latest.yml` (182 bytes) — auto-update metadata

## Legacy / Offline Alternatives

- `bago-4.9.0-setup.exe` (150,568,960 bytes aprox.) — legacy offline installer, SHA256 `D2DD1004230346CB2648E2070408AE2C6DEF65AB6F9DB9822BAB4ABBCEBB8C72`

## Distribution Guarantees in 4.9.0

- Official installer is fail-closed: every critical NSIS step aborts on non-zero exit.
- `BAGO-Installation-Manager-4.9.0-win-x64.exe` embeds the full backend + frontend + Electron payload.
- Installer source is pinned to immutable tag+commit (`APP_GIT_REF` + `APP_GIT_SHA`).
- Final gate verifies `BAGO.exe` exists before writing registry/shortcuts.
- Electron app startup validates backend readiness (`/health`) before opening UI.
- CI includes packaged smoke for `BAGO.exe` lifecycle on Windows.
- `latest.yml` always points to the matching official installer SHA512/size.

## Install Paths and Shortcuts

- Install root: `%LOCALAPPDATA%\\BAGO`
- Start Menu and Desktop shortcuts target:
  - `%LOCALAPPDATA%\\BAGO\\BAGO.exe` (official NSIS layout)
  - `%LOCALAPPDATA%\\BAGO\\electron-viewer\\dist\\win-unpacked\\BAGO.exe` (legacy layout)
- Registry traceability keys:
  - `HKCU\\Software\\BAGO\\InstallPath`
  - `HKCU\\Software\\BAGO\\InstallRef`
  - `HKCU\\Software\\BAGO\\Version`

## Notes

- The installer and release assets are version-locked to `4.9.0`.
- Release generation must use a tagged immutable ref, never mutable `main`.
- The official release format uses electron-builder NSIS, not the older PowerShell/NSIS hybrid.
