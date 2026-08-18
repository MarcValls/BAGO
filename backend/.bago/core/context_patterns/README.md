# Core Context Patterns

This directory defines the packaged context-pattern bundle consumed by the core runtime.

## Authority

- [manifest.json](manifest.json) — required manifest for the packaged bundle.
- [workspace_markers.json](workspace_markers.json) — phrases that indicate active workspace context.
- [workspace_followups.csv](workspace_followups.csv) — follow-up cue phrases for workspace detection.
- [workspace_questions.toml](workspace_questions.toml) — question phrases for workspace inference.
- [workspace_discourse.md](workspace_discourse.md) — discourse notes and examples.

## Notes

- The manifest is the authoritative inventory for this bundle.
- These files are data inputs, not operational policy.
- The bundle is consumed by `context_patterns.py` and related session-context logic.
