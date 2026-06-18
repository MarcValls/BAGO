# Changelog

## [4.6.3] - 2026-06-18

### Added
- Manager UI restructured around a coherent nodular pipeline model.
- Project analysis flow for opening and inspecting a repository as a new user.
- User-facing bundle for parallel local-model setup without shipping model weights.
- External audit bundle with sidecars for reproducibility and verification.
- Release gate now accepts explicit external artifact paths for offline audit.

### Fixed
- Startup state now resolves outside `Program Files`.
- `"/"` opens the command palette instead of being treated as an empty command.
- Manager launch actions and transpose action are wired.
- Audit bundle generation avoids circular hashes and writes deterministic sidecars.
- Secret scanners ignore explicit test fixtures and skip generated runtime folders.

### Changed
- `Pipelines`, `Ruta`, `Registry`, `Instalaciones`, `Releases`, `Trabajos`, `Sesiones`, `Sistema`, `Salud`, `Auditoría`, and `Métricas` follow a single visual grammar.
- `project` accepts `--root` consistently across `init`, `status`, `link`, and `analyze`.
- Release verification uses explicit artifact paths or `BAGO_RELEASE_ASSETS`.

### Published artifacts
- `BAGO-Installation-Manager-4.6.3-win-x64.exe`
- `bago-v4.6.3.zip`
- `bago-user-v4.6.3.zip`
- `bago-audit-v4.6.3.zip`

### Notes
- The audit bundle is published with `*.sha256`, `*.manifest.json`, `*.snapshot.json`, and `*.report.md` sidecars.
- The user bundle intentionally excludes local model weights and caches.
- The audit bundle intentionally excludes local model weights, caches, credentials, and release/dist/build outputs.
