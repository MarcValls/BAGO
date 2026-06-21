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

Current release claims must point at the 4.6.4 bundle:

- ZIP: `release/v4/bago-v4.6.4.zip`
- ZIP checksum: `release/v4/bago-v4.6.4.zip.sha256`
- Installer: `dist/BAGO-Installation-Manager-4.6.4-win-x64.exe`
- Audit bundle: `release/v4/bago-audit-v4.6.4.zip`

Rules:

- Do not publish a `release/v4/latest.yml` or `release/v4/release.json` that points at an older build.
- Keep release notes and policy references present in-tree.
- Treat `release/v4/archive/` as historical only.
- Treat `dist/latest.yml` as the installer updater source of truth for the current build.
- Treat the audit bundle as external evidence, not as a replacement for the installer ZIP.

