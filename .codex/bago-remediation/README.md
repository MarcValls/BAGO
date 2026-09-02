# BAGO 15-point governed remediation

This package turns the 15 remediation fronts into one governed Codex orchestration built on the existing `.codex/bago-workpack` roles.

## Contract

For every front:

1. Fetch current `origin/main` and verify that `origin` is `MarcValls/BAGO`.
2. Create a unique isolated Git worktree and remediation branch without deleting prior evidence.
3. Run `20-implement-approved-pr` with the front objective and acceptance criteria.
4. Commit the resulting candidate and bind it to an exact SHA.
5. Run `22-verify-change` independently and read-only against that exact candidate.
6. Require the strict machine contract `BAGO_CANDIDATE_SHA: <sha>` plus exactly one `BAGO_VERDICT: PREVERIFIED|BLOCKED|FAILED` line.
7. Stop unless the verifier returns `PREVERIFIED` for the exact candidate and leaves both HEAD and the worktree unchanged.
8. Push the candidate and create a PR.
9. Wait for GitHub PR checks and re-check that the PR head still equals the preverified SHA.
10. Record `VERIFIED` only after independent preverification plus green PR checks for that exact SHA.
11. Request squash merge only when all gates remain green, then poll GitHub until the PR is actually reported `MERGED`.
12. Record `VALIDATED` only after the remote merge is confirmed.
13. Record every transition in a JSONL ledger stored below the repository Git directory, outside tracked worktree state.

The process is deliberately fail-closed. Automatic closure means "close when demonstrated", never "force success".

## State semantics

- `PREPARED`: front selected and base resolved.
- `EXECUTED`: worker produced a committed candidate.
- `PREVERIFIED`: independent read-only verifier accepted all non-deferred criteria for the exact candidate SHA. GitHub CI/merge gates have not yet been claimed.
- `PR_OPEN`: candidate was pushed and a PR exists.
- `VERIFIED`: exact candidate has independent preverification and green GitHub PR checks.
- `VALIDATED`: GitHub additionally confirms that the verified PR is merged.
- `BLOCKED`: a required invariant, test, evidence item, tool, review, CI or merge-confirmation gate failed or is missing. The orchestration stops immediately.

Acceptance criteria that explicitly require GitHub CI or confirmed merge are deferred external gates during `PREVERIFIED`; they are owned by the supervisor afterward and cannot be claimed by the verifier in advance.

## Prerequisites

- clean BAGO worktree;
- `origin` pointing to `MarcValls/BAGO`;
- `git` authenticated for the repository;
- GitHub CLI `gh` authenticated for `MarcValls/BAGO`;
- Codex CLI available in PATH and compatible with `.codex/bago-workpack/Run.ps1`;
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

With `-NoMerge`, a front may reach `VERIFIED` but never `VALIDATED`.

## Resume after a blocked front

Use a new `RunId` and select the blocked front:

```powershell
powershell -ExecutionPolicy Bypass -File .codex\bago-remediation\Run-Remediation.ps1 -RepoRoot . -RunId retry-001 -StartAt F06
```

The blocked run's ledger, branch and worktree are preserved for inspection rather than silently destroyed.

## Safety / authority invariants

- Workers cannot certify their own changes.
- Verifiers run through the existing read-only verification task.
- Free-text mentions of words such as `VERIFIED` are not authority; only the strict machine verdict contract is parsed.
- Verification evidence from another SHA is stale by default.
- Candidate HEAD/worktree mutation during verification invalidates the pass.
- A moved PR head invalidates preverification.
- Green CI alone does not replace independent preverification.
- A successful merge command alone does not imply `VALIDATED`; GitHub must report `MERGED`.
- Prior branches/worktrees are not force-deleted on failure.
- P0/P1/P2/P3 are processed sequentially in dependency-safe plan order.
- Broad fronts may return `BLOCKED` with a smaller decomposition rather than forcing an unsafe mega-PR.

## Validation coverage

`backend/tests/test_remediation_orchestrator_contract.py` falsifies ambiguous verdicts, duplicate verdicts, candidate-SHA mismatch and critical supervisor gate regressions on Canonical CI's Windows/PowerShell environment.

## Files

- `remediation-plan.json`: authoritative orchestration scope and acceptance criteria for F01-F15.
- `Run-Remediation.ps1`: supervisor.
- `VerificationVerdict.psm1`: strict candidate-bound verdict parser.
- `.git/bago-remediation-runs/<RunId>/ledger.jsonl`: local lifecycle/evidence index; it is not remote authority by itself.
