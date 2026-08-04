# Core Orchestrator Index

This directory contains the routing and role-selection authority used by the core runtime.

## Entry points

- [ORQUESTADOR_CENTRAL.md](ORQUESTADOR_CENTRAL.md) — orchestration authority and task classification.
- [MATRIZ_DE_ENRUTADO.md](MATRIZ_DE_ENRUTADO.md) — task-to-workflow matrix.
- [ROUTER_DE_ROLES.md](ROUTER_DE_ROLES.md) — role selection rules derived from task shape and risk.

## Notes

- The table in `MATRIZ_DE_ENRUTADO.md` is the canonical compact view for routing.
- `ROUTER_DE_ROLES.md` expands the matrix into decision rules; it should not reintroduce a second authority.
