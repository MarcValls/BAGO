# BAGO 15-point governed remediation

This package turns the 15 remediation fronts into one governed Codex orchestration built on the existing `.codex/bago-workpack` roles.

## Contract

For every front:

1. Fetch current `origin/main` and verify that `origin` is `MarcValls/BAGO`.
2. Create a unique isolated Git worktree and remediation branch without deleting prior evidence.
3. Run `20-implement-approved-pr` with the front objective and acceptance criteria.
4. Commit the resulting candidate and bind it to an exact SHA.
5. Run `22-verify-change` independently and read-only against that exact candidate.
6. Preserve the existing workpack verdict contract: the report begins with exactly `PASS`, `FAIL`, or `BLOCKED`.
7. Require a second strict machine contract with exactly one `BAGO_CANDIDATE_SHA: <sha>` and one mapped verdict: `PASS -> PREVERIFIED`, `FAIL -> FAILED`, `BLOCKED -> BLOCKED`.
8. Stop unless both verdict layers agree on `PASS/PREVERIFIED` for the exact candidate and verification leaves HEAD/worktree unchanged.
9. Push the candidate and create a PR.
10. Wait for GitHub PR checks and re-check that the PR head still equals the preverified SHA.
11. Require explicit successful evidence for every workflow declared by `execution_policy.required_pr_workflows`; a missing workflow or skipped-only workflow cannot satisfy this gate.
12. Record `VERIFIED` only after independent preverification plus those required green PR workflows for the exact SHA.
13. Request squash merge with `--match-head-commit <candidate-sha>` so a head change cannot win a check/merge race.
14. Poll GitHub until the PR is actually reported `MERGED`; only then record `VALIDATED`.
15. Record every transition in a JSONL ledger stored below the repository Git directory, outside tracked worktree state.

The process is deliberately fail-closed. Automatic closure means "close when demonstrated", never "force success".

## Required PR workflows

`remediation-plan.json` schema 1.1 currently requires all of these workflow identities before a candidate can become `VERIFIED`:

- `Canonical CI`
- `Validate Expected`
- `njsscan sarif`

The supervisor first waits for PR checks, then enumerates them and proves that each named workflow is present, has at least one passing check, and has no failing, cancelled, or pending check. Skipped jobs may coexist with passing jobs when they are intentionally inapplicable, but skipped-only evidence is insufficient.

## State semantics

- `PREPARED`: front selected and base resolved.
- `EXECUTED`: worker produced a committed candidate.
- `PREVERIFIED`: independent read-only verifier returned the workpack `PASS` verdict and the candidate-bound machine verdict for all non-deferred criteria. GitHub CI/merge gates have not yet been claimed.
- `PR_OPEN`: candidate was pushed and a PR exists.
- `VERIFIED`: exact candidate has independent preverification and explicit green evidence from every required PR workflow.
- `VALIDATED`: GitHub additionally confirms that the SHA-pinned verified PR is merged.
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

`-NoMerge` deliberately stops after the first selected front reaches `VERIFIED`. It cannot continue to a dependent front from `origin/main` while the preceding candidate remains unmerged. Merge the verified PR, then resume with a new run at the next front.

## Resume after a blocked front

Use a new `RunId` and select the blocked front:

```powershell
powershell -ExecutionPolicy Bypass -File .codex\bago-remediation\Run-Remediation.ps1 -RepoRoot . -RunId retry-001 -StartAt F06
```

The blocked run's ledger, branch and worktree are preserved for inspection rather than silently destroyed.

## Safety / authority invariants

- Workers cannot certify their own changes.
- Verifiers run through the existing read-only verification task.
- Free-text mentions of words such as `VERIFIED` are not authority; the required workpack verdict and strict machine verdict must agree.
- Verification evidence from another SHA is stale by default.
- Candidate HEAD/worktree mutation during verification invalidates the pass.
- A moved PR head invalidates preverification.
- Generic green checks are insufficient if a required workflow is absent.
- The merge request is atomically pinned to the verified candidate SHA.
- Green CI alone does not replace independent preverification.
- A successful merge command alone does not imply `VALIDATED`; GitHub must report `MERGED`.
- Prior blocked branches/worktrees are not force-deleted.
- P0/P1/P2/P3 are processed sequentially in dependency-safe plan order.
- Broad fronts may return `BLOCKED` with a smaller decomposition rather than forcing an unsafe mega-PR.

## Validation coverage

`backend/tests/test_remediation_orchestrator_contract.py` falsifies missing/ambiguous verdicts, verdict disagreement, duplicate verdicts, candidate-SHA mismatch, required-workflow omission, missing SHA-pinned merge behavior and critical supervisor gate regressions on Canonical CI's Windows/PowerShell environment.

## Files

- `remediation-plan.json`: authoritative orchestration scope, execution gates and acceptance criteria for F01-F15.
- `Run-Remediation.ps1`: supervisor.
- `VerificationVerdict.psm1`: strict workpack + candidate-bound verdict parser.
- `.git/bago-remediation-runs/<RunId>/ledger.jsonl`: local lifecycle/evidence index; it is not remote authority by itself.
