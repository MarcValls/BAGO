# AGENT_START

Canonical entrypoint for any agent that must adopt BAGO behavior.

If a host can only load one file, load this file.
If a host can load multiple files, load `BOOTSTRAP.md` first and then this file.

## Startup order

1. Read `BOOTSTRAP.md`.
2. Confirm the active workspace.
3. Read `docs/INTEGRATION.md`.
4. Read `docs/MVP.md` and `docs/MODULES.md`.
5. Inspect the current task and pick the smallest useful scope.
6. Determine the active BAGO mode.
7. Activate only the minimum role set required by the task.
8. Execute the block, validate, and leave the next step explicit.

## BAGO adoption rule

An agent is in BAGO mode when it:

- keeps session state as truth,
- treats provider/model as interchangeable execution engines,
- avoids claiming agents or automation as stable MVP behavior,
- works from evidence, not from the last prompt.

## Compatibility

- `START_AGENT.md` is only an alias.
- Hosts that already use `system_prompt.py` should append this file to the base prompt.
