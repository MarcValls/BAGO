# BAGO — Agent context for Pi 0.84.2+

This is the BAGO monorepo. BAGO is a local AI control plane: the session is the source of truth; providers and models are interchangeable execution engines.

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

## BAGOx behavior overlay (PROPOSED_RC)

This is a scoped projection of the Codex fragment from
`BAGOx-BEHAVIOR-PACKAGE-v1.2-RC1`, anchored to the external
`MANIFEST.sha256` SHA-256
`239534797e0f5ba0957aef5513508c350494ebc59185b6c1372d7bd2ae22387c`.
It adopts only stable agent-behavior rules; package templates, schemas,
hooks, and BAGOx-only state mechanisms remain outside this repository until
separately adopted. BAGOx behavior rules do not themselves modify BAGO canon
or state: BAGO changes require explicit repository operations and BAGO-native
evidence. This overlay does not override explicit user instructions,
repository-local authority, or verified BAGO state.

### Resolve state before material work

- Never use conversational memory as repository authority.
- Resolve repository identity, branch, HEAD, worktree state, canonical version,
  active decisions, conflicts, and current evidence before material mutations
  OR claims about repository state.
- Resolve remote state before claims about GitHub or any remote: run
  `git fetch origin` and verify `origin/main`, PR merge status, and branch
  state against the actual remote. Local tracking refs are last-known, not
  current.
- `.bago/` state files are local projections of last-known state, not remote
  authority. Reconcile with remote before any claim about PRs, merges, or
  GitHub state. Internal coherence of a local file is not evidence of
  current remote truth.
- Resolve the canonical product version from `release_version.txt`; package
  manifests and runtime output are derived checks and never belong in
  `AGENTS.md` as mutable values.
- Treat current-state artifacts as reproducible projections of their
  authorities, not as independent truth.
- On state drift, rehydrate and replan; never reset, restore, or revert merely
  to match remembered state.
- If a tool needed to verify state is unavailable, find an alternative path
  (shell, API, fetch). Tool failure is never permission to skip verification.

### Authority, review, and evidence

- One critical property has one authority; other occurrences are derived.
- Preserve superseded decisions as history.
- `PREPARED`, `EXECUTED`, `VERIFIED`, and `VALIDATED` are distinct states.
- `CRIT_PASS` does not imply `CANON`.
- Reviewers do not silently modify code. Fix agents do not certify their own
  changes. Verification agents do not modify during certification.
- Findings require rule, observed behavior, violation, impact, evidence,
  proposed correction, and verification method.
- Bind claims and receipts to the current candidate. Evidence from another
  candidate is stale unless applicability is explicitly proved.
- Do not claim complete test success when relevant suites were skipped or
  omitted.
