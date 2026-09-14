# Core Orchestrator Index

This directory contains the routing and role-selection guidance used by the core runtime.

## Entry points

- [ORQUESTADOR_CENTRAL.md](../../roles/gobierno/ORQUESTADOR_CENTRAL.md) — cabinet planning authority and task classification.
- [MATRIZ_DE_ENRUTADO.md](MATRIZ_DE_ENRUTADO.md) — task-to-workflow matrix.
- [ROUTER_DE_ROLES.md](ROUTER_DE_ROLES.md) — role selection rules derived from task shape and risk.

## Notes

- The table in `MATRIZ_DE_ENRUTADO.md` is the canonical compact view for routing.
- `ROUTER_DE_ROLES.md` expands the matrix into decision rules; it should not reintroduce a second authority.
- `agent_router.py --cabinet` creates a plan from `roles/manifest.json`; it
  does not activate or execute roles.
