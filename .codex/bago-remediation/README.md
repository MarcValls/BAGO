# BAGO 15-point governed remediation

This package turns the 15 remediation fronts into a single governed Codex orchestration built on the existing `.codex/bago-workpack` roles.

## Contract

For every front:

1. Fetch current `origin/main`.
2. Create an isolated Git worktree and remediation branch.
3. Run `20-implement-approved-pr` with the front objective and acceptance criteria.
4. Commit the resulting candidate.
5. Run `22-verify-change` independently and read-only against that exact candidate SHA.
6. Stop unless the verifier explicitly returns `VERIFIED` and no blocking/failure state.
7. Push the candidate and create a PR.
8. Wait for GitHub PR checks.
9. Re-check that the PR head SHA is still the independently verified candidate.
10. Squash-merge only when all gates remain green.
11. Record lifecycle state in a JSONL run ledger.

The process is deliberately fail-closed. Automatic closure means "close when demonstrated", never "force success".

## Prerequisites

- clean BAGO worktree;
- `git` authenticated for `MarcValls/BAGO`;
- GitHub CLI `gh` authenticated for `MarcValls/BAGO`;
- Codex CLI available in PATH;
- Codex CLI version compatible with `.codex/bago-workpack/Run.ps1`;
- repository CI configured and runnable.

## Dry run

```powershell
powershell -ExecutionPolicy Bypass -File .codex\bago-remediation\Run-Remediation.ps1 -RepoRoot . -DryRun
```

## Execute all 15 fronts

```powershell
powershell -ExecutionPolicy Bypass -File .codex\bago-remediation\Run-Remediation.ps1 -RepoRoot .
```

## Execute without automatic merge

```powershell
powershell -ExecutionPolicy Bypass -File .codex\bago-remediation\Run-Remediation.ps1 -RepoRoot . -NoMerge
```

## Resume from a blocked front

```powershell
powershell -ExecutionPolicy Bypass -File .codex\bago-remediation\Run-Remediation.ps1 -RepoRoot . -StartAt F06
```

Replace `F06` with the front to resume.

## States

- `PREPARED`: front selected and base resolved.
- `EXECUTED`: worker produced a committed candidate.
- `VERIFIED`: independent verifier accepted the exact candidate and CI is green, but merge was intentionally disabled.
- `VALIDATED`: independently verified candidate passed PR checks and was merged.
- `BLOCKED`: a required invariant, test, evidence item, tool, review or CI gate failed/missing. Orchestration stops immediately.

## Safety / authority invariants

- Workers cannot certify their own changes.
- Verifiers run through the existing read-only verification task.
- Evidence from another SHA is stale by default.
- A moved PR head invalidates pre-PR verification.
- No front may be marked successful merely because the implementation agent claims completion.
- P0/P1/P2/P3 are processed in dependency-safe plan order; this version intentionally prefers correctness over parallel mutation.
- Broad fronts may return `BLOCKED` with a smaller decomposition rather than forcing an unsafe mega-PR.

## Files

- `remediation-plan.json`: authoritative orchestration scope and acceptance criteria for F01-F15.
- `Run-Remediation.ps1`: supervisor.
- `runs/<RunId>/ledger.jsonl`: generated lifecycle/evidence index (local runtime output; do not treat as remote authority by itself).
