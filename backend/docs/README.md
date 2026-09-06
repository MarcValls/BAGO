# BAGO Docs Index

This is the canonical entrypoint for BAGO documentation.

## Read first

- [Architecture](ARCHITECTURE.md)
- [System overview](system-overview.md)
- [Modules inventory](MODULES.md)
- [Live surfaces](live-surfaces.md)
- [UI canonical contract](ui-canonical-contract.md)
- [Testing](TESTING.md)
- [Security](SECURITY.md)

## Architecture and boundaries

- [Backend architecture](backend-architecture.md)
- [Layers](LAYERS.md)
- [Resolver architecture](resolver-architecture.md)
- [MVP boundary](MVP.md)
- [Centralization contract](centralization-contract.md)
- [Distribution contract](distribution-contract.md)
- [Support matrix](support-matrix.md)
- [State taxonomy](state-taxonomy.md)

## Runtime and modules

- [Commands reference](COMMANDS.md)
- [Live surfaces](live-surfaces.md)
- [RL engine](rl-engine.md)
- [Reflexive interpreter](reflexive-interpreter.md)
- [Node control spec](node-control-spec.md)

## Contracts

- [Contracts README](contracts/README.md)
- [Engineering contract](contracts/bago_v4_engineering_contract.md)
- [Evidence contract](contracts/bago_v4_evidence_contract.md)
- [Governance contract](contracts/bago_v4_governance_contract.md)
- [Knowledge contract](contracts/bago_v4_knowledge_contract.md)
- [Pipeline contract](contracts/bago_v4_pipeline_contract.md)
- [REPL contract](contracts/bago_v4_repl_contract.md)
- [Runtime contract](contracts/bago_v4_runtime_contract.json)
- [Resolver contract](contracts/resolver_contract.json)
- [Workspace seed contract](contracts/workspace_seed_contract.md)
- [Workspace seed tests](contracts/workspace_seed_tests.md)

## Audits

- [Audit index](audit/README.md)
- [Baseline audit](audit/bago-4-8-baseline.md)
- [Fix plan](audit/bago-4-8-fix-plan.md)
- [Workspace authority map](audit/bago-4-8-workspace-authority-map.md)
- [Pending integrations](audit/bago-pending-integrations-2026-07-17.md)
- [State audit](audit/bago-state-audit-2026-07-17.md)

## Evidence

- [Evidence index](evidence/README.md)
- [UI shell current](evidence/ui_shell_current/report.md)

## UI and visual design

- [UI system visual grammar](ui-system-visual-grammar.md)
- [UI cognitive load review](ui-cognitive-load-review.md)
- [BAGO landing UI evidence](evidence/ui_shell_current/report.md)

## Traceability and claims

- [Claims](CLAIMS.md)
- [Traceability](TRACEABILITY.md)

## Historical records

- [Migration sprints (completed record)](migration-sprints-current.md)
- [Audit reports](audit/README.md)
- [Technical-debt snapshots](TECH_DEBT_LARGE_FILES.md) and [marker inventory](TECH_DEBT_MARKERS.md)

These records preserve dated evidence. They do not define the current release
candidate, runtime state, or operating procedure.

## Notes

- [Naming convention](naming.md)
- New canonical docs use lowercase kebab-case filenames in English.
- Existing uppercase core documents remain canonical until a governed,
  repository-wide rename updates every reference and external consumer.
- Experimental or ad hoc material should live under `tests_local/`, `docs/archive/` if present, or a clearly named audit subfolder.
