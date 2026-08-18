<!-- BAGO-COPILOT-ENGINEERING:BEGIN -->
## BAGO Copilot engineering contract

This repository is BAGO. For non-trivial engineering work, use the BAGO context/evidence discipline and the `bago-core` skill. For repository change governance, use `repository-engineering`; for full audits, use `bago-audit`.

- Resolve current repository root, branch, HEAD and worktree before current-state claims.
- Project-local Copilot continuity is isolated under `.gabo/copilot/`; never use it as a replacement for BAGO framework sources under `backend/.bago/`.
- Current explicit user instructions outrank this adapter. Do not import unrelated project canon or memory automatically.
- Distinguish `PROPOSED`, `PREPARED`, `EXECUTED`, `VERIFIED`, `VALIDATED`; negative terminal states are `BLOCKED`, `CONFLICT`, `FAILED` when evidence supports them.
- Preserve unrelated pre-existing changes. Do not perform broad cleanup during a scoped fix.
- Canon/governance mutation requires explicit authority; a task override is not automatically canon mutation.
- Never claim a command, test, build, push, release or external mutation occurred unless it actually occurred.
- Final verification must be bound to the final repository state. Earlier evidence becomes stale after material edits.
- Do not commit, push, merge, publish, release, create a repository or change remote settings unless explicitly authorized.
- BAGO backend-confirmed state is authoritative over UI presentation. Security gates fail closed; credentials and live state must not enter release artifacts.
- Relevant repository authorities include `README.md`, `backend/docs/ARCHITECTURE.md`, `backend/docs/SECURITY.md`, `backend/docs/CLAIMS.md`, and `backend/docs/TESTING.md`; read the relevant ones before consequential changes.
- For important closure, use the read-only `bago-final-verifier` agent after implementation evidence exists.
<!-- BAGO-COPILOT-ENGINEERING:END -->

<!-- BAGO-FRONTEND-ENGINEERING:START -->
## BAGO Frontend Engineering
For material work under `frontend/**`, use the `bago-frontend-engineering` skill and applicable path instructions. Preserve backend system authority, canonical navigation, state ownership, secret non-persistence and semantic tokens. Trace UI behavior to real backend capability/evidence where applicable. Separate AUDIT/TRACE, IMPLEMENT and VERIFY; do not equate visible UI or successful compilation with validated behavior.
<!-- BAGO-FRONTEND-ENGINEERING:END -->
