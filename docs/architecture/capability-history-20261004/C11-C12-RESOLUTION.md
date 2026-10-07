# C11 / C12 capability resolution

The initial resolution was recorded on worktree HEAD `b9b2eda8f21be16f5ade510b5f069abe09ae5387`. Historical audit artifacts remain an unchanged snapshot of that candidate. The remote-based revalidation is recorded below.

## C11 — bounded autopilot execution

- **Previous evidence:** `v4.5.0` limited `/autopilot` to 20 plan steps. The audit probe observed that current code attempted all 25 steps in its 25-step fixture.
- **Change:** `cmd_autopilot` now processes at most `AUTOPILOT_MAX_STEPS` (20). Remaining steps stay pending, the plan status becomes `stopped`, and the response states how many remain.
- **Capability result:** the 20-step bound is preserved. Oversized plans now expose incomplete work rather than appearing complete.
- **Evidence:** `backend/tests/test_capability_c11_c12.py::test_c11_autopilot_stops_at_twenty_and_keeps_remainder_pending` asserts 21 provider calls (one plan plus 20 execution calls), 20 completed steps, five pending steps, and `stopped` status for a 25-step plan.

## C12 — persistent agent lifecycle and portable agent definitions

- **Previous evidence:** `agent spawn/kill/status` used `spiral_agent`, while `agent list/run` were intercepted by the portable `agent_kit_cli` catalog. The audit could not establish that these commands addressed the same agent record.
- **Change:** `agent spawn/list/run/kill/status` now route through `spiral_agent`. Portable definitions use the explicit `agent pack list/describe/run/plan` namespace. Existing top-level `agent describe/plan` remain compatible aliases; dispatch and route remain their separate operations.
- **Capability result:** the persistent lifecycle now uses one registry and one agent identity. Portable catalog behavior remains available under its own namespace.
- **Evidence:** `backend/tests/test_capability_c11_c12.py::test_c12_persistent_agent_lifecycle_uses_one_registry` drives CLI parsing and dispatch through spawn → list → run → kill against a temporary root, checking the same registry and persisted cycle state. `test_c12_agent_pack_routes_to_portable_catalog` verifies portable catalog routing.

## Remote-based integration revalidation

The capability changes and focused test were transplanted onto remote base `5d90f9a04f262202c363cb2e34a0a32db1cd6bf7`. The earlier frozen audit report remains a historical snapshot; this section records the revalidated behavior on the integration worktree.

- Command: `python -m pytest -q -p no:cacheprovider --basetemp=.run/reconcile-20261005 backend/tests/test_capability_c11_c12.py backend/tests/test_orchestration_tools.py backend/tests/test_provider_endpoint_boundary.py`
- Result: `41 passed`.
- Mind-map JSON-to-HTML projection check: `PASS`.
- `git diff --check`: `PASS`.
- Scope: focused C11/C12 behavior and provider test-root boundary; no full backend suite or Framework/CLI/App extraction was validated.

## Verification

Command:

```text
python -m pytest tests/test_capability_c11_c12.py tests/test_orchestration_tools.py -q
```

Result: **15 passed**.

`git diff --check` completed without whitespace errors. This is focused verification of C11/C12 and adjacent orchestration tests only; it does not certify the full capability audit or any Framework/CLI/App extraction. The repository already contained unrelated dirty and untracked files, which were left untouched.
