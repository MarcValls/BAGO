---
name: bago-frontend-engineering
description: Specialized BAGO frontend engineering for React/TypeScript UI architecture, state ownership, UI-to-backend tracing, tokens, implementation and verification. Use for material work under frontend/ or UI behavior in BAGO.
---

# BAGO Frontend Engineering

## Authority stack
1. Current user task and authorized effects.
2. Active BAGO UI canon: `backend/docs/ui-canonical-contract.md`, `backend/docs/ui-system-visual-grammar.md`, `backend/docs/state-taxonomy.md`.
3. Current source/worktree and backend-confirmed state.
4. Domain specialization under `.gabo/copilot/domains/repository.engineering.frontend/` when installed.
5. Inference/recommendation.

## Select operation
- unclear bug/behavior: TRACE
- broad diagnosis: AUDIT
- known cause: PLAN → IMPLEMENT
- structural cleanup: REFACTOR with invariants
- new UI: ADD_SURFACE
- closure: VERIFY
- stale architecture inventory: REFRESH_SURFACE_MAP

## Proof model
For material behavior, prove applicable links:
`interaction → component → state owner → client/API → backend → response/error → reconciliation/render → tests`.
Never use a visible control as proof that a capability works.

## State model
Backend owns system truth. Shared store owns shared presentation only. Local state owns local transient interaction. Persistence is a separate boundary and must exclude secrets/authority.

## Stop conditions
Stop and hand off if the required fix mutates backend/canon/security/release outside scope, if a canonical conflict is material, or if evidence cannot support the requested closure claim.

## Closure
Use repository-defined gates. Report exact checks and NOT_RUN. Later edits stale prior verification. Independent verification is preferred for material work.
