# Conflicts

Record unresolved conflicts between requirements, constraints, or interpretations here.

## Hygiene conflict: duplicate HelpOverlay / CommandPalette / ActivityToast definitions

- **HECHO:** `frontend/src/app/ControlPlane.tsx` defines its own local copies of
  `ActivityToast`, `HelpOverlay`, and `CommandPalette` (`lines ~1718-1805`).
- **HECHO:** `frontend/src/app/ControlPlaneOverlays.tsx` exports the same three
  components with the same APIs.
- **HECHO:** `ControlPlane.tsx` does not import them from `ControlPlaneOverlays.tsx`;
  it uses its local copies, so edits to `ControlPlaneOverlays.tsx` do not affect
  the live UI.
- **INFERENCIA:** This duplication caused the HelpOverlay copy update to appear
  fixed in tests (which import from `ControlPlaneOverlays.tsx`) while the running
  app still showed stale text.
- **RECOMENDACIÓN:** Remove the local definitions from `ControlPlane.tsx` and import
  `ActivityToast`, `HelpOverlay`, and `CommandPalette` from `ControlPlaneOverlays.tsx`.
  Keep `ControlPlaneOverlays.tsx` as the single source of truth.
