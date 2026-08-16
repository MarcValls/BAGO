# DOMAIN PROCEDURES — repository.engineering

Status: PROPOSED

## PROC-BASELINE

objective: Establish a repository baseline for attribution.
activation: before material audit/write/verification when current repository state matters.
steps:
1. Resolve repository identity/root and authorized scope.
2. Resolve current revision/ref and worktree state when VCS inspection exists.
3. Detect pre-existing scoped changes and classify overlap risk.
4. Resolve applicable project binding and repository-canon sources only when operation needs them.
5. Record unavailable/unknown capabilities and state as UNRESOLVED.
6. Produce baseline report with scope and invalidation conditions.
decision_points: clean vs dirty worktree; VCS available vs unavailable; overlapping pre-existing changes; current canon required vs not required.
checks: repository identity coherent; evidence tied to same worktree/revision; no write performed.
output: repository_baseline_report.
evidence: state/ref/status/file metadata payloads.
failure: BLOCKED when missing baseline fact is material.
recovery: use narrower declared scope or handoff to capable runtime.

## PROC-AUDIT

objective: Audit repository state/implementation without confusing repository rules, state and inference.
activation: repo.audit.
steps:
1. Establish audit question and bounded scope.
2. Resolve repository canonical requirements applicable to that question.
3. Inspect implementation/state evidence.
4. Run checks only when requested/justified and executable.
5. For each finding, label requirement/source, observed fact, inference, impact and uncertainty.
6. Separate pre-existing vs current-change attribution if baseline supports it.
7. Produce prioritized remediation/next action.
decision_points: canonical requirement exists vs reference only; evidence sufficient vs unresolved; specialist handoff required.
checks: no unsupported finding promoted to fact/canon; no implicit write.
output: repository_audit_report.
evidence: source/state/check references.
failure: partial audit with explicit UNRESOLVED/BLOCKED items.
recovery: acquire authoritative source or handoff.

## PROC-PLAN

objective: Prepare an executable-in-principle repository change plan.
activation: before repo.apply_change or when user asks for plan only.
steps:
1. Link objective to baseline and applicable constraints.
2. Identify target files/components and expected semantic effect.
3. Detect governance/canon impact.
4. Identify pre-existing overlap/conflicts.
5. Declare required capabilities and runtime dependencies.
6. Define verification checks and expected acceptance criterion.
7. Define containment/rollback strategy proportionate to risk.
8. Produce plan as PREPARED.
decision_points: ordinary change vs canon mutation; direct write vs generated artifact; capability available vs unresolved.
checks: no execution claim; no undeclared destructive effect.
output: repository_change_plan.
evidence: supporting source references.
failure: BLOCKED if safe scope cannot be resolved.
recovery: narrow scope or handoff.

## PROC-APPLY

objective: Apply only the authorized repository change.
activation: repo.apply_change with executable write binding.
steps:
1. Recheck repository identity/baseline freshness before write.
2. Recheck overlapping pre-existing changes.
3. Confirm ordinary implementation vs repository-canon mutation classification.
4. Apply minimal scoped edits through a real binding.
5. Capture exact resulting diff/change set.
6. Inspect for unexpected/out-of-scope changes.
7. Stop and contain if unexpected effects appear.
8. Mark operation EXECUTED; promote to VERIFIED / CHANGE_SET only from evidence.
decision_points: stale baseline; overlap; generated file; unexpected diff; partial write.
checks: unrelated changes preserved; affected paths authorized; actual diff matches objective.
output: repository_change_set.
evidence: before/after or diff/write evidence.
failure: partial execution record plus containment/handoff.
recovery: PROC-CONTAIN or runtime/operator handoff.

## PROC-VERIFY

objective: Verify a repository change using actual repository-declared checks.
activation: repo.verify_change.
steps:
1. Resolve exact revision/change set/environment to be checked.
2. Resolve repository-declared verification commands/config and required check set.
3. Classify each check as executable, unavailable or not applicable.
4. Execute only executable checks and capture invocation/result evidence.
5. Compare failures with baseline/pre-existing evidence when available.
6. Record checks not run separately.
7. Produce scoped verification conclusion.
8. Evaluate validation criterion only if all required evidence exists.
decision_points: local vs remote check; pre-existing vs introduced failure; required check unavailable; side effects from check.
checks: no unexecuted PASS; target revision/change set exact; logs/results captured.
output: repository_verification_report.
evidence: command/CI outputs tied to target.
failure: verification report may contain FAIL/BLOCKED; do not upgrade to VALIDATED.
recovery: fix/re-run, narrow claim, or handoff.

## PROC-GOVERN

objective: Mutate repository-local canon/governance safely and traceably.
activation: repo.govern_change only with explicit CANON_MUTATION intent.
steps:
1. Identify canonical target and mutation authority.
2. Verify current canonical version/source.
3. Record cause, intended effect and compatibility impact.
4. Prepare new version/change and supersession metadata.
5. Apply through real write/VCS capability only if authorized.
6. Preserve prior material state/history.
7. Verify before/after canonical source and repository state.
8. Validate only according to repository governance acceptance criterion.
decision_points: authority sufficient; target actually canonical; version conflict; explicit acceptance required.
checks: no domain authority substituted for project authority; no silent deletion of history.
output: repository_governance_change_record.
evidence: authority + before/after + supersession record.
failure: BLOCKED; leave proposal PREPARED if useful.
recovery: project governance handoff.

## PROC-CONTAIN

objective: Reverse or isolate effects attributable to the current operation without harming unrelated work.
activation: unexpected effect, failed apply/verify side effect, explicit rollback request.
steps:
1. Reconstruct baseline and attributable change set.
2. Compare current state for new unrelated changes since baseline.
3. Select least destructive authorized containment method.
4. Apply containment only to attributable effects.
5. Capture resulting state/diff.
6. Report residual or uncontained effects.
decision_points: attribution sufficient; overlapping unrelated state; write vs VCS rollback method.
checks: unrelated pre-existing/current external changes preserved.
output: repository_containment_report.
evidence: baseline/change/current/final state.
failure: BLOCKED if safe isolation cannot be proven.
recovery: manual/runtime operator or project authority handoff.

## PROC-HANDOFF

objective: Transfer minimum context needed to continue safely.
activation: missing competence, source, authority or runtime binding.
steps:
1. Identify destination class and reason.
2. Include repository identity/baseline only to required scope.
3. Include pending operation/product and current global state.
4. Include evidence references and conflicts.
5. Include missing capability/authority and exact next action.
6. Explicitly exclude unrelated project/domain canon/history.
decision_points: destination resolved vs kernel must route.
checks: no inheritance claims; no execution claim for pending action.
output: repository_handoff_packet.
evidence: referenced existing evidence only.
failure: minimal BLOCKED packet to kernel.
recovery: kernel routing.
