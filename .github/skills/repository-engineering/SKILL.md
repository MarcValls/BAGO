---
name: repository-engineering
description: Candidate repository.engineering v0.1.1 operational projection for auditing, planning, modifying, verifying, governing and containing repository changes with explicit baseline, evidence and authority separation.
---

# Repository Engineering

Use this skill for non-trivial repository operations where attribution, scope, authority and verification matter.

## Source status

The bundled `repository.engineering v0.1.1` source is `PREPARED`; its domain lifecycle is `PROPOSED`; DCT v1.2 conformance is `NOT_RUN`. Do not call this version CONFORMANT or VALIDATED. The v0.1.0 conformance report bundled elsewhere is historical and does not transfer to v0.1.1.

## Operation routing

Route the task to the smallest applicable candidate operation defined in `references/DOMAIN_OPERATIONS.md`:
- `repo.resolve_baseline`
- `repo.audit`
- `repo.plan_change`
- `repo.apply_change`
- `repo.verify_change`
- `repo.govern_change`
- `repo.contain_or_rollback`
- `repo.prepare_handoff`

Use the matching procedure in `references/DOMAIN_PROCEDURES.md`. Load only the references needed for the active operation.

## Required discipline

Before mutation, establish repository identity, HEAD, branch, worktree/index status, pre-existing changes, exact authorized target paths/effects and required capabilities.

Trace material claims as:
`claim -> repository source/action -> evidence reference -> verification scope -> conclusion`

Do not absorb unrelated pre-existing changes into the current change set. Do not infer that a build verifies tests, a diff verifies behavior, or an old CI run verifies a later HEAD.

A governance/canon mutation requires explicit mutation authority and before/after/supersession evidence. A task-specific override is not by itself a canon mutation.

If authority, capability, identity or sufficient evidence is missing, use `BLOCKED`; if incompatible competing state prevents safe attribution, use `CONFLICT`; if an executed acceptance check fails, use `FAILED`.
