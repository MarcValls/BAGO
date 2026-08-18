# DOMAIN EVIDENCE — repository.engineering

Status: PROPOSED

## Specialized evidence classes

1. REPOSITORY_IDENTITY_EVIDENCE
   - repository root/worktree identity;
   - remote/repository identifier when materially required.

2. REVISION_STATE_EVIDENCE
   - HEAD/revision/ref;
   - worktree/index status;
   - relevant submodule/worktree state when in scope.

3. PREEXISTING_CHANGE_EVIDENCE
   - diff/status/file evidence captured before current write;
   - used to prevent false attribution.

4. CHANGE_SET_EVIDENCE
   - exact before/after or diff attributable to current operation;
   - path list and semantic summary.

5. EXECUTION_EVIDENCE
   - action/command actually invoked;
   - cwd/target as material;
   - exit/result status;
   - stdout/stderr/log payload as required.

6. CHECK_EVIDENCE
   - test/build/lint/typecheck/static-analysis/CI output;
   - exact revision/change set and configuration where material.

7. GOVERNANCE_AUTHORITY_EVIDENCE
   - source identifying who/what may mutate target repository canon;
   - explicit mutation intent.

8. CANON_MUTATION_EVIDENCE
   - before/after canonical content;
   - version/supersession record;
   - resulting repository revision/state.

9. CONTAINMENT_EVIDENCE
   - baseline/change/current/final delta showing attributable effects removed or contained.

## Sufficiency by operation

repo.resolve_baseline:
- identity plus observed state sufficient for the declared baseline scope.

repo.audit:
- every material finding linked to source/state/check evidence; inference separately labeled.

repo.apply_change:
- exact change set against baseline and evidence that unrelated pre-existing changes were not silently absorbed.

repo.verify_change:
- exact check invocation/result tied to exact verification target; not-run checks explicit.

repo.govern_change:
- authority + explicit mutation intent + before/after canonical source + supersession/version evidence.

repo.contain_or_rollback:
- evidence that only attributable effects were contained/restored plus residual state.

## Traceability

Required pattern:

`claim -> repository source/action -> evidence reference -> verification scope -> conclusion`

Examples of invalid traceability:

- "tests pass" based on a prior run on a different revision;
- "change is correct" based only on a clean diff;
- "architecture updated" based on code change when canonical architecture source was not mutated;
- "rollback complete" without final state evidence.

## Verification scopes

Verification statements must name one or more explicit scopes, such as:

- REPOSITORY_BASELINE
- AUDIT_SCOPE
- CHANGE_SET
- STATIC_CHECKS
- BUILD
- TESTS
- CI
- GOVERNANCE_MUTATION
- CONTAINMENT_SCOPE

No scope implies another.

## Retention/location

The domain does not mandate a universal evidence directory. Evidence location is determined by the target project/repository governance or current operation output. Handoffs must retain stable references sufficient to retrieve or reconstruct the evidence.
