---
applyTo: "**/test_*.py,**/*.test.*,**/*.spec.*,.github/workflows/**"
---

# BAGO tests and CI instructions

Tests and CI are evidence mechanisms, not obstacles to bypass. Do not delete, skip, weaken or broaden exclusions merely to obtain green status without explicit justification. Bind pass/fail claims to the exact command/run and final revision. Record `NOT_RUN`/`NOT_EXECUTABLE` when a gate cannot actually run. Check Git status before and after commands that can generate artifacts.
