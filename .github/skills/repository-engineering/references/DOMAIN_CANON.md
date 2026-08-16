# DOMAIN CANON — candidate for repository.engineering v0.1.1

Status: PROPOSED

## Canonical location

This file is the designated canonical location for the domain after explicit acceptance by an authorized domain-governance actor/process. Until that acceptance occurs, its contents are candidate canon and remain PROPOSED.

## Domain-canon subjects

Once accepted, domain canon may define:

- repository-engineering vocabulary and entity semantics;
- domain operation inventory and local restrictions;
- repository-specific evidence sufficiency rules;
- repository baseline/change attribution rules;
- domain products and acceptance criteria;
- routing signals and local handoff semantics;
- project-binding and runtime-binding models;
- versioning and supersession records.

## Not domain canon

The following do not become `repository.engineering` canon by being used with this domain:

- project instructions;
- project architectural decisions;
- target repository architecture/governance;
- repository current state;
- commits, branches or issues;
- runtime tool availability;
- memory;
- inferences;
- task-specific overrides.

## Mutation authority

A domain-canon mutation requires an actor/process explicitly authorized to govern `repository.engineering` plus explicit mutation intent.

A target repository-canon mutation requires the authority of that repository/project, not the authority of this domain.

## Mutation procedure

1. Classify the requested change as ordinary execution, TASK_OVERRIDE, domain CANON_MUTATION or target-repository CANON_MUTATION.
2. Require explicit mutation intent for either canon mutation.
3. Resolve the correct authority.
4. Identify current canonical version and any conflicting/superseded records.
5. Prepare change and impact.
6. Execute only if required capability is real and authorized.
7. Preserve prior material as SUPERSEDED/DEPRECATED/CONFLICT as appropriate.
8. Verify exact before/after source.
9. Validate only against the explicit acceptance criterion and acceptance authority.

## Supersession history

- v0.1.0: initial candidate; `SUPERSEDED` by v0.1.1; conformance remained `NOT_RUN`.
- v0.1.1: current candidate; `PROPOSED`; package `PREPARED`; conformance `NOT_RUN`.

Supersession cause: documentary consistency correction covering repository capability identifiers, diff inspection semantics, operation/manifest capability requirements, `AUDIT_SCOPE`, package boundary and version traceability.

Effect: v0.1.1 replaces v0.1.0 as the current candidate without asserting acceptance as canonical, execution through the domain, verification, validation or conformance.

Future canonical changes must record old version, new version, cause, effect and prior-version state.
