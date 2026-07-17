# BAGO UI System Visual Grammar

This document describes the active visual grammar of the new React shell.
Behavioral navigation and mode rules live in `docs/UI_CANONICAL_CONTRACT.md`.

## Purpose

Define the current UI as a single system: `ControlPlane` owns the shell, `GlobalHeader` provides context and mode switching, `MainSidebar` is the only visible destination navigator in normal mode, and `WorkspaceShell` hosts the active surface.

## Core Surfaces

- `ControlPlane` - shell orchestration, bootstrap, global modes, command palette, workspace picker, and selection plumbing.
- `GlobalHeader` - status, workspace, model, search, actions, and mode controls.
- `MainSidebar` - destination navigation and next actions.
- `WorkspaceShell` - active content surface for the selected section.
- `SelectionInspector` - detail surface for the selected entity, only in normal mode.
- `StatusBar` - compact state summary, only in normal mode.
- `CommandPalette` - recognition path for fast actions and navigation.
- `WorkspacePickerDialog` - explicit workspace binding flow.

## Visual Grammar

- One visible destination navigator only.
- Header is context, not a second rail.
- Inspector appears only for selected entities.
- Palette is for search and high-frequency actions.
- Status is compact and non-blocking.
- Empty or blocked states should still say the next action.

## Layout Language

- `header` = system context and mode.
- `aside` = destination navigation or selection details.
- `section` = active workspace surface.
- `dialog` = palette and workspace binding.

## Validation Rules

- Do not duplicate destination navigation in the header.
- Do not resurrect the old rail as canonical UI.
- Do not treat the UI as authority over backend state.
- Keep the shell backed by live runtime state.
