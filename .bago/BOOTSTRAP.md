# BAGO Bootstrap

BAGO is a session-first control plane. The session is the source of truth.
Providers and models are execution engines, not the authority.

## Purpose

This file is the shared base prompt for hosts that need BAGO behavior.
It should stay short, stable, and host-agnostic.

## Rules

- Keep provider and model interchangeable.
- Do not treat the UI as authority.
- Keep claims tied to evidence.
- Treat RL, agents, autopilot, and advanced orchestration as experimental unless explicitly authorized.
- Prefer the smallest verifiable change over a broader rewrite.

## Canonical reading order

1. `README.md`
2. `docs/MVP.md`
3. `docs/MODULES.md`
4. `docs/CLAIMS.md`
5. `docs/INTEGRATION.md`
6. `bago_core/session_manager.py`
7. `bago_core/install_roles.py`
8. `scripts/bago_supervisor.py`

## BAGO modes

- `B` Balance: clarify objective, scope, risk, and exit criteria.
- `A` Adapt: inspect the real state and choose a workable strategy.
- `G` Generate: produce artifacts that can be verified.
- `O` Organize: record state, close the loop, and leave continuity.

## Working rule

If the task touches the repository, inspect the real tree first and edit only the minimum set of files needed.
