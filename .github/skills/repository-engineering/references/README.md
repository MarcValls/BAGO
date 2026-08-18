# REPOSITORY ENGINEERING — repository.engineering v0.1.1

Package state: PREPARED
Domain lifecycle state: PROPOSED
Kernel contract: KERNEL GLOBAL 1.0 / RC1
Domain Spec: 1.2
Conformance Test: 1.2
Conformance result: NOT_RUN

## Purpose

This package defines the v0.1.1 documentary correction of the `repository.engineering` specialized domain for auditing, modifying, verifying and governing changes in software repositories while keeping repository canon, current state, execution, evidence, project context and runtime bindings separate.

## Status semantics

- PROPOSED: the domain design exists as a proposal and has not yet been accepted as domain canon.
- PREPARED: this package has been constructed.
- EXECUTED: reserved for actual repository operations performed through an available runtime.
- VERIFIED: reserved for a result supported by sufficient evidence and an explicit verification scope.
- VALIDATED: reserved for a verified result that satisfies its acceptance criterion.

This package does not claim EXECUTED, VERIFIED, VALIDATED or CONFORMANT status for the domain.

## Normative basis

Only the following contracts govern this design:

- KERNEL GLOBAL v1.0 RC1
- DOMAIN SPEC v1.2
- DOMAIN CONFORMANCE TEST v1.2

DOMAIN DESIGNER v1.2 was used only as design tooling. DOMAIN TEMPLATE v1.2 and DOMAIN MANIFEST schema v1.2 define the construction form.

## Files

- `DOMAIN.md` — complete instantiated domain design.
- `DOMAIN_STATE.md` — local state model and current proposal state.
- `DOMAIN_CANON.md` — candidate domain canon model and mutation rules.
- `DOMAIN_ROUTING.md` — declarative routing signals and handoffs.
- `DOMAIN_OPERATIONS.md` — operation inventory and closure rules.
- `DOMAIN_PROCEDURES.md` — reproducible operational procedures.
- `DOMAIN_EVIDENCE.md` — specialized evidence model.
- `DOMAIN_MEMORY.md` — specialized memory policy.
- `DOMAIN_RELATIONS.md` — interdomain relation policy.
- `DOMAIN_PROJECT_BINDINGS.md` — many-to-many project binding model; no concrete project is bound in v0.1.1.
- `DOMAIN_RUNTIME_BINDINGS.md` — runtime binding model; no universal binding is asserted.
- `DOMAIN_MANIFEST.json` — machine-readable manifest.
- `DESIGN_DECISIONS.md` — design decisions and unresolved implementation bindings.
- `PACKAGE_INVENTORY.json` — package-integrity inventory for the other 14 artifacts.

## Package boundary

- The package consists of exactly 15 physical files.
- `PACKAGE_INVENTORY.json` is one of those 15 files.
- `PACKAGE_INVENTORY.json` inventories the other 14 artifacts.
- `PACKAGE_INVENTORY.json` intentionally does not declare its own SHA-256, avoiding a recursive self-hash requirement.

## Version traceability

- `repository.engineering v0.1.0`: SUPERSEDED.
- `repository.engineering v0.1.1`: PROPOSED.
- v0.1.1 package construction state: PREPARED.
- DOMAIN_CONFORMANCE: NOT_RUN.
- Cause: close the documentary divergences identified in the preceding inspection without changing superior contracts or activating any project/runtime binding.

## Explicit non-actions

- DOMAIN CONFORMANCE TEST v1.2 has not been executed.
- No software repository has been modified.
- No concrete project has been made an instance, child or property of this domain.
- No concrete runtime binding has been assumed available.
