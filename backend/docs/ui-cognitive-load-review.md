# BAGO UI Cognitive Load Review

Status: aligned to the new `ControlPlane` UI shell.

## Real Findings

- The UI now has one canonical destination navigator: `MainSidebar`.
- `GlobalHeader` carries context, search, commands, and mode switching, not destination chips.
- `focus` and `review` are real global modes in the shell, not document-only concepts.
- `SelectionInspector` and `StatusBar` are conditional chrome that disappear outside normal mode.
- The command palette is the recognition path for frequent actions and mode switching.

## Cognitive Load Methods Required

- Progressive disclosure: keep secondary chrome hidden in focus and review modes.
- Recognition over recall: use the command palette for navigation and actions.
- One visible destination navigator: do not duplicate sections in the header.
- Status summary first: keep backend/model/session state compact in the header.
- Empty states should still say what to do next.
- Review mode should stay read-oriented and centered.

## Ordered UI Constraints

1. Keep `MainSidebar` as the only destination rail in normal mode.
2. Keep `GlobalHeader` free of destination duplication.
3. Preserve `focus` and `review` as global shell modes.
4. Keep `WorkspaceShell` as the active content container for the selected section.
5. Keep command palette access available from keyboard and header.

## Validation Criteria

- No duplicated visible destination navigation.
- Focus mode hides the sidebar and inspector chrome.
- Review mode keeps the shell readable without adding a second navigator.
- Command palette and workspace picker remain explicit and accessible.
