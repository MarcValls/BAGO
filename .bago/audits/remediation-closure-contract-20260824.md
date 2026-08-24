# BAGO remediation closure contract

This document binds the 2026-08-24 remediation candidate to the ten findings
opened in `remediation-baseline-20260824.md`.  It does not itself certify the
candidate.  Final state is determined from the immutable candidate SHA, the raw
gate records in the audit bundle, and the independent review.

| Finding | Remediation | Falsifiable regression / evidence gate |
|---|---|---|
| BAGO-AUD-001 | Information-only plan steps cannot become executed material work. | `test_plan_engine_contract.py`: zero actions, zero evidence and no execution-success wording. |
| BAGO-AUD-002 | Intent stance rejects negated and meta-question action mentions before scoring. | `test_intent_stance_contract.py`: affirmative, polite, negated and interrogative cases. |
| BAGO-AUD-003 | Canonical `/health` and `/api/v1/kb` CRUD contract implemented by the real dispatcher. | `test_kv_integration_contract.py`: real HTTP health/read/write/update/delete and explicit failure behavior. |
| BAGO-AUD-004 | Release backup preparation is phase-aware and never deletes the sole rollback copy on resume. | `test_release_backup_resume.cjs` plus release-manager contract gate. |
| BAGO-AUD-005 | Audit patches are emitted as LF bytes and applied raw to the archived baseline. | `package_remediation_audit.py` aborts unless both raw patches pass `git apply --check`. |
| BAGO-AUD-006 | Package provenance contains full baseline/candidate SHA, remote status, branch/upstream and manifest hashes. | Final audit package provenance JSON, manifest and sidecar SHA-256. |
| BAGO-AUD-007 | A purpose-built handoff is included; no session transcript is used as handoff evidence. | `remediation-handoff-20260824.md` is mandatory input to the packager. |
| BAGO-AUD-008 | Every claimed gate has command, exit code, runtime, timestamps, output hashes and candidate identity. | `record_remediation_gate.py` records raw stdout/stderr and JSON metadata. |
| BAGO-AUD-009 | `gestor-con-bago` has a local Git baseline and a candidate delta with the same package standard. | Gestor baseline/candidate archive, patch, provenance and frontend build/typecheck gates. |
| BAGO-AUD-010 | Session-export HTML is excluded and forbidden by the audit packager. | `session-export-hygiene` gate and package-level filename rejection. |

## Required final gates

- Backend complete suite for the candidate, with every skip visible.
- Focused AUD-001..004 and operational-integrity regressions.
- Backend source ZIP build and packaging tests.
- Frontend tests, typecheck and production build.
- Live UI smoke against the built frontend.
- Release manager and crash/resume tests.
- `gestor-con-bago` typecheck and production build.
- Workflow YAML parse, diff check and session-export hygiene.
- Raw patch reproducibility for BAGO and `gestor-con-bago`.
- Independent final review of the candidate and evidence.

`VALIDATED` is forbidden while any required gate has a non-zero exit code, a
required gate is absent, candidate identities conflict, or independent review
reports a blocking finding.
