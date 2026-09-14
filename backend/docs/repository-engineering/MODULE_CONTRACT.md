# Module Contract Template

Status: **PROPOSED**. Copy this template only when a logical module has an
approved owner and an explicit repository change unit.

## Identity

- Module:
- Owner:
- Lifecycle: `PROPOSED | ACTIVE | SUPERSEDED`
- Source paths:
- Change unit:

## Purpose and responsibility

Describe the single responsibility this module owns. List responsibilities
that are explicitly outside the module.

## Public API

| Symbol/route/event | Direction | Contract source | Stability |
|---|---|---|---|
|  |  |  |  |

Only this surface may be consumed by other modules. Internal symbols are not a
cross-module API.

## Dependencies

### Allowed

- None declared.

### Forbidden

- direct imports from another module's `internal/`;
- access to another module's persistent state;
- duplicate authority for backend-confirmed state;
- undocumented transport or filesystem side effects.

## Invariants

- None declared.

## State ownership

- Persistent state owned:
- Ephemeral state owned:
- State received from another authority:
- Secrets or credentials persisted: **never by default**.

## Events and effects

| Event/effect | Produces or consumes | Authority | Evidence |
|---|---|---|---|
|  |  |  |  |

## Required tests

- contract/API tests:
- regression tests:
- architecture-boundary tests:

## Boundary escalation

Return `ARCHITECTURE_BOUNDARY_REQUIRED` instead of adding a dependency when
the implementation needs a forbidden dependency, changes state ownership,
changes a public contract, or requires a new cross-module effect.
