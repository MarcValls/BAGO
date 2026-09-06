# Safe Refactor Protocol

Status: **PROPOSED**.

Structural work must be a separate operation from a feature unless the change
unit explicitly authorizes both behavior and structure.

## Sequence

1. Capture a repository baseline and the observable public behavior.
2. Add characterization tests for behavior that must remain unchanged.
3. Declare the target boundary and ownership in a module contract.
4. Define or verify public interfaces, schemas, events and DTOs before moving
   implementation.
5. Introduce a compatibility adapter when existing consumers cannot migrate in
   the same change unit.
6. Move one responsibility at a time.
7. Compare before/after public API, behavior, capabilities, dependencies and
   cycles.
8. Migrate consumers explicitly.
9. Remove the adapter only after all consumers use the public contract.
10. Run independent verification against the final change set.

## Prohibited shortcuts

- changing observable behavior under an operation marked `refactor`;
- importing another module's `internal/` surface;
- deleting a compatibility adapter before consumer inventory is empty;
- treating compilation as proof of behavior preservation;
- changing repository canon without `repo.govern_change` authority;
- claiming `VALIDATED` without explicit acceptance criteria.

## Escalation

Stop with `ARCHITECTURE_BOUNDARY_REQUIRED` when the target boundary is
ambiguous, ownership would move, a public contract would change, or a forbidden
dependency is necessary. Return the affected paths, requested dependency,
reason, alternatives and required verification.
