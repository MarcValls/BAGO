# Public Release Policy

BAGO release artifacts in `release/v4/` are split into two groups:

- Active distribution metadata:
  - `release/v4/latest.yml`
  - `release/v4/release.json`
  - `release/v4/seal/release.json`
  - `dist/latest.yml`
- Historical or archived material:
  - `release/v4/archive/**`
  - versioned snapshots kept for audit or comparison

Current release claims must point at the 4.6.1 bundle:

- ZIP: `release/v4/bago-v4.6.1.zip`
- ZIP checksum: `release/v4/bago-v4.6.1.zip.sha256`
- Installer: `dist/BAGO-Installation-Manager-4.6.1-win-x64.exe`

Rules:

- Do not publish a `release/v4/latest.yml` or `release/v4/release.json` that points at an older build.
- Keep release notes and policy references present in-tree.
- Treat `release/v4/archive/` as historical only.
- Treat `dist/latest.yml` as the installer updater source of truth for the current build.
