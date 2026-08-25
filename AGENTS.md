# BAGO — Agent context for Pi 0.84.2+

This is the BAGO monorepo (v4.9.0). BAGO is a local AI control plane: the session is the source of truth; providers and models are interchangeable execution engines.

## Project structure

- `backend/` — Python runtime (core, CLI, API, contracts). Exact candidate results live in gate receipts.
- `frontend/` — React + TypeScript (Vite). Exact candidate results live in gate receipts.
- `electron-viewer/` — Electron shell with automatic backend lifecycle.
- `.bago/` — BAGO runtime state, context, decisions, conflicts, and handoffs.
- `.codex/agents/` — Legacy Codex CLI agent definitions (Pi does not load them; use the `.agents/skills/` equivalents).

## Available Pi skills

- `/skill:bago-core` — lifecycle, state, evidence-first execution, closure discipline. Load this for any non-trivial or continuation work.
- `/skill:bago-auditors <mode>` — read-only audit swarm. Modes: `architecture`, `backend`, `frontend`, `contracts`, `security`, `performance`, `tests`, `hygiene`, `truth`, `code-map`.
- `/skill:bago-workers <mode>` — implementation. Modes: `implement`, `mechanical`.
- `/skill:bago-final-verifier` — independent verification pass.

## Conventions

- Read `.bago/` state before editing when it exists (`python .bago/bin/bago.py status`).
- Separate canon, verified state, inference, proposal, and experimental material.
- Mark changes `EXECUTED` until final evidence exists; do not call them `VERIFIED` or `VALIDATED` prematurely.
- Make the smallest defensible change and preserve existing architecture unless the request changes it.
- Run repository-defined checks after material edits (tests, typecheck, build).

## Pi-specific notes

- Pi 0.84.2 supports `AGENTS.override.md` for per-directory overrides and `defaultTools` configuration.
- Project trust is required to load project-local `.pi/` settings and `.agents/skills/`.
- Use `/tree`, `/fork`, `/compact`, or `/clone` to manage long-running BAGO sessions.
