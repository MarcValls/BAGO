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
| Interactive architecture overview | [docs/architecture/README.md](docs/architecture/README.md) |
| Historical release records | [docs/archive/releases/README.md](docs/archive/releases/README.md) and [local archived payloads](releases/archive/README.md) |
| Architecture | [backend/docs/ARCHITECTURE.md](backend/docs/ARCHITECTURE.md) |
| Security posture | [backend/docs/SECURITY.md](backend/docs/SECURITY.md) |
| Claims and executable evidence | [backend/docs/CLAIMS.md](backend/docs/CLAIMS.md) and [backend/docs/TESTING.md](backend/docs/TESTING.md) |
| Module and MVP boundaries | [backend/docs/MODULES.md](backend/docs/MODULES.md) and [backend/docs/MVP.md](backend/docs/MVP.md) |
| Historical release notes (4.10.0) | [docs/archive/releases/RELEASE_NOTES_4.10.0.md](docs/archive/releases/RELEASE_NOTES_4.10.0.md) |
| Historical UI reports | [docs/archive/frontend-ui/README.md](docs/archive/frontend-ui/README.md) |
| Frontend product contract | [frontend/PRODUCT.md](frontend/PRODUCT.md) and [frontend/CONTEXT_PRODUCT_CONTRACT.md](frontend/CONTEXT_PRODUCT_CONTRACT.md) |
| Repository engineering protocol (proposed) | [backend/docs/repository-engineering/README.md](backend/docs/repository-engineering/README.md) |

## Historical and evidence records

The following preserve dated facts and must not be used as current operating
instructions:

- Historical release artifacts live under `docs/archive/releases/` and retain
  their versioned names. The root directory is reserved for current entrypoints.
- `TASK_COMPLETION_SUMMARY.md` and `CODEX_SESSION_RESUME.md` remain historical
  working records, not current operating instructions.
- `backend/MANUAL.md`, which documents the 4.9.0 release surface.
- `backend/docs/audit/`, `backend/docs/TECH_DEBT_*.md`, and
  `backend/docs/migration-sprints-current.md`.
- UI refactor and validation reports were moved to
  `docs/archive/frontend-ui/`; they describe dated proposals and builds, not
  the current frontend product contract.
- Versioned payloads under `releases/archive/v*/` are local historical
  artifacts; [releases/INDEX.md](releases/INDEX.md) is the current release
  index and `docs/archive/releases/` holds historical records.
- `.bago/audits/`, which is immutable candidate-bound evidence rather than
  operating documentation.

## Documentation maintenance rules

1. Resolve the version from `release_version.txt`; `versions.json` is a
   derived compatibility index.
2. Treat backend-confirmed state, contracts, and candidate-bound receipts as
   authoritative over UI or prose summaries.
3. Preserve historical reports rather than rewriting their factual record.
4. Treat the generated block in `README.md` and
   `backend/contracts/readme_projection.v1.json` as projections, not
   independent authorities. Regenerate them with `npm run docs:sync`; CI
   enforces `npm run docs:check` semantics through
   `generate_readme_projection.py --check`.
5. Update this index when adding or retiring an operating document.
