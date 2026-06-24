# Changelog

## [4.8.0] - 2026-06-24

### Bumped by bump_version.py

## [4.7] - 2026-06-21

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
- Runtime version drift closed: new sessions, supervisor, orchestrator and E2E now report 4.7.
- Supervisor and Windows release-job helpers no longer open transient PowerShell windows during background checks.
- Release notes no longer embed stale self-referential artifact hashes; final digests live in external sidecars and GitHub release metadata.

### Changed
- `Pipelines`, `Ruta`, `Registry`, `Instalaciones`, `Releases`, `Trabajos`, `Sesiones`, `Sistema`, `Salud`, `Auditoría`, and `Métricas` follow a single visual grammar.
- `project` accepts `--root` consistently across `init`, `status`, `link`, and `analyze`.
- Release verification uses explicit artifact paths or `BAGO_RELEASE_ASSETS`.

### Published artifacts
- `BAGO-Installation-Manager-4.7-win-x64.exe`
- `bago-v4.7.zip`
- `bago-user-v4.7.zip`
- `bago-audit-v4.7.zip`
- `bago-release-assets-v4.7.zip`

### Notes
- The audit bundle is published with `*.sha256`, `*.manifest.json`, `*.snapshot.json`, and `*.report.md` sidecars.
- The user bundle intentionally excludes local model weights and caches.
- The audit bundle intentionally excludes local model weights, caches, credentials, and release/dist/build outputs.

