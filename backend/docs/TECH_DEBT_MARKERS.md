# FIXME/HACK/XXX audit

Date: 2026-08-16  
Scope: `backend/bago_core/`, `backend/.bago/`, `backend/tools/`

## Result

No unresolved `FIXME`, `HACK` or `XXX` markers remain in production code.

All matches found are either:

1. Part of the scanning regexes in `dead_code.py`, `todo_scan.py`, `commit_readiness.py` and `secret_scan.py`.
2. A deliberately planted fixture string inside `dead_code.py` self-test data:  
   `# FIXME: esto rompe en Python 3.12` — used only to exercise the scanner.

## Action

If new `FIXME`/`HACK`/`XXX` markers are added, `todo_scan.py` and the commit-readiness gate will flag them automatically.
