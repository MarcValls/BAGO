# Goal: close UNIQUE_EXECUTION_BOUNDARY

## Objective

Route every runtime material-effect sink through the canonical
`ExecutionGateway`, with one registered server-owned adapter per canonical
effect, authority resolved before materialization, and negative pre-effect
coverage.

## Additional user scope

Close the two remaining partial capabilities in the map branch Contexto y memoria: SQLite/FTS5/embeddings and Nodos y conectores. Reuse existing stores and contracts where possible; preserve a single session/workspace identity and one authorized persistence path.

## Acceptance criteria

- `python backend/.bago/tools/effect_sink_inventory.py --strict-runtime` exits 0.
- `python backend/.bago/tools/effect_sink_inventory.py --strict-classification` exits 0.
- Every migration preserves one authority/identity path; scanner exemptions or
  relocations without runtime dispatch proof do not count as closure.
- Candidate-bound focal gates and the full backend suite pass on the final
  committed candidate.
- Independent final review passes before claiming global `VERIFIED` or
  `VALIDATED`.

## Baseline

- Candidate: `c95b516d9110979b01826ffc9a64e145d23aec05`.
- Worktree: clean at entry.
- Inventory: 2,123 total findings; 478 runtime-unbound, including 308
  filesystem writes, 77 deletes, 79 process executions, 13 network reads and
  one external network write. Strict classification has zero unclassified
  scope/binding.
- Current lifecycle: `EXECUTED`; global uniqueness remains OPEN.

## Execution rule

Work in dependency-ordered, reviewable tranches. Keep installers, build/admin
and derived evidence visible in inventory; scope is not an exclusion. Each
tranche must show runtime reachability, authority owner, effect adapter,
pre-effect blocking, regression evidence and candidate identity.

## Status

`EXECUTED / OPEN` — the dirty worktree inventory is 2,219 findings, 103
runtime-unbound, and zero unclassified scope/binding. PI sidecar process
creation now uses the registered `process.sidecar.execute` owner, while
arbitrary test shims stay confined to pytest. Autonomous learning
writes route through the registered policy effect `learning.write`, restricted
to its two canonical files. The duplicate `LearningWriter` and process-monitor
self-tests now live in pytest rather than executable runtime tools.
`process_monitor generate` now uses the explicit `monitor.generate` Permit and
one shared TTY CLI authorization helper, also used by autonomous repairs. The
adapter binds project root, destination, prior-file digest, and report digest;
it blocks path escape, links, and target drift before writing. Standalone
`install-remote.ps1`, legacy rollback, and other runtime sinks remain open. The
candidate is uncommitted; strict runtime, the full backend suite on the final
candidate, and independent review remain open.

The inventory scanner now detects write modes in bound `Path.open("a"/"w"/"x")`
calls; its regression suite passes 28 tests. This exposed direct append sinks
that were absent from the prior count. Reflexive audit JSONL now uses the
existing server-owned `state.write` owner and no longer creates its evidence
directory during construction; its two focused tests pass. Current strict
classification passes, while strict runtime remains open at 103. The latest
tranches route `LayerStore` JSONL persistence through the existing
`state.write` owner and REPL UI configuration through `config.write`; both
preserve their existing data format and path identities. Focused tests and
strict classification pass. Runtime state bootstrap now uses its own registered
`state.bootstrap` owner. `ConfigManager` also defers directory creation until
its existing state writer persists the first update. Strict runtime remains
open with 103 findings.
