# BAGO remediation baseline recovery

Recorded: 2026-08-28

## Scope

This record resolves the historical dirty-boundary limitation opened by
`remediation-baseline-addendum-20260824.md`. It does not modify
`remediation-baseline-20260824.md`.

## Recovered Boundary

- Baseline HEAD: `e76b01b0a0552d8eee7c536f8c4eef25e3a82a42`
- Recorded dirty diff SHA-256: `943f59fd339f0f57c63f21beb785c0d3c35f6977ecf7bf569b74c324a523bb79`
- Recovered artifact: `.bago/audits/recovered-dirty-boundary-20260824.patch`
- Recovered artifact SHA-256: `943f59fd339f0f57c63f21beb785c0d3c35f6977ecf7bf569b74c324a523bb79`
- Recovered artifact size: `13711` bytes
- Line endings: `CRLF`
- Normalized LF SHA-256: `4b6f71631abf8d4fc2d7e9eb028053f94e48be707965e21329602e2751be56c7`
- Provenance: `.bago/audits/recovered-dirty-boundary-20260824.json`
- Recovery/verifier: `scripts/recover_dirty_boundary.py`

## Source Evidence

The patch was reconstructed from recorded `CommandExecution` stdout in:

`C:\Users\AMTEC_Terminal_1º\.codex\sessions\2026\08\24\rollout-2026-08-24T00-50-09-01a030d1-2adf-7103-9fcd-1a649215f72e.jsonl`

Used lines:

- `571`: `handlers_jobs.py`, `plan_engine.py`, `session_turn_mixin.py`,
  `test_plan_engine_contract.py`
- `577`: `config_manager.py`, `test_negatives.py`

The recovery script extracts those diff chunks, orders them by the tracked file
list in the baseline, serializes the result as CRLF, verifies the recorded
SHA-256, and checks that the LF-normalized patch applies to the archived
baseline.

## Conclusion

The former statement "patch bytes were not retained" remains true for the
original baseline capture moment, but it is no longer an active closure blocker:
the exact dirty-boundary bytes have been recovered with the recorded hash and
are now retained as repository evidence.

This recovery only resolves the historical attribution boundary. Candidate
validation still depends on candidate-bound gates, package verification and
independent review as required by the closure contract.
