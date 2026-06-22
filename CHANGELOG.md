# Changelog

## Unreleased

### Changed
- Unified version resolution across `bago_core/__init__.py`,
  `bago_core/version.py`, `bago_core/versioning.py`, `pyproject.toml`,
  `release_version.txt`, and `versions.json`. Version now flows from the
  release file and `versions.json` history.
- Vercel landing page (`index.html`) and build script
  (`scripts/build_vercel_site.cjs`) now render release URLs and repo
  identity from `repo.json` instead of hardcoding `MarcValls/BAGO` and
  `v4.7` literals.

### Added
- `repo.json` canonical source for repository owner/name/branch/homepage.
- `scripts/version_site.cjs` exposes `readRepo()` alongside
  `readReleaseVersion()` for site rendering.
- `bago provider` CLI subcommand for provider inspection and patching:
  `list`, `show`, `set-key`, `unset-key`, `set-default-model`,
  `unset-default-model`, `enable`, `disable`.
- Backwards-compatible aliases `provider set-fallback` and
  `provider remove-fallback` that resolve against `default_provider`.
- `tests/test_cmd_provider.py` covering the new subcommand surface.

### Fixed
- `bago_core/version.py` now works when executed standalone (wheel/source
  compatibility shim inserts package root into `sys.path`).
- `versions.json` history entry for 4.7.0 now uses full semver `4.7.0`.
- `tests/test_evidence_integrity.py` now inserts repo root into
  `sys.path` so it can run from source.

### Documentation
- `MANUAL.md` documents `bago provider` usage and the singular/plural
  split: CLI uses `provider`, REPL uses `/providers`.

## [4.7.0] - 2026-06-21

### Added
- BAGO Code Forge 3B: deterministic generate→validate→repair pipeline that
  drives the local model (default `llama3.2:3b`) and keeps BAGO as the
  authority on accept/reject.
  - `bago_core/codegen/` adds `task_classifier`, `task_compiler`,
    `context_builder`, `patch_parser`, `repair_loop`, `code_verdict`,
    `evidence_builder`.
  - `bago_core/validation/` adds `language_adapter`,
    `validation_pipeline`, `validation_result` and a `python_adapter` that
    runs the seven canonical gates (syntax → imports → formatter → lint →
    typecheck → security → tests).
  - `bago_core/execution/` adds `process_runner`, `staging_workspace` and
    `atomic_patch` so the runtime can apply a patch atomically with a
    pre-image snapshot under `.bago/snapshots/` and roll back on failure.
- Code Forge operates in four modes — `SAFE` (no apply),
  `STAGED` (staging only), `APPLY` (apply if validation passes) and
  `AUTONOMOUS` (apply unattended). The mode is decided per request by
  the validator, never by the model.
- `EvidenceBundle` (frozen dataclass, JSON-safe) carries the task id,
  CodeVerdict, per-attempt history, validation summary and a list of
  `LIMIT_*` limitation codes so external auditors can replay the decision.
- `bundle_to_audit_record` adapts an `EvidenceBundle` to the audit-bundle
  record format expected by `scripts/package_audit_bundle.py`.

### Tests
- 121 Code Forge tests across 11 files (classifier, compiler, context,
  parser, repair loop, code verdict, evidence builder, validation,
  python adapter, execution, codegen integration).
- Full suite: 238 passed, 8 skipped, 16 subtests passed.

### Notes
- The pre-existing failure in `test_security_release.py` is unrelated to
  Code Forge (caused by the deferred `.bago/` cleanup that will archive
  `BAGO.pyproj`); it is excluded from the new suite totals.

## [4.6.4] - 2026-06-18

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
- Runtime version drift closed: new sessions, supervisor, orchestrator and E2E now report 4.7.0.
- Supervisor and Windows release-job helpers no longer open transient PowerShell windows during background checks.
- Release notes no longer embed stale self-referential artifact hashes; final digests live in external sidecars and GitHub release metadata.

### Changed
- `Pipelines`, `Ruta`, `Registry`, `Instalaciones`, `Releases`, `Trabajos`, `Sesiones`, `Sistema`, `Salud`, `Auditoría`, and `Métricas` follow a single visual grammar.
- `project` accepts `--root` consistently across `init`, `status`, `link`, and `analyze`.
- Release verification uses explicit artifact paths or `BAGO_RELEASE_ASSETS`.

### Published artifacts
- `BAGO-Installation-Manager-4.7.0-win-x64.exe`
- `bago-v4.7.0.zip`
- `bago-user-v4.7.0.zip`
- `bago-audit-v4.7.0.zip`
- `bago-release-assets-v4.7.0.zip`

### Notes
- The audit bundle is published with `*.sha256`, `*.manifest.json`, `*.snapshot.json`, and `*.report.md` sidecars.
- The user bundle intentionally excludes local model weights and caches.
- The audit bundle intentionally excludes local model weights, caches, credentials, and release/dist/build outputs.

