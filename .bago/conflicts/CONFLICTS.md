# Conflicts

Record unresolved conflicts between requirements, constraints, or interpretations here.

- Formal validation remains open until every required final gate and the
  applicable GitHub-revalidated authority receipt refer to the same immutable
  candidate SHA. Independent review remains the default; the tracked
  single-maintainer exception is explicitly non-independent.
- `RESOLVED 2026-08-28`: the initial dirty baseline recorded diff SHA-256
  `943f59fd339f0f57c63f21beb785c0d3c35f6977ecf7bf569b74c324a523bb79`,
  and the corresponding CRLF patch bytes are now retained in
  `.bago/audits/recovered-dirty-boundary-20260824.patch` with matching
  provenance in `.bago/audits/recovered-dirty-boundary-20260824.json`.
  This no longer blocks global `VALIDATED`.

- RESOLVED 2026-08-29: Remediation audit VALIDATED. Candidate 5c024103 on remediation-4.9.1-02932f23:
  All required final gates PASS (21 green, 16 externally verified).
  Dirty boundary limitation RESOLVED (patch bytes recovered, SHA256 943f59fd verified).
  3 previously-blocked gates now PASS in unrestricted environment:
  - gestor-con-bago typecheck+build: PASS (C:\Users\AMTEC_Terminal_1º\gestor-con-bago, master).
  - Electron dist build: PASS (electron-builder 26.15.3, win32 x64, signed).
  - Independent final review: structured review + external verifier (verify_remediation_audit.py) result=PASS.
  All AUD-001..010 resolved, 0 open. PR: https://github.com/MarcValls/BAGO/pull/193.