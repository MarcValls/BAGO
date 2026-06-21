# BAGO Code Forge 3B Roadmap v4.7

Status: draft ready for implementation

Depends on:
- `docs/AUTONOMOUS_EXECUTION_CONTRACT.md`
- `docs/AUTONOMOUS_EXECUTION_PLAN.md`
- `docs/NODE_CONTROL_SPEC.md`
- `docs/CLAIMS.md`
- `docs/TESTING.md`
- `docs/BAGO_MIGRATION_SPRINTS.md`

## Goal

Turn BAGO into a deterministic code-generation factory:

`peticion humana -> contrato -> contexto minimo -> modelo local -> validacion determinista -> aplicacion transaccional -> evidence bundle`

Architectural rule:

> El modelo propone código. BAGO decide si ese código puede considerarse válido.

## Existing Building Blocks

Already present and reusable:
- `intent_engine`
- `plan_engine`
- `provider_adapter`
- `script_registry`
- `session_manager`
- `node_control_policy`
- `evidence_bundle`

Do not create a general-purpose agent framework. Add a specialized pipeline on top of these pieces.

## Non-Goals

- No free-form shell execution from the model.
- No repo-wide autonomous mutation.
- No replacement of `session_manager` or provider adapters.
- No direct application without validation.
- No unbounded repair loops.
- No new authority layer that bypasses BAGO validation.

## Sprint Map

| Sprint | Focus | Main outcome |
|---|---|---|
| 1 | Deterministic classification | BAGO classifies requests before calling any model |
| 2 | Task compiler | Human request becomes a small, verifiable contract |
| 3 | Context builder | Only authorized files, symbols, tests, and interfaces are loaded |
| 4 | Model passes and repair loop | Planner, generator, and reviewer produce bounded diffs |
| 5 | Validation and transactional apply | Syntax, lint, types, imports, security, tests, staging, rollback |
| 6 | Evidence and integration | Accepted tasks emit evidence and connect to session/runtime flow |

## Sprint 1 - Deterministic Classification

Deliverables:
- Rule-first classifier with these outcomes:
  - `explain`
  - `inspect`
  - `create_file`
  - `modify_file`
  - `fix_error`
  - `add_test`
  - `refactor_local`
  - `generate_project`
  - `unsafe_or_unsupported`
- File detection and existence checks.
- Error-aware classification when a traceback or failing test is present.
- Allowlist / denylist for paths and modes.
- Exact task contract: `docs/contracts/bago_code_forge_47_task_CODE-20260621-001.json`

Exit criteria:
- A user request can be classified without model inference.
- Unsupported requests are rejected early and explicitly.

Implementation order:
1. Define classifier inputs and outputs.
2. Add deterministic rules.
3. Add path and mode guards.
4. Add classifier tests.

## Sprint 2 - Task Compiler

Deliverables:
- Convert a human request into a compact task contract.
- Produce structured fields:
  - `task_id`
  - `operation`
  - `objective`
  - `target_files`
  - `allowed_files`
  - `forbidden_paths`
  - `constraints`
  - `acceptance`
- Validate that the contract only references approved files.

Exit criteria:
- The model receives a contract, not an open-ended prompt.
- The contract can be serialized and audited.

Implementation order:
1. Define the task schema.
2. Compile the user request into JSON.
3. Validate allowed and forbidden paths.
4. Add compiler tests.

## Sprint 3 - Minimal Context Builder

Deliverables:
- Load only:
  - the target file
  - its direct imports
  - the related tests
  - the public interfaces that cannot break
  - the closest convention examples
  - the real error, if any
- Extract symbols and references.
- Keep the context bounded and reproducible.

Exit criteria:
- The prompt stays small.
- The model sees contracts and symbols, not the whole repository.

Implementation order:
1. Read allowed files only.
2. Extract direct symbols and references.
3. Collect related tests and API surfaces.
4. Build the prompt payload.

## Sprint 4 - Model Passes And Repair Loop

Deliverables:
- Planner pass returns JSON only.
- Generator pass returns unified diff only.
- Reviewer pass checks scope, imports, signatures, and unsupported changes.
- Repair loop limited to three attempts.
- Same model instance can be reused in sequential passes.

Exit criteria:
- The model can plan, generate, and review without becoming the authority.
- Repair stops after the configured maximum.

Implementation order:
1. Planner pass.
2. Patch generation pass.
3. Reviewer pass.
4. Limited repair loop.

## Sprint 5 - Validation And Transactional Apply

Deliverables:
- Language-specific validation adapters:
  - Python: AST, compile, lint, types, tests
  - JS/TS: parse, formatter, ESLint, TypeScript, tests, build
  - PowerShell: parser, analyzer, controlled execution
  - JSON/YAML/TOML: parse and schema validation
- Staging workspace for patch application.
- Rollback if validated and applied diffs diverge.

Exit criteria:
- BAGO decides validity, not the model.
- Nothing is written to the workspace before validation passes.

Implementation order:
1. Add validation adapters.
2. Add staging workspace and hash checks.
3. Apply patch only after gates pass.
4. Add rollback and post-apply verification.

## Sprint 6 - Evidence And Integration

Deliverables:
- Evidence bundle for every accepted task.
- Claim / proof / limit record.
- Integration with `session_manager`.
- Integration with `script_registry` as a closed executor registry.
- Integration with `node_control_policy` for allowed modes.

Exit criteria:
- Every accepted codegen task leaves a durable evidence trail.
- The pipeline can be invoked from the existing BAGO session flow.

Implementation order:
1. Emit evidence bundle.
2. Record claims and limits.
3. Hook into session flow.
4. Gate autonomous mode by policy.

## Suggested Module Layout

Runtime-oriented modules:
- `bago_core/codegen/code_task.py`
- `bago_core/codegen/task_compiler.py`
- `bago_core/codegen/context_builder.py`
- `bago_core/codegen/prompt_builder.py`
- `bago_core/codegen/plan_pass.py`
- `bago_core/codegen/generation_pass.py`
- `bago_core/codegen/review_pass.py`
- `bago_core/codegen/patch_parser.py`
- `bago_core/codegen/repair_loop.py`
- `bago_core/codegen/code_verdict.py`
- `bago_core/codegen/evidence_builder.py`

Validation modules:
- `bago_core/validation/validation_pipeline.py`
- `bago_core/validation/validation_result.py`
- `bago_core/validation/adapters/python_adapter.py`
- `bago_core/validation/adapters/javascript_adapter.py`
- `bago_core/validation/adapters/typescript_adapter.py`
- `bago_core/validation/adapters/powershell_adapter.py`
- `bago_core/validation/adapters/data_adapter.py`

Execution modules:
- `bago_core/execution/staging_workspace.py`
- `bago_core/execution/atomic_patch.py`
- `bago_core/execution/process_runner.py`
- `bago_core/execution/rollback.py`

## Operational Sequence

1. Classify the request deterministically.
2. Compile the task contract.
3. Build the minimum authorized context.
4. Plan the change with the local model.
5. Generate the diff with the local model.
6. Validate the patch deterministically.
7. Repair at most three times.
8. Apply transactionally.
9. Build the evidence bundle.

## Acceptance For v4.7

- The model never decides validity.
- The model never chooses arbitrary shell commands.
- The model only proposes code or patches inside a contract.
- BAGO can validate, reject, apply, or roll back independently.
- Every accepted task has evidence.
- Small tasks can run locally with `llama3.2:3b` without expanding into a general agent runtime.
