# Goal: close the seven-point BAGO consolidation plan

## Baseline

- Repository: `MarcValls/BAGO`
- Branch: `orchestration/7-point-kernel-closure`
- Baseline commit: `c2a60a1d22ec09d0f0cb6bdc1700d8b9531ec33f`
- Published baseline: `v4.9.3`

The published tag and assets are immutable. All remediation is developed on the goal branch and must produce a new candidate.

## Objective

Implement and verify the seven agreed consolidation points:

1. Reconcile BAGO operational truth with the current candidate and release.
2. Close release-distribution security: fail-closed Authenticode pipeline and npm vulnerability remediation.
3. Declare and enforce the canonical kernel boundary.
4. Begin safe incremental consolidation of the dual-core/import-path architecture.
5. Stabilize Capability API v1 as an external extension boundary.
6. Separate model identity, observed capabilities, and routing policy; clarify RL/evolution authority.
7. Replace material hand-maintained status documentation with generated, drift-checked projections.

## Acceptance criteria

### AC1 - Candidate-bound truth

- `.bago` state and handoff describe the final goal candidate rather than a historical PR candidate.
- Historical evidence is retained as history and not promoted to the final candidate.
- A drift check detects stale candidate/release projections.

### AC2 - Release security

- Both packaged `BAGO.exe` and the final NSIS installer pass a mandatory Authenticode verification gate before release upload.
- Missing credentials, unsigned output, wrong publisher, invalid timestamp, or invalid signature fail closed.
- CI has a non-secret test path for the signing/verification contract.
- Production public-trust signing is marked BLOCKED unless an authorized real signing identity is supplied; no self-signed test identity may be represented as public trust.
- npm audit has zero high/critical findings and the dependency changes pass product packaging and installer tests.

### AC3 - Kernel boundary

- A canonical, versioned ownership/dependency contract defines kernel and extension responsibilities.
- Automated checks reject a capability or UI surface becoming session/canon authority.

### AC4 - Import consolidation

- At least one coherent vertical slice uses package imports instead of runtime `sys.path` mutation.
- Compatibility facades preserve existing entrypoints.
- No big-bang relocation is required for closure; the remaining migration is explicitly enumerated and mechanically checkable.

### AC5 - Capability API v1

- Existing capability/package routes expose a versioned contract with declarative permissions, dry-run/confirmation/network declarations, and receipts.
- Backend, frontend types, and contract tests agree.

### AC6 - Model/RL policy separation

- Model identity, observed/declared capabilities, and routing policy are separate representations with provenance/fallback behavior.
- Unknown models do not receive fabricated capabilities.
- RL observation/learning/suggestion cannot imply or obtain execution authority; automatic application defaults fail closed.

### AC7 - Generated truth projections

- Version, routes, providers/capabilities, and release/candidate status have generated projections or drift checks where repository authority exists.
- CI runs the drift checks.

### Final validation

- Relevant focused tests pass after each phase.
- Full frontend tests/typecheck/build and backend suite pass on the final state.
- Packaged Electron smoke and real installer E2E pass on the final candidate.
- `git diff --check` passes.
- Independent final verifier returns PASS or explicitly identifies an external BLOCKED condition.

## State semantics

- Code changes are `EXECUTED` until final evidence is recorded.
- Focused tests make only their covered claims `VERIFIED`.
- The goal is `VALIDATED` only when all acceptance criteria, including final installer evidence and any required production signing authority, are satisfied.
