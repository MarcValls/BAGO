# BAGO MVP Boundary

This document freezes the current BAGO product boundary. Anything outside the stable table is not a stable product claim.

## Stable MVP

| Area | Status | Canonical docs |
|---|---|---|
| Core runtime | Stable | `docs/claims.md`, `docs/testing.md` |
| Install and platform support | Stable | `README.md`, `docs/claims.md`, `docs/support-matrix.md` |
| Security posture | Stable | `docs/security.md`, `docs/testing.md` |
| UI surface | Optional | `docs/ui-canonical-contract.md`, `docs/claims.md` |

## Outside The MVP

| Area | Status | Canonical docs |
|---|---|---|
| RL policy layer | Experimental | `docs/security.md`, `docs/claims.md` |
| Agents and autopilot | Experimental | `docs/security.md`, `docs/claims.md` |
| C++ runtime | Experimental | `docs/claims.md` |
| Cloud multiprovider completeness | Partial | `docs/support-matrix.md`, `docs/claims.md` |
| Advanced knowledge/embedding store | Partial | `docs/modules.md`, `docs/claims.md` |
| Extended monitoring | Experimental | `docs/security.md`, `docs/claims.md` |

## Product Rule

The release line must stay small until the MVP proves reproducible on a clean Windows target.
