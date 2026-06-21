# BAGO Migration Sprint Plan

Status: completed
Depends on: `BAGO_MIGRATE_TARGET.md`
Applies to: `C:\Users\AMTEC_Terminal_1º\bago_fw`

This plan turns the 25 migration rows into implementation slices.
Sprint 1 is already implemented in the current tree; the remaining sprints are the backlog.

## Sprint Map

| Sprint | Rows | Focus | Status |
|---|---|---|---|
| 0 | 8 | Freeze truth and block snapshot leakage | done |
| 1 | 1, 18, 19, 22 | Entrypoints and runtime selection | done |
| 2 | 2, 3, 4, 5, 20, 25 | Layout, registry, workflows, state, manifest | done |
| 3 | 6, 7, 9, 10, 11, 12, 13, 15, 16 | Knowledge, recovered assets, and contracts | done |
| 4 | 8, 14, 17, 21, 23, 24 | Cleanup, external surfaces, and CI gates | done |
| 5 | final | Validation, sync, and release proof | done |

## Sprint 0 - Freeze And Triage

Rows covered:
- 8

Deliverables:
- Lock the source and target paths.
- Treat the migration map as a snapshot artifact, not live truth.
- Mark snapshot claims as historical unless they have proof in the current tree.

Exit criteria:
- The migration target is represented as a tracked plan.
- No doc in the current tree reuses the snapshot paths as if they were active roots.

## Sprint 1 - Entrypoints And Session Contract

Rows covered:
- 1
- 18
- 19
- 22

Deliverables:
- Canonical bootstrap and agent entry contract.
- Dev-root resolution for the editable tree.
- Runtime selection for the CLI opener.
- Wrapper behavior that prefers the development tree when available.

Implemented in the current tree:
- `.bago/BOOTSTRAP.md`
- `.bago/AGENT_START.md`
- `.bago/START_AGENT.md`
- `bago.ps1`
- `electron/environment.cjs`
- `electron/runtime-service.cjs`
- `electron/main.cjs`
- `tests/test_system_prompt_bootstrap.py`
- `tests/test_no_visible_powershell.py`

Exit criteria:
- The editable tree is the default launch target for development.
- The installed runtime remains the fallback target only.

## Sprint 2 - Layout, Registry, And Truth

Rows covered:
- 2
- 3
- 4
- 5
- 20
- 25

Deliverables:
- Layout truth for the runtime tree.
- Registry truth for tools and taxonomy.
- Workflow and role inventory checks.
- State schema validation.
- Manifest truth checks.

Exit criteria:
- Counts and schemas come from probes, not snapshot text.
- Claims about layout, registry, state, and manifest are all test-backed.

## Sprint 3 - Knowledge And Asset Recovery

Rows covered:
- 6
- 7
- 9
- 10
- 11
- 12
- 13
- 15
- 16

Deliverables:
- Restore the missing assets from the hardening snapshot.
- Keep knowledge, templates, prompts, and core subdirs explicit.
- Preserve RC1-only surfaces such as MCP and extensions without flattening them away.

Exit criteria:
- Restored assets exist in the tree with tests.
- Historical examples are documented as references, not as active claims.

## Sprint 4 - Cleanup And External Surfaces

Rows covered:
- 8
- 14
- 17
- 21
- 23
- 24

Deliverables:
- No snapshot leakage in docs, tests, or runtime output.
- Monitor and supervision contracts kept explicit.
- External daemons marked deprecated when they are not stable product surfaces.
- CI gates and test coverage expanded to cover the new contract.

Exit criteria:
- Stable docs do not mention unsupported externals as product guarantees.
- The test suite blocks regressions in daemon, monitor, and CI surfaces.

## Sprint 5 - Validation, Sync, And Release Proof

Deliverables:
- Run the full validation suite.
- Sync the accepted changes to the installed runtime.
- Recompute any claims that changed during the migration.
- Publish only after evidence matches the current tree.

Exit criteria:
- The current tree and the installed runtime match for the accepted set.
- All public claims are backed by commands or evidence bundles.

Implemented in this tree:
- `python -m unittest tests.test_sprint_2_contracts tests.test_sprint_3_assets tests.test_sprint_4_surfaces tests.test_sprint_5_validation -v`
- `python tests/test_no_snapshot_leakage.py`
- `python test_e2e.py`
- `python test_security_release.py`
- `python test_ollama_live_optional.py`
- `python scripts/publish_release.py --test`
- `python scripts/verify_release.py` with a local release asset bundle at `C:\Users\AMTEC_Terminal_1º\bago-release-v4.6.4`

## Notes

- This plan is intentionally smaller than the 25-row source map: the rows remain the source of truth for implementation detail.
- The current repo already covers Sprint 1.
- The remaining work should be pulled forward only when the tests for each sprint exist first.
