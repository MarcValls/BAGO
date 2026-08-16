# Hook Protocol

The runtime uses hooks as guardrails, not as the sole source of truth.

## SessionStart

When `.bago/config.json` is enabled, load a compact view of project context, state, handoff, and verification freshness as developer context. This also runs after compaction, restoring continuity.

## PostToolUse

For Bash and apply_patch, append a redacted local evidence receipt and update the repository fingerprint. Successful verification-like commands are recorded as checks, but they do not automatically satisfy unknown acceptance criteria.

## Stop

The closure guard is intentionally narrow. It only continues the turn when the final message makes a strong verification/validation/test-success claim that is not supported by fresh final-state evidence.

The guard avoids loops by honoring `stop_hook_active`.
