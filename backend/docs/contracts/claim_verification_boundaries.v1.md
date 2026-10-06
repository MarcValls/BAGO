# Claim verification boundaries v1

## Authority

`bago_core.operational_integrity.EvidenceBoundaryPolicy` is the decision point
for matching a claim's required verification boundary to the boundary its
evidence actually observed. `ClaimLedger` persists the requested boundary and
rejects `verified` unless candidate-bound evidence matches it. The legacy
`_evidence_verified` boolean bypass is removed, and the append-only writer
also rejects verified rows unless the same evidence is revalidated there.

## Boundaries

| Boundary | What evidence must establish |
|---|---|
| `COMMAND_EXECUTION` | The identified command ran with its recorded result on a stable candidate. It does not prove downstream target state or visible output. |
| `TARGET_STATE` | The exact target/resource state was observed after the operation. |
| `VISIBLE_RENDER` | The exact artifact and UI state were loaded and the rendered result was inspected. |
| `EXTERNAL_ACCEPTANCE` | The named external authority accepted the identified result. |

Boundaries are exact-match scopes; no boundary implies another. Unknown values
fail closed. New claims must declare a boundary through both the Python ledger
API and the CLI. Existing claim rows without a boundary are read as
`COMMAND_EXECUTION` for compatibility.

The current `bago.gate-evidence.v1` adapter emits only
`COMMAND_EXECUTION`. Therefore a gate receipt cannot verify claims requiring
target state, visible rendering, or external acceptance.

Scoped observers do exist. For example, `backend/tests/test_ui_live_smoke.cjs`
uses Playwright to inspect rendered UI state and capture screenshots, and
`frontend/capture_screenshots.mjs` captures selected frontend views. These are
test/capture mechanisms, not currently `ClaimLedger` evidence adapters: they
do not emit a typed boundary receipt bound to the claim, target identity,
artifact hash, observed state, and freshness that `ClaimLedger` revalidates.
Likewise, provider/reviewer receipts prove their defined review scope, not
arbitrary visible UI state or downstream acceptance.

Those claims remain open/failed in the canonical claim ledger until an
appropriate observer is adapted to produce and revalidate evidence for the
requested boundary. A user-authored boundary label or screenshot file alone
does not create such evidence.

## Use

`bago claim add` requires `--verification-boundary` with one of the boundary
names above. `bago claim verify` accepts the current candidate-bound gate
receipt only for `COMMAND_EXECUTION`; unsupported scopes fail closed. Adding a
future adapter requires its own provenance, target identity, freshness,
revalidation, and tests before expanding the accepted boundary set.
