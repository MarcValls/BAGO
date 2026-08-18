# DOMAIN OPERATIONS — repository.engineering

Status: PROPOSED

## repo.resolve_baseline

purpose: Capture the starting repository state required to attribute later observations and changes.
inputs: repository identifier/path/reference; requested operation scope.
preconditions: repository object identifiable; read capability if current state is required.
required_sources: repository files/metadata; VCS state when available; project binding if relevant.
required_capabilities: repo.read. optional_capabilities: repo.enumerate, vcs.inspect.
procedure: PROC-BASELINE.
allowed_effects: read/inspect only; create operation-local report/evidence.
forbidden_effects: repository writes, VCS mutation, remote mutation.
required_evidence: repository identity/root, observed revision/ref if available, worktree/status or explicit limitation, pre-existing changes relevant to scope.
product: repository_baseline_report.
acceptance_criterion: baseline distinguishes current operation scope from known pre-existing repository state sufficiently for intended follow-on work.
closure_criterion: report exists and all material unresolved baseline facts are exposed.
failure_behavior: BLOCKED when current state is essential and cannot be observed; otherwise produce reduced-scope baseline with explicit limitation.
recovery_or_handoff: request/route to a runtime with read/VCS inspection capability.

## repo.audit

purpose: Produce evidence-backed findings about repository implementation/state against declared repository requirements or engineering objective.
inputs: baseline; audit objective; scoped paths; applicable repository canon/reference.
preconditions: baseline resolved to sufficient scope; audit criteria identified.
required_sources: repository files/state; applicable canonical/reference sources; existing check results if used.
required_capabilities: repo.read. optional_capabilities: repo.enumerate; command.execute only when checks are actually requested and executable.
procedure: PROC-AUDIT.
allowed_effects: read, analyze, run non-mutating checks when authorized, produce report.
forbidden_effects: silently modify files; treat inference as canonical finding; broaden scope without disclosure.
required_evidence: source excerpts/paths, state/check evidence supporting each material finding.
product: repository_audit_report.
acceptance_criterion: every material finding has traceability and uncertainty/status is explicit.
closure_criterion: report covers declared scope and separates findings, evidence, inference, unresolved items and next actions.
failure_behavior: partial report with BLOCKED/UNRESOLVED items when critical sources cannot be resolved.
recovery_or_handoff: route missing specialist judgment or runtime evidence appropriately.

## repo.plan_change

purpose: Construct a safe, scoped repository change plan without applying it.
inputs: baseline; objective; audit/findings or direct request; constraints.
preconditions: intended effect and authorized repository scope are identified.
required_sources: relevant repository canon/state/evidence.
required_capabilities: none beyond conceptual analysis. optional_capabilities: repo.read when current state is material.
procedure: PROC-PLAN.
allowed_effects: create plan only.
forbidden_effects: repository writes or claims of execution.
required_evidence: references supporting target files, constraints and verification plan.
product: repository_change_plan.
acceptance_criterion: plan names intended effects, affected scope, verification and rollback/containment strategy without undeclared dependencies.
closure_criterion: plan is PREPARED and execution dependencies/unresolved conflicts are explicit.
failure_behavior: BLOCKED if objective or canonical constraint is materially unresolved.
recovery_or_handoff: resolve source/authority/runtime dependency before apply.

## repo.apply_change

purpose: Apply an authorized implementation change to repository content.
inputs: accepted/current change plan or explicit scoped change objective; baseline.
preconditions: repository identity and target paths resolved; repo.write executable; conflicting pre-existing changes isolated/accepted; ordinary code change vs governance mutation classified.
required_sources: baseline; relevant repository canon/state; change objective.
required_capabilities: repo.write. optional_capabilities: repo.read, vcs.inspect for attribution as needed.
procedure: PROC-APPLY.
allowed_effects: scoped file modifications required by objective.
forbidden_effects: unrelated file changes; implicit repository-canon mutation; destructive/remote VCS effects not explicitly requested; overwrite of unrelated pre-existing work.
required_evidence: before/after or diff evidence tied to baseline; affected paths; write result.
product: repository_change_set.
acceptance_criterion: actual change set matches authorized intent and excludes unrelated modifications.
closure_criterion: change is EXECUTED and attributable; VERIFIED only after diff/file evidence confirms exact change set.
failure_behavior: stop/contain on unexpected overlap, out-of-scope effect or failed write; do not claim completed change.
recovery_or_handoff: contain own partial effects when safe or handoff with exact residual state.

## repo.verify_change

purpose: Execute and interpret repository-specific checks for an exact change set/revision.
inputs: baseline/change set; verification plan; repository-declared check commands/config.
preconditions: exact verification target resolved; each required execution binding available or explicitly not run.
required_sources: repository check definitions; current change/revision; previous baseline/failure evidence when attribution matters.
required_capabilities: any_of(command.execute, remote.check.read), with at least one selected execution path. optional_capabilities: repo.read, vcs.inspect as needed.
procedure: PROC-VERIFY.
allowed_effects: execute authorized verification commands; produce logs/report; incidental generated outputs only when declared by repository process and contained.
forbidden_effects: claim unexecuted checks passed; reinterpret partial success as full validation; hide pre-existing failures.
required_evidence: command/check identity, target revision/change set, results, outputs, exit/status, checks not run, attribution evidence.
product: repository_verification_report.
acceptance_criterion: each verification claim is reconstructible and scoped to executed evidence.
closure_criterion: report states EXECUTED checks and VERIFIED scopes; validation only if explicit product acceptance criterion is satisfied.
failure_behavior: report failing/blocked/not-run checks distinctly; contain unintended command side effects if material.
recovery_or_handoff: route unavailable remote/local check capability or external infrastructure issue.

## repo.govern_change

purpose: Mutate repository-local engineering canon/governance under explicit intent and authority.
inputs: explicit mutation request; target canonical source; proposed change; current canonical version.
preconditions: CANON_MUTATION intent explicit; mutation authority resolved; canonical source identified; write capability available; supersession method known.
required_sources: target repository canon; authority source; applicable history/version record.
required_capabilities: repo.read, repo.write. optional_capabilities: vcs.mutate if explicitly required for the governance workflow.
procedure: PROC-GOVERN.
allowed_effects: authorized change to identified repository canonical/governance sources plus required history/version record.
forbidden_effects: treating ordinary implementation request as governance mutation; deleting prior canon history; using domain authority as repository authority.
required_evidence: authority, before/after canonical source, version/supersession metadata, resulting repository state.
product: repository_governance_change_record.
acceptance_criterion: mutation is explicit, authorized, versioned/traceable and preserves prior material state.
closure_criterion: EXECUTED only after actual mutation; VERIFIED / GOVERNANCE_MUTATION only after source evidence; VALIDATED only when repository acceptance criterion is met.
failure_behavior: BLOCKED if authority/canon/version is unresolved; otherwise prepare proposed mutation without applying.
recovery_or_handoff: project/repository governance authority.

## repo.contain_or_rollback

purpose: Contain or reverse effects attributable to the current operation while preserving unrelated repository state.
inputs: baseline; current change set; containment/rollback objective.
preconditions: attributable effects identifiable; rollback effect authorized; required write/VCS capability available.
required_sources: baseline, change set, current repository state.
required_capabilities: any_of(repo.write, vcs.mutate), with at least one selected safe containment/rollback method.
procedure: PROC-CONTAIN.
allowed_effects: reverse/disable only attributable effects within authorized scope.
forbidden_effects: reset/delete unrelated pre-existing changes; destructive history rewrite unless separately explicit and authorized.
required_evidence: before/change/after state; preserved unrelated changes; residual differences.
product: repository_containment_report.
acceptance_criterion: attributable effects are contained/restored and residual state is explicit.
closure_criterion: actual containment action EXECUTED and resulting state VERIFIED for containment scope.
failure_behavior: stop rather than broaden destructive scope; return BLOCKED/handoff with residual state.
recovery_or_handoff: runtime/operator or project authority for manual/conflicting recovery.

## repo.prepare_handoff

purpose: Package minimum repository context for continuation by kernel, project governance, another domain or runtime.
inputs: pending operation; baseline/state; evidence; conflicts; missing capability/authority.
preconditions: recipient type/reason identified.
required_sources: only sources required to continue safely.
required_capabilities: none beyond ability to produce the handoff artifact.
procedure: PROC-HANDOFF.
allowed_effects: produce handoff packet.
forbidden_effects: transfer unrelated project history; imply recipient inherits canon; claim missing action executed.
required_evidence: references to existing repository evidence.
product: repository_handoff_packet.
acceptance_criterion: packet contains minimum sufficient context and explicit unresolved item/next action.
closure_criterion: packet PREPARED and destination/reason are clear.
failure_behavior: return minimal BLOCKED record if destination cannot be resolved.
recovery_or_handoff: kernel resolves final destination.
