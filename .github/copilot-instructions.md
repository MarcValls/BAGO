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

### Codex agentic alignment

Project-local Codex configuration under `.codex/` is legacy but authoritative as
the behavioral source for the Pi/Copilot BAGO skills. When a task needs role
selection, project the Codex roles as follows instead of inventing a new agent
taxonomy:

- Use `bago-auditors` for read-only review modes: `architecture`, `backend`,
  `frontend`, `contracts`, `security`, `performance`, `tests`, `hygiene`,
  `truth`, and `code-map`.
- Use `bago-workers implement` only for approved scoped implementation, and
  `bago-workers mechanical` only for fully specified repetitive edits.
- Use `bago-final-verifier` as the independent read-only verifier after
  implementation evidence exists or before closure-sensitive claims.
- Preserve the Codex role boundary: auditors and final verifiers do not edit;
  workers do not certify their own changes; tests/builds are evidence, not
  validation authority.
- Treat `.codex/config.toml` as an execution-profile hint only
  (`workspace-write`, live web, medium verbosity). It does not override current
  user instructions, BAGO runtime state, repository authorities, tool
  availability, or Copilot CLI operating constraints.

### Dynamic Copilot orchestration

Select the smallest non-overlapping operating shape from the current task,
affected surface, risk, and evidence requirement:

| Task shape | Default operating shape |
|---|---|
| Focused lookup, explanation, or change covering at most a few direct tool calls | Work directly; do not delegate. |
| Bounded read-only concern | Use the matching BAGO auditor or tracer. |
| Approved, scoped implementation | Use the matching worker; use the frontend engineer for material `frontend/**` work. |
| Cross-surface, authority-sensitive, or closure-sensitive change | Coordinate through `bago-repository-engineer`; request only the specialist roles needed. |
| Final-state or release-sensitive conclusion | Run repository-defined evidence first, then use `bago-final-verifier`. |

- Re-evaluate the operating shape after material findings, failed checks, scope
  expansion, or a changed candidate. Do not retain a delegation merely because
  it was selected earlier.
- A cabinet plan is advisory and limited to three concurrent delegated roles.
  It must separate investigation, implementation, and independent verification;
  agents must not review or certify their own edits.
- Planning never authorizes an edit, a destructive action, a commit, a remote
  mutation, or a claim of completion. Preserve user approval and repository
  authority gates at every adjustment.
<!-- BAGO-COPILOT-ENGINEERING:END -->

<!-- BAGO-FRONTEND-ENGINEERING:START -->
## BAGO Frontend Engineering
For material work under `frontend/**`, use the `bago-frontend-engineering` skill and applicable path instructions. Preserve backend system authority, canonical navigation, state ownership, secret non-persistence and semantic tokens. Trace UI behavior to real backend capability/evidence where applicable. Separate AUDIT/TRACE, IMPLEMENT and VERIFY; do not equate visible UI or successful compilation with validated behavior.
<!-- BAGO-FRONTEND-ENGINEERING:END -->
