# BAGO 4.8 baseline

Date: 2026-07-08

## Scope

This baseline records the current state before the workspace-authority fixes.
It is intentionally narrow: release evidence, task-contract normalization, and
workspace authority wiring.

## Validated facts

1. `release_version.txt` reports `4.8.0`.
2. `tests/test_code_forge_compiler.py` passes in the current tree.
3. `test_security_release.py` still expects `docs/archive/evidence/release_4_7_0`
   and `4.7.0` evidence metadata even though the current release is `4.8.0`.
4. `test_security_release.py` currently fails earlier on
   `features.auto_allow_tools` defaulting to `True` instead of `False`.
5. `handlers_workspace.py` still computes `canChat` from provider/model plus
   `binding_confirmed OR project_root`.
6. `workspace_binding.py` still treats `.gabo/workspace.json` as the canonical
   workspace identity record.
7. `project_memory.py` still writes legacy `.bago` artifacts for init/link.

## Commands run

- `python -m pytest test_security_release.py -q --maxfail=1`
- `python -m pytest tests\\test_code_forge_compiler.py -q --maxfail=1`

## Results

- `test_security_release.py`: failed on
  `assert cfg.get("features.auto_allow_tools") is False`.
- `tests/test_code_forge_compiler.py`: `6 passed`.

## Risk summary

- Release packaging evidence is stale relative to the current release tag.
- Workspace authority is still mixed between legacy `.bago` state and the
  canonical `.gabo` workspace root.
- Backend permissions still over-trust project presence when `binding_confirmed`
  is false.

