# BAGO 15-point governed remediation

This package turns the 15 remediation fronts into one governed Codex orchestration built on the existing `.codex/bago-workpack` roles.

## Contract

Before mutation, the supervisor validates both governing inputs:

1. `remediation-plan.json` must match schema `1.1`, keep the non-relaxable safety policy, contain exactly the ordered F01-F15 fronts, safe task/front identifiers, valid priorities and non-empty acceptance criteria.
2. The plan-selected tasks must resolve exactly once in `.codex/bago-workpack/manifest.json`. The implementation task must be a scoped `workspace-write` BAGO worker; the verification task must be `read-only`, require explicit target context, and use `bago_final_verifier`. They cannot be the same task.

Task IDs remain plan authority; the supervisor does not hard-code them, and the verification report filename is derived from the plan-selected verification task.

The user-provided `RunId` is retained as audit metadata, but every filesystem/branch/workpack identifier uses a sanitized `safeRunId`. The safe value cannot be `.`/`..`, is length-bounded, and ledger directories are additionally prefixed with `run-`. This prevents path separators, traversal-like segments, reserved-name collisions and excessive physical paths from escaping or corrupting workpack report locations, especially on Windows.

For every front:

1. Fetch current `origin/main`, validate the base ref format, and verify that `origin` is `MarcValls/BAGO`.
2. Create a unique isolated Git worktree and remediation branch without deleting prior evidence.
3. Run the plan-selected implementation task with the front objective and acceptance criteria, using a sanitized physical run ID.
4. Commit the resulting candidate and bind it to an exact SHA.
5. Run the plan-selected verification task independently and read-only against that exact candidate, also using a sanitized physical run ID.
6. Preserve the existing workpack verdict contract: the report begins with exactly `PASS`, `FAIL`, or `BLOCKED`.
7. Require a second strict machine contract with exactly one `BAGO_CANDIDATE_SHA: <sha>` and one mapped verdict: `PASS -> PREVERIFIED`, `FAIL -> FAILED`, `BLOCKED -> BLOCKED`.
8. Stop unless both verdict layers agree on `PASS/PREVERIFIED` for the exact candidate and verification leaves HEAD/worktree unchanged.
9. Push the candidate and create a PR.
10. Poll GitHub Actions by exact candidate SHA until every workflow declared by `execution_policy.required_pr_workflows` exists and its latest run completes successfully.
11. Run the complete PR-check query as an additional gate so non-required checks can still block integration.
12. Re-check that the PR head still equals the preverified SHA.
13. Record `VERIFIED` only after independent preverification plus required successful workflow runs and a green complete PR-check set for the exact SHA.
14. Request squash merge with `--match-head-commit <candidate-sha>` so a head change cannot win a check/merge race.
15. Poll GitHub until the PR is actually reported `MERGED`; only then record `VALIDATED`.
16. Record every transition in a JSONL ledger stored below the repository Git directory, outside tracked worktree state.

The process is deliberately fail-closed. Automatic closure means "close when demonstrated", never "force success".

## Non-relaxable execution policy

Schema `1.1` requires:

- `mode = sequential_dependency_safe`
- `close_only_on_verified = true`
- `auto_merge_only_after_ci = true`
- `self_certification_forbidden = true`
- `failure_policy = stop_and_block`
- `evidence_required = true`

Changing any of these values without introducing a new supported schema blocks the run before repository mutation.

## Plan governance

`remediation-plan.json` is the execution authority for the orchestration scope. It declares the base branch, implementation/verification task IDs, required PR workflows and ordered F01-F15 acceptance contracts. An unsupported schema, missing/blank required property, empty workflow list, unsafe task/front ID, duplicate/out-of-order front, invalid priority or empty acceptance criterion stops before repository mutation.

The supervisor resolves task IDs and the expected verifier report filename from this validated plan, then cross-checks those selected roles against the workpack manifest. This prevents silent plan/runner drift while preserving separation of duties.

## Required PR workflows

The current plan requires all of these workflow identities before a candidate can become `VERIFIED`:

- `Canonical CI`
- `Validate Expected`
- `njsscan sarif`

The supervisor polls `gh run list` for the exact candidate SHA and `pull_request` event. This removes the registration race where a newly-created PR temporarily has no visible check entries. For each required workflow, the newest matching run must reach `completed/success`; missing, pending, cancelled, failed or otherwise non-successful required runs cannot promote the candidate. Once these workflow gates pass, the supervisor also requires the complete PR check set to pass.

## State semantics

- `PREPARED`: front selected and base resolved.
- `EXECUTED`: worker produced a committed candidate.
- `PREVERIFIED`: independent read-only verifier returned the workpack `PASS` verdict and the candidate-bound machine verdict for all non-deferred criteria. GitHub CI/merge gates have not yet been claimed.
- `PR_OPEN`: candidate was pushed and a PR exists.
- `VERIFIED`: exact candidate has independent preverification, explicit successful evidence from every required PR workflow, and a green complete PR-check set.
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

The blocked run's ledger, branch and worktree are preserved for inspection rather than silently destroyed. Both the original audit `RunId` and its sanitized physical form are written into the ledger.

## Safety / authority invariants

- Plan safety flags cannot be relaxed inside schema 1.1.
- Plan-selected task roles are cross-checked against the workpack manifest; the verifier must remain `read-only` and `bago_final_verifier`.
- Plan and supervisor cannot silently disagree about task IDs or verifier report naming.
- Raw user `RunId` never reaches a branch, worktree, workpack report directory or report lookup path.
- Workers cannot certify their own changes.
- Free-text mentions of words such as `VERIFIED` are not authority; the required workpack verdict and strict machine verdict must agree.
- Verification evidence from another SHA is stale by default.
- Candidate HEAD/worktree mutation during verification invalidates the pass.
- A moved PR head invalidates preverification.
- A newly-created PR cannot fail open merely because checks have not registered yet.
- Generic green checks are insufficient if a required workflow is absent or not successful.
- The merge request is atomically pinned to the verified candidate SHA.
- Green CI alone does not replace independent preverification.
- A successful merge command alone does not imply `VALIDATED`; GitHub must report `MERGED`.
- Prior blocked branches/worktrees are not force-deleted.
- P0/P1/P2/P3 are processed sequentially in dependency-safe plan order.
- Broad fronts may return `BLOCKED` with a smaller decomposition rather than forcing an unsafe mega-PR.

## Validation coverage

`backend/tests/test_remediation_orchestrator_contract.py` falsifies missing/ambiguous verdicts, verdict disagreement, duplicate verdicts, candidate-SHA mismatch, plan/policy/task-role drift, raw-RunId filesystem leakage, required-workflow omission, the initial PR-check registration race, missing SHA-pinned merge behavior and critical supervisor gate regressions on Canonical CI's Windows/PowerShell environment.

## Files

- `remediation-plan.json`: authoritative orchestration scope, execution gates and acceptance criteria for F01-F15.
- `Run-Remediation.ps1`: plan-governed supervisor.
- `VerificationVerdict.psm1`: strict workpack + candidate-bound verdict parser.
- `.git/bago-remediation-runs/run-<safeRunId>/ledger.jsonl`: local lifecycle/evidence index; it is not remote authority by itself.
