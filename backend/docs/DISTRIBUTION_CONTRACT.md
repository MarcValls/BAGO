# BAGO Distribution Contract

This contract defines what may ship in the repository and in release artifacts.
Validation details live in `docs/TESTING.md` and `docs/SECURITY.md`.

## Scope

- source code
- active contracts
- docs needed to validate the current product
- release evidence

## Must Not Ship

- credentials
- runtime state
- caches
- logs
- `node_modules`
- `__pycache__`
- temporary build output
- per-user session data

## Directory Roles

| Directory | Role |
|---|---|
| `.bago/chat/` | system prompts and chat runtime source |
| `.bago/core/` | session, provider, and control runtime |
| `.bago/providers/` | provider adapters |
| `.bago/api/` | local API surface |
| `bago_core/` | CLI and compatibility runtime |
| `docs/` | active contracts, active evidence, and readable support docs |
| `docs/archive/` | historical material only |
| `scripts/` | utility scripts |
| `tests/` | executable validation |

## Release Rules

- releases must be reproducible
- release version strings must match across the tree
- installers must not execute arbitrary commands without confirmation
- release contents must match the published manifest and traceability contract

## Update Rule

If a document is only describing a historical roadmap or an old release policy, move it to `docs/archive/`.
