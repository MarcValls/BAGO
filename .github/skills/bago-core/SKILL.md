---
name: bago-core
description: Apply BAGO context architecture, project isolation, evidence-first execution and final-state verification. Use for non-trivial work, continuation, conflicts, implementation, verification, validation or closure-sensitive repository engineering.
---

# BAGO Core for GitHub Copilot

This skill is an operational layer. It does not create authority. Resolve authority from the current user request and the active repository.

## Entry

For this repository, Copilot continuity state lives under `.gabo/copilot/`. It must remain separate from BAGO framework code such as `backend/.bago/`.

1. Resolve the Git root, branch, HEAD and `git status`.
2. If installed, run `python .gabo/copilot/bin/bago.py status`.
3. Read only the needed portions of `.gabo/copilot/context/PROJECT_CONTEXT.md`, `.gabo/copilot/state/PROJECT_STATE.json`, `.gabo/copilot/runtime/ACTIVE_HANDOFF.md`, `.gabo/copilot/decisions/DECISIONS.md`, and `.gabo/copilot/conflicts/CONFLICTS.md`.
4. Identify requested product, authorized effects and closure criterion.
5. Separate canon, verified state, inference, proposal and experimental material.
6. Detect material conflicts before editing.

If `.gabo/copilot/` is absent, use the same reasoning discipline without claiming the runtime exists.

## BAGO-specific repository authority

For material BAGO changes, inspect relevant live sources before acting: `README.md`, `backend/docs/ARCHITECTURE.md`, `backend/docs/SECURITY.md`, `backend/docs/CLAIMS.md`, `backend/docs/TESTING.md`, plus the actual code and tests being changed. Never treat the generation baseline SHA in this pack as current state.

## Execution

- Inspect before editing.
- Keep changes inside explicitly authorized scope.
- Preserve unrelated pre-existing changes.
- Do not mutate canonical architecture/governance merely to make implementation fit.
- Make the smallest defensible change.
- `EXECUTED` means an action actually happened; it does not mean verified.
- Do not commit, push, merge, release, publish, create repositories or change remote settings unless the user explicitly authorizes that external effect.

Useful lifecycle commands when the runtime is installed:

`python .gabo/copilot/bin/bago.py state PREPARED --note "Artifact constructed"`

`python .gabo/copilot/bin/bago.py state EXECUTED --note "Change applied"`

## Verification

Use repository-defined checks, not invented checks. Prefer binding final evidence through:

`python .gabo/copilot/bin/bago.py verify -- <real check command>`

A successful check verifies only its actual scope and exact final repository fingerprint. Later edits stale that evidence. For high-impact closure, delegate an independent read-only pass to `bago-final-verifier`.

## Validation

`VALIDATED` requires explicit acceptance criteria, all PASS, and fresh verification. A green test suite alone is not automatic validation.

## Handoff

For partial long work, preserve only the minimum reconstructable state:

`python .gabo/copilot/bin/bago.py handoff --set "Current state, blocker, and next authorized action"`

## Output contract

For non-trivial work report: requested operation; artifacts changed/produced; actions actually executed; checks actually run; evidence scope; lifecycle state; remaining blockers/risks. Never fabricate tool output, memory retrieval, repository state or successful checks.
