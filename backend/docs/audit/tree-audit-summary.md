# Tree audit summary

Generated with:

```powershell
python scripts\tree_state_audit.py --root . --format md --workspace-only --max-results 200 --output backend/docs/audit/tree-state-audit.md
python scripts\tree_bug_audit.py --root . --format md --max-results 200 --output backend/docs/audit/tree-bug-audit.md
python scripts\tree_truth_audit.py --root . --format md --max-results 200 --output backend/docs/audit/tree-truth-audit.md
```

## What this battery covers

- `tree-state-audit`: state that can cross workspace boundaries.
- `tree-bug-audit`: lifecycle bugs, stale effects, and mirrored state.
- `tree-truth-audit`: dependency gaps, dual sources of truth, and snapshot/storage mixing.

## Top findings

### High-priority state crossings

- `backend/manager/js/chain-manager.js`: global `localStorage` keys for patch surface, pipeline rail, query, and chains.
- `backend/manager/js/patch-manager.js`: global `localStorage` keys for audit tab, audit metrics, and matrix orientation.
- `frontend/src/api/client.ts`: `bago.ui.apiToken` is removed through global storage.
- `frontend/src/features/sections.tsx`: `bago.start.chat-mode` is read and cleared through session storage.

### Lifecycle and cleanup risks

- `frontend/src/features/sections.tsx`: mount-only refresh effects around `client`.
- `frontend/src/features/workspace/WorkspaceModule.tsx`: mount refresh of GitHub state.
- `frontend/src/layout/SystemTabs.tsx`: interval-like refresh effect without obvious cleanup nearby.
- `frontend/src/features/workspace/WorkspacePickerDialog.tsx`: timeout effects without obvious cleanup nearby.

### Truth-source and dependency risks

- `frontend/src/app/ControlPlane.tsx`: empty-deps effects and callbacks that still read live values.
- `frontend/src/features/context-tree/useContextTree.ts`: multiple callbacks with incomplete dependency surfaces.
- `frontend/src/features/sections.tsx`: snapshot and storage are mixed in the same file.
- `frontend/src/features/context-tree/ContextActivityTray.tsx` and `frontend/src/layout/ChatPanel.tsx`: state seeded from props and mirrored locally.

## Rule

- Treat these reports as review evidence only.
- Do not interpret them as automatic repair instructions.
