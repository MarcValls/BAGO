# Conflicts

Record unresolved conflicts between requirements, constraints, or interpretations here.

## Open conflict: chat-dock help text

- **HECHO:** `HelpOverlay` still says "El chat es un panel conmutado, no una pantalla" (`frontend/src/app/ControlPlaneOverlays.tsx`).
- **HECHO:** The implemented `chatDocked` feature makes the chat a panel that can be combined with any screen, and also still a full screen via the `chat` active section.
- **HECHO:** Behavioral tests and fixes now ensure that:
  - only the chat can be docked as a right column,
  - the chat dock and any side panel/inspector are mutually exclusive,
  - the full-screen chat section owns the entire workspace area.
- **INFERENCIA:** The UI copy is stale and contradicts the new behavior.
- **RECOMENDACIÓN:** Update `HelpOverlay` help-note to describe the chat as either a docked panel or a full screen, depending on the user action.
