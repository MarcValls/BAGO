# Current UI Shell Evidence

- **Date:** 2026-07-05
- **Target:** repository `frontend/src/app/ControlPlane.tsx`
- **Status:** validated

## Evidence

Validated files:

- `frontend/src/app/ControlPlane.tsx`
- `frontend/src/layout/GlobalHeader.tsx`
- `frontend/src/layout/MainSidebar.tsx`
- `frontend/src/layout/WorkspaceShell.tsx`
- `frontend/src/styles.css`

## Validation Commands

```text
python -m pytest -q tests/test_focus_mode_contract.py tests/test_command_palette_contract.py tests/test_ui_cognitive_load_contract.py tests/test_shortcuts_contract.py tests/test_ui_static_contract.py
```

## Result

```text
12 passed
```

## Notes

- This evidence is a proof artifact. Conclusions and load analysis live in the UI contract and review docs.
- Historical UI run reports are archived under `docs/archive/evidence/`.
