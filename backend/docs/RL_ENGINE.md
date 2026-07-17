# BAGO RL Engine

This is the overview for RL policy surfaces. The live authority is split across code, security rules, module inventory, and tests.

## Live Authority

- `bago_core/rl_bridge.py`
- `bago_core/rl_policies.py`
- `.bago/core/rl_engine.py`
- `.bago/api/control_shadow.py`
- `docs/SECURITY.md`
- `docs/MODULES.md`
- `tests/test_ollama_tool_calling.py`
- `tests/test_f4_guardrails.py`

## Current Contract

- RL observes, recommends, scores, and logs by default.
- `shadow/off` is the default safe posture.
- Autonomous execution is not allowed by default.
- RL live state and checkpoints must not be packaged.

## Notes

- `bago rl status`, `bago rl shadow`, `bago rl train bc`, and `bago rl eval` are the active command surfaces.
- Any future canary/full mode requires explicit evidence and policy gates.
