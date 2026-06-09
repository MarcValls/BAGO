# BAGO Agent Release Plan

Objective: move BAGO to `release-clean` with a supervised, sprint-based agent workflow.

## Operating Rules

- Do not move to the next sprint until the current sprint gate is green.
- Do not shrink scope to make progress look easier.
- Every sprint must end with evidence: tests, command output, or a verified diff.
- If a command, page, module, or file is announced but missing, either deliver it or remove the announcement.
- If a piece does not exist, do not leave it as an indefinite pending item.
- Missing pieces must be created under user supervision.
- If a missing piece requires design choice, the agent proposes one concrete option and waits for approval before implementing.
- If a missing piece blocks a `P0`, the sprint stays open until the piece exists or the user approves an alternative.

## Operational Checklist

- [ ] Sprint 0 map and classify the current state.
- [ ] Sprint 1 close release blockers.
- [ ] Sprint 2 close security gaps.
- [ ] Sprint 3 align dependencies and build.
- [ ] Sprint 4 harden state writes.
- [ ] Sprint 5 wire QA and CI.
- [ ] Sprint 6 align product docs and UI.
- [ ] Sprint 7 harden release packaging.

## Sprint 0 - Base And Map

Duration: 0.5 day
Priority: `P0` preparation

Goal:
- Confirm the current state and freeze the work map.

Tasks:
- Inventory `bago validate`, `pytest`, `requirements.txt`, `electron/`, `.bago/api/`, `bago_core/commands/`, `bago_core/translators/`.
- Classify each finding as `P0`, `P1`, `P2`, or `P3`.
- Build a short file-touch list.
- Define the evidence needed for each finding.

Done when:
- There is a prioritized backlog.
- There is a concrete file list.
- There is a clear execution order.

Commands:

```powershell
python -m py_compile bago_core\cli.py bago_core\launcher.py .bago\api\bridge.py .bago\core\config_manager.py test_security_release.py test_e2e.py
python bago_core\cli.py validate
python -m pytest -q
```

Evidence:

- backlog entry list
- file-touch list
- failing or passing command transcript

## Sprint 1 - Release Blockers

Duration: 1 to 2 days
Priority: `P0`

Goal:
- Make validation and announced surfaces coherent.

Tasks:
- Repair `bago validate`, starting with `translators_roundtrip` and the missing `registry`.
- Deliver or remove `workspace` and `knowledge` if they do not exist.
- Fix `pytest` collection failures.
- Align help text, docs, and real commands.

Done when:
- `python bago_core\cli.py validate` passes.
- `python -m pytest -q` collects and finishes.
- No announced command fails because of a missing module.

Commands:

```powershell
python bago_core\cli.py validate
python -m pytest -q
python bago_core\cli.py evidence --test
python .bago\api\bridge.py --test
```

Evidence:

- validate output
- pytest collection output
- command transcript for announced surfaces

## Sprint 2 - Security Closure

Duration: 1 to 2 days
Priority: `P0` / `P1`

Goal:
- Remove direct paths to arbitrary code execution and unsafe mutability.

Tasks:
- Remove generic `runCommand` from Electron or replace it with typed IPC and allowlists.
- Remove the mutable bootstrap from `main` or pin it to an immutable tag/asset.
- Limit `POST /command` and the HTTP body size.
- Sanitize API error output.
- Define a browser automation policy.

Done when:
- There is no direct UI/API path to arbitrary PowerShell execution.
- The API rejects oversized bodies.
- Browser automation has explicit policy.

Commands:

```powershell
python .bago\api\bridge.py --test
python bago_core\cli.py validate
python -m pytest -q tests\test_security_release.py
```

Evidence:

- API smoke output
- security test output
- diff showing allowlist or IPC policy

## Sprint 3 - Dependencies And Build

Duration: 1 day
Priority: `P0` / `P1`

Goal:
- Make clean installs reproducible.

Tasks:
- Complete `requirements.txt` with real runtime dependencies.
- Include `pypdf`.
- Review `numpy`, `playwright`, and other optional or layer-specific imports.
- Split dependencies by layer if needed: core, UI, browser, RL, tests.
- Add bounds where future breakage is likely.

Done when:
- Runtime dependencies match real imports.
- A minimal install does not fail on missing expected packages.

Commands:

```powershell
python -m pip install -r requirements.txt
python -c "import pypdf; print(pypdf.__version__)"
python -c "import importlib.util; print('numpy', bool(importlib.util.find_spec('numpy')))"
```

Evidence:

- install output
- import checks
- updated dependency file

## Sprint 4 - State Robustness

Duration: 1 to 2 days
Priority: `P1`

Goal:
- Avoid silent corruption and write races.

Tasks:
- Convert JSON/JSONL writes to temp + rename atomic writes.
- Add locks or other exclusion where state is shared.
- Stop silencing corruption without warning.
- Add backup or quarantine behavior when needed.

Done when:
- Critical state is not written via truncate-direct patterns.
- Corruption is detected and reported.

Commands:

```powershell
python -m pytest -q tests\test_paths.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
```

Evidence:

- atomic-write diff
- state-handling tests
- corruption-handling logs

## Sprint 5 - QA And CI

Duration: 1 to 2 days
Priority: `P1`

Goal:
- Catch regressions before release.

Tasks:
- Add a minimum CI workflow for `compileall`, `pytest`, `validate`, API smoke, and CLI smoke.
- Add timeouts and cleanup for processes/threads in tests.
- Add smoke tests for every top-level announced command.
- Separate optional integration tests from mandatory gates.

Done when:
- CI blocks the key regressions.
- Tests do not hang on unmanaged resources.

Commands:

```powershell
python -m py_compile bago_core\cli.py bago_core\launcher.py .bago\api\bridge.py
python -m pytest -q
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
```

Evidence:

- CI workflow diff
- green local smoke output
- timeout or cleanup test proof

## Sprint 6 - Product Coherence

Duration: 1 day
Priority: `P2`

Goal:
- Align docs, versioning, and UI with reality.

Tasks:
- Remove stale version references.
- Align README, manual, and contracts with `4.5.0`.
- Reduce `innerHTML` usage where possible.
- Reduce duplication between `manager` and `landing/manager`.

Done when:
- Claims, docs, and runtime match.

Commands:

```powershell
python bago_core\cli.py validate
python -m pytest -q
cd ui-react
npm run build
```

Evidence:

- docs diff
- version alignment diff
- UI build output

## Sprint 7 - Release Hardening

Duration: 1 day
Priority: `P2`

Goal:
- Make distribution reproducible and auditable.

Tasks:
- Add SBOM or dependency audit in CI.
- Require signed or immutable release assets for final release.
- Add clean-install tests for new environments.
- Verify live state, credentials, and caches are not packaged.

Done when:
- The release is reproducible, auditable, and excludes live state.

Commands:

```powershell
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
python scripts\package_v4.py --test
python scripts\package_v4.py
```

Evidence:

- package test output
- release artifact manifest
- SBOM or dependency audit output

## Execution Order

1. Sprint 0
2. Sprint 1
3. Sprint 2
4. Sprint 3
5. Sprint 4
6. Sprint 5
7. Sprint 6
8. Sprint 7

## Stop Conditions

- If a sprint gate fails, fix it in the same sprint.
- If a missing piece blocks a `P0`, stop and create it under user supervision.
- If a design choice is needed, propose one concrete option and wait for approval.
- If a piece does not exist, never leave it as an indefinite pending item.

## Sprint Dashboard

Use this as the execution view:

1. Check the sprint checklist.
2. Run the listed commands.
3. Record the evidence.
4. Mark the sprint as done only when all gate outputs are green.
5. Move to the next sprint only after the current one is green.
