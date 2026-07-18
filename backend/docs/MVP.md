# BAGO MVP Boundary

This document freezes the current BAGO product boundary. Anything outside the stable table is not a stable product claim.

## Stable MVP

| Area | Status | Canonical docs |
|---|---|---|
| Core runtime | Stable | `docs/CLAIMS.md`, `docs/TESTING.md` |
| Install and platform support | Stable | `README.md`, `docs/CLAIMS.md`, `docs/SUPPORT_MATRIX.md` |
| Security posture | Stable | `docs/SECURITY.md`, `docs/TESTING.md` |
| UI surface | Optional | `docs/UI_CANONICAL_CONTRACT.md`, `docs/CLAIMS.md` |

## Outside The MVP

| Area | Status | Canonical docs |
|---|---|---|
| RL policy layer | Experimental | `docs/SECURITY.md`, `docs/CLAIMS.md` |
| Agents and autopilot | Experimental | `docs/SECURITY.md`, `docs/CLAIMS.md` |
| C++ runtime | Experimental | `docs/CLAIMS.md` |
| Cloud multiprovider completeness | Partial | `docs/SUPPORT_MATRIX.md`, `docs/CLAIMS.md` |
| Advanced knowledge/embedding store | Partial | `docs/MODULES.md`, `docs/CLAIMS.md` |
| Extended monitoring | Experimental | `docs/SECURITY.md`, `docs/CLAIMS.md` |

## Product Rule

The release line must stay small until the MVP proves reproducible on a clean Windows target.
