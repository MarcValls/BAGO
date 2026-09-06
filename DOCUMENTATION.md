# BAGO Documentation Status

This is the entrypoint that separates current operating documentation from
historical records. The canonical product version is
[`release_version.txt`](release_version.txt); derived files and historical
records do not override it.

## Current operating documentation

| Area | Source |
|---|---|
| Product, installation, commands, and current candidate status | [README.md](README.md) |
| Technical documentation index | [backend/docs/README.md](backend/docs/README.md) |
| Architecture | [backend/docs/ARCHITECTURE.md](backend/docs/ARCHITECTURE.md) |
| Security posture | [backend/docs/SECURITY.md](backend/docs/SECURITY.md) |
| Claims and executable evidence | [backend/docs/CLAIMS.md](backend/docs/CLAIMS.md) and [backend/docs/TESTING.md](backend/docs/TESTING.md) |
| Module and MVP boundaries | [backend/docs/MODULES.md](backend/docs/MODULES.md) and [backend/docs/MVP.md](backend/docs/MVP.md) |
| Release candidate notes | [releases/RELEASE_NOTES_4.10.0.md](releases/RELEASE_NOTES_4.10.0.md) |
| Frontend product contract | [frontend/PRODUCT.md](frontend/PRODUCT.md) and [frontend/CONTEXT_PRODUCT_CONTRACT.md](frontend/CONTEXT_PRODUCT_CONTRACT.md) |

## Historical and evidence records

The following preserve dated facts and must not be used as current operating
instructions:

- Root `RELEASE_4.8.2_MANIFEST.md`, `RELEASE_NOTES_4.8.3.md`,
  `RELEASE_NOTES_4.8.4.md`, `RELEASE_NOTES_4.8.7.md`,
  `RELEASE_PUBLICATION_SUMMARY.md`, `TASK_COMPLETION_SUMMARY.md`,
  `CODEX_SESSION_RESUME.md`, `INSTALLER-DELIVERY.md`, and `RELEASE-READY.md`.
- `backend/MANUAL.md`, which documents the 4.9.0 release surface.
- `backend/docs/audit/`, `backend/docs/TECH_DEBT_*.md`, and
  `backend/docs/migration-sprints-current.md`.
- `frontend/README_REFACTOR_BAGO_UI_v2*.md`,
  `frontend/VALIDACION_*.md`, `frontend/RELEASE_CANDIDATE_REPORT.md`, and
  `frontend/DEPENDENCY_REBUILD_REPORT.md`.
- Historical 4.9.0 material in `releases/`; start from
  [releases/INDEX.md](releases/INDEX.md) to distinguish it from the current
  candidate notes.
- `.bago/audits/`, which is immutable candidate-bound evidence rather than
  operating documentation.

## Documentation maintenance rules

1. Resolve the version from `release_version.txt`; `versions.json` is a
   derived compatibility index.
2. Treat backend-confirmed state, contracts, and candidate-bound receipts as
   authoritative over UI or prose summaries.
3. Preserve historical reports rather than rewriting their factual record.
4. Update this index when adding or retiring an operating document.
