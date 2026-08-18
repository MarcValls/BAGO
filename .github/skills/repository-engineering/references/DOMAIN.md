# DOMAIN — repository.engineering v0.1.1

## 1. IDENTITY

domain_id: `repository.engineering`
name: `REPOSITORY ENGINEERING`
version: `0.1.1`
status: `PROPOSED`
kernel_contract_version: `1.0`
kernel_release: `RC1`
domain_spec_version: `1.2`
owner_scope: `null`
purpose: Define a specialized domain for inspecting, auditing, planning, modifying, verifying and governing changes in software repositories, while preserving explicit separation between repository canon, authoritative repository state, executed actions, evidence, project context and runtime capabilities.

The domain solves a functional problem: repository work routinely mixes intent, repository policy, current checkout state, generated changes, verification results and project decisions. This domain provides repository-specific operations and closure criteria so those planes remain distinguishable and traceable.

It may serve multiple independent software projects and repositories through explicit project-domain bindings. It does not own those projects or repositories.

## 2. IN_SCOPE

- Resolve a repository baseline for an explicitly identified repository/worktree.
- Inspect repository structure, tracked/untracked state, revisions, refs and configured engineering entry points when runtime capability exists.
- Audit repository implementation against repository-local requirements, declared architecture, build/test/lint/typecheck contracts and change intent.
- Prepare repository change plans without writing files.
- Apply authorized changes to repository content when a writable runtime binding exists.
- Compute and inspect change sets/diffs against a captured baseline.
- Execute repository-declared verification commands when command execution is available and authorized.
- Distinguish pre-existing failures from failures introduced by the current change when evidence permits.
- Produce verification reports scoped to an exact revision/change set/environment.
- Prepare or perform repository-local governance/canon changes only when mutation intent and authority are explicit.
- Contain or roll back changes introduced by the current operation when technically possible and authorized.
- Produce handoffs when required capability, authority, context or specialist competence is missing.
- Maintain explicit many-to-many bindings between this domain and projects without sharing project canon by association.

## 3. OUT_OF_SCOPE

- Redefining KERNEL GLOBAL, DOMAIN SPEC, global evidence policy, global state taxonomy, global routing or global memory policy.
- Owning, instantiating or absorbing a project or repository into the domain.
- Treating all software tasks as repository engineering tasks.
- Assuming a filesystem, shell, Git, GitHub, GitLab, CI service, package manager, compiler or test runner exists without a runtime binding or equivalent evidence.
- Pushing, merging, force-pushing, tagging, releasing, deleting branches, rewriting history or performing other remote/destructive VCS effects unless the current operation explicitly requests them, authority is sufficient and the runtime exposes the capability.
- Security vulnerability assessment requiring a dedicated security specialization, except repository-engineering observations needed to route or block safely.
- Product-management, legal, licensing-policy or organizational approval decisions beyond repository-specific evidence and handoff.
- Treating README text, issue text, memory or recent files as canon unless repository authority explicitly designates them.
- Claiming execution, verification, validation or conformance without the required evidence and criterion.

## 4. VOCABULARY

### Repository
Definition: A version-controlled or otherwise governed software source tree selected as the object of an operation.
Ambiguity: A repository may have multiple worktrees, clones, remotes or submodules; identity must be resolved for the current operation.
Relation to kernel: Specialized object; it is not a project by definition.

### Repository baseline
Definition: The captured starting point used to interpret later changes, normally including repository identity, worktree/root, revision/ref when available, relevant status and scope.
Ambiguity: A dirty worktree means baseline includes both committed and pre-existing uncommitted state.
Relation to kernel: Specialized AUTHORITATIVE_STATE/EVIDENCE snapshot; validity is scope-bound.

### Change set
Definition: The bounded set of repository modifications attributable to an operation, expressed as file-level or VCS-level deltas against a baseline.
Ambiguity: A working tree may contain unrelated changes; attribution must not be inferred merely because a diff exists.
Relation to kernel: Specialized execution product/evidence.

### Repository canon
Definition: Repository-local decisions or artifacts explicitly designated by applicable project/repository governance as canonical for architecture, interfaces, workflows, policies or other controlled engineering facts.
Ambiguity: Not every documentation file is canonical.
Relation to kernel: Specialized CANONICAL source; distinct from domain canon.

### Domain canon
Definition: The accepted normative contract of `repository.engineering` itself.
Ambiguity: In v0.1.1 the proposed files are candidate canon, not accepted canon.
Relation to kernel: Domain-local CANONICAL source after explicit acceptance.

### Verification run
Definition: An execution of one or more checks against an exact or adequately identified repository state/change set, with outputs and exit/result evidence.
Ambiguity: A successful build does not automatically verify unrelated acceptance criteria.
Relation to kernel: Specialized evidence leading at most to VERIFIED for the declared scope.

### Repository governance change
Definition: A change that mutates repository-local canonical engineering rules, designated architectural contracts, ownership rules or other repository governance sources.
Ambiguity: A code edit may implement canon without mutating canon.
Relation to kernel: Potential CANON_MUTATION in the target repository context; requires explicit mutation intent and authority.

### Pre-existing change/failure
Definition: Repository modification or failing condition shown to exist before the current operation's attributable change set.
Ambiguity: Requires a baseline or equivalent evidence.
Relation to kernel: Specialized evidence classification used to avoid false attribution.

### Runtime binding
Definition: Concrete mechanism exposed by the current runtime for a semantic repository capability, such as reading files, inspecting VCS state or executing commands.
Ambiguity: Documentation naming a tool does not prove availability.
Relation to kernel: RUNTIME_BINDING, never universal capability.

## 5. ENTITIES

### REPOSITORY_CONTEXT
Identity: repository root/worktree plus repository identity sufficient for the operation.
Attributes: root, VCS kind if known, active revision/ref if available, remote identity if relevant, project binding if any, observed timestamp/snapshot id.
Source of truth: runtime inspection plus repository/project authoritative sources.
Lifecycle: UNRESOLVED -> RESOLVED -> STALE when material repository state changes.

### BASELINE
Identity: immutable operation-local baseline id.
Attributes: repository context, revision/ref, worktree status, pre-existing changes, scoped files, environment metadata where relevant.
Source of truth: captured inspection evidence.
Lifecycle: PREPARED -> EXECUTED when captured -> VERIFIED when evidence is sufficient for declared scope -> STALE when invalidated.

### CHANGE_SET
Identity: operation id plus delta against baseline.
Attributes: affected paths, additions/deletions, semantic purpose, attribution, generated/non-generated classification, governance impact.
Source of truth: diff/file evidence against baseline.
Lifecycle: PROPOSED -> PREPARED -> EXECUTED -> VERIFIED -> VALIDATED or CONTAINED/ROLLED_BACK when applicable.

### VERIFICATION_RUN
Identity: run id tied to repository/change-set scope.
Attributes: command/check, environment, revision/change set, result, exit code/status, logs, timestamp.
Source of truth: runtime execution evidence or authoritative CI result.
Lifecycle: PREPARED -> EXECUTED -> VERIFIED; VALIDATED only when it satisfies a declared product criterion.

### REPOSITORY_CANON_SOURCE
Identity: repository artifact explicitly designated canonical by applicable authority.
Attributes: path/identifier, version/revision, scope, mutation authority, status.
Source of truth: project/repository governance.
Lifecycle: PROPOSED/CANONICAL -> SUPERSEDED/DEPRECATED/CONFLICT as governed by its owner.

### PROJECT_BINDING
Identity: explicit association between a project and `repository.engineering`.
Attributes: purpose, transferable context, non-transferable context, authority, activation/deactivation conditions.
Source of truth: binding record or project/domain governance.
Lifecycle: PROPOSED -> ACTIVE -> DEACTIVATED/SUPERSEDED.

### RUNTIME_BINDING
Identity: semantic operation plus concrete runtime mechanism.
Attributes: binding name, dependency, availability condition, executable condition, scope, limitations.
Source of truth: current runtime capability exposure or direct evidence.
Lifecycle: UNRESOLVED -> AVAILABLE -> EXECUTABLE -> VERIFIED_FOR_SCOPE; may become UNAVAILABLE.

## 6. SOURCES

CANONICAL:
- Accepted `repository.engineering` domain canon, when explicitly approved.
- Target repository/project artifacts explicitly designated canonical for the current repository scope.

AUTHORITATIVE_STATE:
- Current VCS/worktree state observed from the active repository runtime.
- Current project/repository state source explicitly designated by the applicable project binding.
- Authoritative CI/check state tied to an exact revision when verification depends on remote execution.

EVIDENCE:
- File contents and hashes captured for the scoped operation.
- Repository status and revision/ref outputs.
- Diffs/change sets against a captured baseline.
- Command invocation, exit status and logs.
- Build/test/lint/typecheck outputs.
- CI job/check results tied to exact revision/change set.
- Commit/revision identifiers produced or observed by the operation.

REFERENCE:
- README files, non-canonical documentation, code comments, issues, PR descriptions, tickets and external technical references unless explicitly designated otherwise.

MEMORY:
- Confirmed stable repository conventions and recurring workflow preferences that do not replace current repository state or canon.

INFERENCE:
- Inferred architecture intent, likely fault cause, likely affected modules, proposed remediation or estimated impact not confirmed by authoritative source/evidence.

EXPERIMENTAL:
- Spike changes, draft patches, temporary branches/worktrees, proof-of-concept commands or hypotheses explicitly treated as experimental.

UNRESOLVED:
- Repository identity/root when not yet inspected.
- Active revision/ref or dirty state when not yet observed.
- Applicable repository canon when no authoritative designation is available.
- Required runtime capability/tool availability before runtime inspection.
- Mutation authority for a repository governance change when not explicit.

## 7. LOCAL AUTHORITY AND VALIDITY

Canonical sources:
- Domain canon: accepted `DOMAIN_CANON.md` and explicitly linked accepted domain records.
- Target repository canon: only sources designated canonical by the applicable repository/project authority.

Mutation authority:
- Domain canon: actor or governance process explicitly authorized to approve/change `repository.engineering` canon.
- Target repository canon: authority declared by the target repository/project governance; unresolved authority blocks canonical mutation.

State authority:
- `DOMAIN_STATE.md` for this domain proposal.
- For target repositories, current runtime-observed VCS/worktree state and any explicitly designated project state source for non-VCS facts.

Validity/supersession rules:
- A repository-state observation is valid only for its captured repository identity, revision/ref, worktree and verification scope.
- A moved HEAD/ref, changed working tree or changed relevant environment can invalidate prior verification evidence.
- A CI result is authoritative only for the revision/check configuration to which it is tied.
- `SUPERSEDED`, `DEPRECATED` and `CONFLICT` records remain traceable and are not silently deleted.
- A copied or newly timestamped old rule does not regain authority merely by recency.
- `TASK_OVERRIDE` changes only the current operation unless explicit mutation intent and authority establish a repository/domain CANON_MUTATION.

Equivalent-source tie-breaker:
- Recency may break ties only after authority, applicability, explicit validity/supersession and evidentiary strength are equivalent.

Conflict escalation:
- Unresolved source/state/version/authority/project-domain/interdomain conflicts that can materially change the repository result are returned to the kernel or applicable project governance authority.

## 8. CANON

Canonical location: `DOMAIN_CANON.md` after explicit acceptance. In v0.1.1 it is a candidate canonical location and its content remains PROPOSED.

Mutation procedure:
1. Identify whether the requested change is domain canon, target repository canon, or ordinary implementation state.
2. Require explicit mutation intent for canon.
3. Resolve the applicable mutation authority.
4. Capture current canonical version and relevant evidence.
5. Prepare the mutation and impact record.
6. Execute only through an available authorized capability.
7. Preserve prior version as SUPERSEDED/DEPRECATED/CONFLICT as applicable.
8. Verify the mutation against the exact source/revision.
9. Validate only against the explicit acceptance criterion and required acceptance authority.

Explicit mutation intent required: `true`
Versioning: `MAJOR.MINOR.PATCH` for domain canon. Target repository canon follows the repository's own valid scheme.
Supersession record: `DOMAIN_CANON.md#supersession-history` for domain canon; target repository uses its designated history/record.

## 9. STATE

Current state source: `DOMAIN_STATE.md`
Local additional states: `STALE`, `CONTAINED`, `ROLLED_BACK` are local descriptors mapped to global state records rather than replacements for global taxonomy.
Mapping to global states:
- proposal/design decision -> PROPOSED
- constructed plan/patch not applied -> PREPARED
- repository read/write/command action actually performed -> EXECUTED
- claim matched by sufficient repository evidence -> VERIFIED with scope
- verified product meeting acceptance criterion -> VALIDATED
- required source/capability/authority absent -> BLOCKED
- previous rule/version not current -> SUPERSEDED or DEPRECATED
- incompatible unresolved repository facts -> CONFLICT
Verification scopes:
- `VERIFIED / REPOSITORY_BASELINE`
- `VERIFIED / AUDIT_SCOPE`
- `VERIFIED / CHANGE_SET`
- `VERIFIED / STATIC_CHECKS`
- `VERIFIED / BUILD`
- `VERIFIED / TESTS`
- `VERIFIED / CI`
- `VERIFIED / GOVERNANCE_MUTATION`
- combinations must enumerate included checks; none imply broader validation.
History location: `DOMAIN_STATE.md#history` for domain lifecycle; each target repository retains its own history independently.

## 10. OPERATIONS

Detailed inventory is normative for this proposal in `DOMAIN_OPERATIONS.md`.

Operations:
- `repo.resolve_baseline`
- `repo.audit`
- `repo.plan_change`
- `repo.apply_change`
- `repo.verify_change`
- `repo.govern_change`
- `repo.contain_or_rollback`
- `repo.prepare_handoff`

Each material operation defines inputs, preconditions, sources, capabilities, procedure, allowed/forbidden effects, evidence, product, acceptance criterion, closure criterion and failure/handoff behavior.

## 11. CAPABILITIES AND RUNTIME BINDINGS

### CAPABILITY repo.read
purpose: Read scoped repository files and metadata.
dependency: runtime filesystem/repository connector.
availability_condition: runtime exposes read access to the identified repository scope.
executable_condition: requested paths are within authorized repository scope.
verification_evidence: actual file/metadata payload or equivalent read evidence.
fallback: PREPARED analysis from supplied material only, or BLOCKED when current state is required.

### CAPABILITY repo.enumerate
purpose: Enumerate repository tree/paths needed for scope resolution.
dependency: runtime filesystem/repository connector.
availability_condition: enumeration capability is exposed.
executable_condition: repository root is resolved and readable.
verification_evidence: returned path inventory.
fallback: use explicitly supplied paths; otherwise BLOCKED if inventory is material.

### CAPABILITY vcs.inspect
purpose: Resolve revision/ref/status/diff information.
dependency: VCS-capable runtime binding appropriate to the repository.
availability_condition: VCS metadata and inspection mechanism are available.
executable_condition: repository identity and VCS scope are resolved.
verification_evidence: actual VCS state output or authoritative connector payload.
fallback: file-only baseline with reduced verification scope, explicitly declared.

### CAPABILITY repo.write
purpose: Apply authorized file changes.
dependency: writable filesystem/repository connector.
availability_condition: runtime exposes write/patch capability.
executable_condition: baseline, target paths and scope are resolved; conflicting pre-existing changes are contained or explicitly accepted.
verification_evidence: post-write file/diff evidence.
fallback: produce a PREPARED patch/change specification without claiming execution.

### CAPABILITY command.execute
purpose: Execute repository-declared engineering commands.
dependency: command-capable runtime.
availability_condition: execution mechanism is exposed and command is permitted.
executable_condition: command, cwd, environment assumptions and expected effect are resolved.
verification_evidence: invocation plus exit/result output.
fallback: provide PREPARED verification commands and mark actual verification NOT_RUN/BLOCKED as appropriate.

### CAPABILITY vcs.mutate
purpose: Perform requested VCS mutations such as commit/branch operations.
dependency: VCS mutation runtime binding.
availability_condition: concrete mutation capability is exposed.
executable_condition: explicit requested effect, sufficient authority, exact repository scope and safe preconditions are resolved.
verification_evidence: resulting refs/revision/status evidence.
fallback: PREPARED instructions or handoff; never simulate mutation.

### CAPABILITY remote.check.read
purpose: Read remote CI/check status tied to a revision.
dependency: remote repository/CI connector or API binding.
availability_condition: connector/API is exposed and authorized.
executable_condition: repository remote identity and exact revision are resolved.
verification_evidence: authoritative check payload tied to revision.
fallback: local verification only with narrower scope.

### RUNTIME_BINDING
No universal concrete binding is declared in v0.1.1. See `DOMAIN_RUNTIME_BINDINGS.md`. A concrete binding registry is resolved per runtime before execution.

## 12. PROCEDURES

See `DOMAIN_PROCEDURES.md` for reproducible procedures:
- `PROC-BASELINE`
- `PROC-AUDIT`
- `PROC-PLAN`
- `PROC-APPLY`
- `PROC-VERIFY`
- `PROC-GOVERN`
- `PROC-CONTAIN`
- `PROC-HANDOFF`

## 13. EVIDENCE SPECIALIZATION

Required classes:
- repository identity evidence;
- baseline/revision evidence;
- pre-existing-change evidence when worktree is not clean;
- change-set evidence for writes;
- execution evidence for commands/actions;
- check result evidence tied to scope;
- governance authority and before/after canonical source evidence for canon mutation.

Sufficiency criteria:
- Evidence must identify the repository/change scope closely enough that the claim cannot be mistaken for another revision/worktree.
- Verification of a change requires both attribution of the change set and evidence from the declared checks.
- Validation additionally requires the product's acceptance criterion to be met.

Traceability: `claim -> repository source/action -> captured evidence -> scoped verification -> conclusion`.
Verification scope: explicitly enumerated; no successful check expands to unexecuted checks.
Retention/location: target project/repository evidence location when defined; otherwise operation output/handoff must identify evidence references. This domain does not impose a universal storage path.

## 14. PRODUCTS

### repository_baseline_report
purpose: Establish the exact starting repository state for subsequent attribution.
form: structured report.
minimum_requirements: repository identity/root, observed state, revision/ref when available, pre-existing changes, scope, unresolved items.
evidence: inspection outputs/payloads.
acceptance_criterion: sufficient to distinguish current operation changes from known pre-existing repository state for the declared scope.
maximum_state_without_external_acceptance: VERIFIED / REPOSITORY_BASELINE.

### repository_audit_report
purpose: Record evidence-backed repository findings and prioritized remediation.
form: structured findings report.
minimum_requirements: scope, sources, findings, severity/impact rationale, evidence, uncertainty, pre-existing/current attribution when relevant, next action.
evidence: file/state/check evidence.
acceptance_criterion: every material finding is traceable and unsupported conclusions are explicitly inference/unresolved.
maximum_state_without_external_acceptance: VERIFIED / AUDIT_SCOPE.

### repository_change_plan
purpose: Define intended change before execution.
form: ordered plan with target files/effects/checks/rollback.
minimum_requirements: baseline reference, objective, affected scope, planned effects, forbidden effects, verification plan, conflict handling.
evidence: source analysis supporting the plan.
acceptance_criterion: plan is executable in principle without relying on undeclared capabilities or authority.
maximum_state_without_external_acceptance: PREPARED.

### repository_change_set
purpose: Represent actual applied repository modifications.
form: diff/patch plus change summary.
minimum_requirements: baseline reference, attributable changes, affected paths, governance impact classification, unrelated changes preserved.
evidence: post-write diff/file evidence.
acceptance_criterion: actual changes match authorized intent and do not silently include unrelated modifications.
maximum_state_without_external_acceptance: VERIFIED / CHANGE_SET, but not VALIDATED without acceptance criterion checks.

### repository_verification_report
purpose: Determine what has actually been checked and with what result.
form: scoped verification matrix/report.
minimum_requirements: exact change/revision, checks executed, checks not run, outputs/results, pre-existing failures, introduced failures, scope conclusion.
evidence: command/CI outputs.
acceptance_criterion: report can reconstruct each verification claim from executed evidence and does not equate partial checks with complete validation.
maximum_state_without_external_acceptance: VERIFIED for enumerated scopes.

### repository_governance_change_record
purpose: Record an authorized mutation to repository-local canon/governance.
form: before/after change record plus supersession metadata.
minimum_requirements: explicit mutation intent, authority, canonical source, prior/new version or revision, cause, effect, supersession state, verification evidence.
evidence: authority evidence plus before/after source evidence.
acceptance_criterion: mutation is authorized, traceable and preserves prior canon history.
maximum_state_without_external_acceptance: VERIFIED / GOVERNANCE_MUTATION; VALIDATED only if repository governance requires and supplies acceptance.

### repository_containment_report
purpose: Show containment/rollback of changes attributable to the operation.
form: scoped restoration report.
minimum_requirements: affected change set, action performed, preserved unrelated state, resulting repository status, residual risks.
evidence: before/change/after diffs or equivalent state evidence.
acceptance_criterion: attributable effects are contained/restored without claiming removal of unrelated pre-existing state.
maximum_state_without_external_acceptance: VERIFIED / CONTAINMENT_SCOPE.

### repository_handoff_packet
purpose: Transfer minimum repository context when another authority/domain/runtime is required.
form: kernel-compatible handoff plus repository-specific payload.
minimum_requirements: repository identity, baseline/revision, pending operation, affected scope, available evidence, unresolved item/capability, conflicts, next action.
evidence: references to captured source/state/evidence.
acceptance_criterion: recipient can continue without importing unrelated project history or assuming unavailable capabilities.
maximum_state_without_external_acceptance: PREPARED.

## 15. ROUTING

Positive signals:
- explicit request to inspect, audit, patch, refactor, fix, test, build, review or govern a software repository/codebase;
- request to compare repository implementation with repository-local architecture/contracts;
- request to determine current branch/revision/diff/status as part of an engineering task;
- request to apply and verify repository changes;
- request to prepare a repository-safe handoff or rollback.

Negative signals:
- pure conceptual programming question with no repository object/state;
- general product planning without repository implementation work;
- content editing unrelated to source repositories;
- security, legal or operational tasks whose primary competence belongs elsewhere and do not require repository-engineering action;
- request to change kernel/domain architecture itself unless the object is this domain package and routing explicitly selects domain design/governance rather than repository engineering.

Ambiguous cases:
- reviewing code pasted in chat without a repository context: domain may assist as reference-only review, but no repository-state claim is allowed;
- Git/GitHub question that is only usage education: activate only if repository-specific state/action is material;
- dependency vulnerability request: repository engineering may establish files/build context, then handoff to a security specialization for vulnerability judgment.

Activation preconditions:
- kernel selects this domain as applicable;
- repository object or repository-specific artifact is identified enough for the requested operation;
- required authority/capability is resolved before material effects.

Deactivation:
- requested product no longer requires repository-specific state/operations;
- required object is outside authorized repository scope;
- another specialist domain becomes primary and only a handoff is needed.

Handoff targets:
- kernel for final routing/conflict resolution;
- applicable project governance authority for unresolved repository canon/state authority;
- applicable specialist domain when repository engineering is supporting rather than primary;
- runtime/operator when a required concrete binding is unavailable.

## 16. INTERDOMAIN RELATIONS

No concrete interdomain relation is declared in v0.1.1 because no other domain id is required to complete this proposal.

Relation policy:
- relations are explicit and operation-specific;
- transferable context is limited to repository identity, scoped state, relevant evidence, pending operation and conflicts;
- repository/domain/project canon is never inherited by association;
- handoff returns minimal context, not full project history.

## 17. PROJECT-DOMAIN BINDINGS

No concrete project binding is active in v0.1.1.

Binding model:
- relation is many-to-many;
- a project may use this domain for one repository task and other domains for other tasks;
- this domain may serve multiple projects without sharing their canon, state or evidence;
- each binding must declare purpose, transferable/non-transferable context, authority, activation and deactivation.

A repository/project used later to test this domain remains an external application context. It does not become an instance, subobject or property of `repository.engineering`.

## 18. MEMORY SPECIALIZATION

Allowed candidates:
- stable, confirmed repository naming conventions;
- stable recurring build/test workflow preferences if not critical to correctness;
- stable repository relationship metadata that improves routing, subject to refresh rules.

Forbidden local items:
- current branch, HEAD, worktree status, exact version, current test result, current CI status;
- repository canon or project canon as memory-only truth;
- execution evidence or proof of a completed write/command;
- mutation authority unless refreshed from an authoritative source when material.

Requires source refresh:
- current repository state before any material write/verification;
- current canonical engineering contract before an audit/change that depends on it;
- current runtime binding availability before execution;
- current project binding/authority before repository governance mutation.

Expiry/refresh condition:
- any material repository state change invalidates cached state for affected scope;
- current-state memory is advisory only and must be refreshed before material claims.

## 19. CONFLICTS

Known conflicts:
- none established in the abstract design.

Conflict types supported:
- repository source conflict;
- revision/state conflict;
- repository canon version conflict;
- mutation authority conflict;
- dirty-worktree attribution conflict;
- project-domain binding conflict;
- interdomain responsibility conflict;
- runtime capability claim vs actual availability conflict.

Impact:
- material conflicts can block writes, governance mutation, verification or validation.

Local resolution authority:
- repository-specific conflicts may be resolved only by sources/authorities valid for that repository scope.

Escalation condition:
- escalate to kernel/project governance when local evidence cannot resolve a conflict that may change the result or authorized effect.

## 20. LOCAL RESTRICTIONS

- Do not write before resolving repository identity, target scope and an operation baseline sufficient for attribution.
- Preserve unrelated pre-existing worktree changes; do not overwrite or silently include them in the current change set.
- If pre-existing changes overlap target paths and safe attribution/isolation cannot be established, block or handoff rather than overwrite.
- Do not perform destructive/history-rewriting/remote VCS effects unless explicitly requested, authorized and executable through a real binding.
- Do not modify repository tests, checks or acceptance artifacts merely to obtain a passing result unless such modification is part of the authorized objective and is reported as a material change.
- Do not mutate repository canon/governance through an ordinary implementation request; require explicit mutation intent and authority.
- Tie verification claims to the exact revision/change set/environment actually checked.
- Report checks not executed separately from checks passed.
- Separate pre-existing failures from introduced failures when baseline evidence permits; otherwise mark attribution UNRESOLVED.
- Generated or derived files should be changed through their repository-designated generator/process when such requirement is authoritative and the capability exists; otherwise prepare/handoff rather than invent a generator result.
- Restrict file/system effects to the authorized repository scope and any explicitly authorized supporting paths.

## 21. VERSIONING

Scheme: `MAJOR.MINOR.PATCH`
Current version: `0.1.1`
Previous version: `0.1.0` — SUPERSEDED
Kernel compatibility: `KERNEL GLOBAL contract 1.0 / RC1`, `DOMAIN SPEC 1.2`
Change record:
- 0.1.0 SUPERSEDED — initial real-domain design, replaced by the v0.1.1 documentary correction; conformance NOT_RUN.
- 0.1.1 PROPOSED / package PREPARED — normalized repository capability ids; folded diff inspection into `vcs.inspect`; aligned operation/manifest capability alternatives without promoting optional capabilities; added `AUDIT_SCOPE`; defined 15-file package boundary and supersession traceability; conformance NOT_RUN.

## 22. SEMANTIC INTERFACE

identify(request): Determine whether a repository-specific engineering operation is requested and identify the target repository/artifact without auto-activating universally.
get_scope(): Return IN_SCOPE/OUT_OF_SCOPE and operation-specific authorized repository scope.
get_local_authority(): Return domain canon authority plus target repository/project canon and state authority for the operation.
get_validity_rules(): Return baseline/revision/worktree/check validity and supersession rules.
get_state_source(): Return `DOMAIN_STATE.md` for domain state and runtime/project authoritative source for target repository state.
get_canon(): Return accepted domain canon and target repository canonical sources separately; proposed/unresolved sources are not promoted.
get_sources(): Return classified repository/domain sources including UNRESOLVED.
get_operations(): Return the eight operation definitions.
get_constraints(): Return local repository restrictions plus references to superior constraints without redefining them.
get_evidence_requirements(operation): Return repository identity/baseline/change/execution/check/governance evidence required for that operation.
get_products(): Return the product inventory in section 14.
get_acceptance_criterion(product): Return the product-specific criterion and maximum state without external acceptance.
get_routing_signals(): Return positive/negative/ambiguous signals and deactivation/handoff conditions.
get_project_bindings(): Return explicit bindings only; currently empty in v0.1.1.
get_runtime_dependencies(): Return semantic capabilities plus any concrete bindings resolved for the current runtime; no universal concrete binding is assumed.
handoff(target): Produce kernel-compatible minimum handoff enriched with repository identity, baseline/revision, affected scope and evidence references.

Optional when capability exists:
execute(operation): Execute only after required runtime bindings, authority and preconditions resolve.
verify(result, scope): Match claims against repository evidence for the exact declared verification scope.
validate(result): Determine whether the verified product meets its explicit acceptance criterion; does not imply domain conformance.

## 23. CONFORMANCE

kernel_contract_version: `1.0`
kernel_release: `RC1`
spec_version: `1.2`
test_version: `1.2`
result: `NOT_RUN`
last_test: `null`
evidence: `[]`

DOMAIN CONFORMANCE TEST v1.2 is intentionally not executed during this documentary correction step.
