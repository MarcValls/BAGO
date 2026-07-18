# BAGO UI Canonical Contract

This document defines the active UI contract for BAG4.8. The new React shell is the starting point for all interface work.
Layout, visual grammar, and presentation language live in `backend/docs/UI_SYSTEM_VISUAL_GRAMMAR.md`.
The canonical maturity taxonomy lives in `backend/docs/BAGO_STATE_TAXONOMY.md`.

## Source Of Truth

- `frontend/src/app/ControlPlane.tsx`
- `frontend/src/layout/GlobalHeader.tsx`
- `frontend/src/layout/MainSidebar.tsx`
- `frontend/src/layout/WorkspaceShell.tsx`
- `frontend/src/features/sections.tsx`
- `frontend/src/layout/InspectorDrawer.tsx`
- `backend/docs/BAGO_STATE_TAXONOMY.md`

## Canonical Shell

- `ControlPlane` owns the UI state, backend bootstrap, command palette, workspace picker, selection inspector, and global mode.
- `GlobalHeader` is context and mode chrome, not destination navigation.
- `MainSidebar` is the only visible destination navigator in normal mode.
- `WorkspaceShell` is the active content surface for the current destination.
- `InspectorDrawer` is the contextual inspection surface.
- `frontend/src/features/sections.tsx` renders the task-oriented screens and their backend-driven guidance.
- `backend/docs/BAGO_STATE_TAXONOMY.md` is the reference for implementation maturity labels.

## Destinations

The active destinations are:

- `home` (`Inicio`)
- `chat` (`Trabajo`)
- `workspace` (`Workspace`)
- `graph` (`Control`)
- `pipeline`, `evidence`, `context` (`Control`)
- `system` (`Sistema`)

These are switched from `MainSidebar` and from the command palette, never duplicated as a second visible destination rail in the header.

## Global Modes

- `normal`
- `focus`
- `review`

Behavioral mode rules are defined in `docs/UI_SYSTEM_VISUAL_GRAMMAR.md` only as presentation guidance; the canonical mode contract is here.

## Command And Shortcut Contract

- `Ctrl+K` and `Cmd+K` open the command palette.
- `Escape` closes the palette and picker dialogs.
- The command palette must include mode switching and the active backend actions exposed by `ControlPlane`.
- The workspace picker remains explicit and manual; no hidden path assumption.

## UI Boundaries

- Do not reintroduce the previous shell entry as the active shell.
- Do not reintroduce the previous top chrome or rail as canonical UI surfaces.
- Keep destination navigation in one place.
- Keep the header for context, search, actions, and mode switching.
- Do not infer implementation maturity from runtime states; use `implementation_state` for that purpose.
