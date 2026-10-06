# BAGO — Agent context for Pi 0.84.2+

This is the BAGO monorepo. BAGO is a local AI control plane: the session is the source of truth; providers and models are interchangeable execution engines.

## Project structure

- `backend/` — Python runtime (core, CLI, API, contracts). Exact candidate results live in gate receipts.
- `frontend/` — React + TypeScript (Vite). Exact candidate results live in gate receipts.
- `electron-viewer/` — Electron shell with automatic backend lifecycle.
- `.bago/` — BAGO runtime state, context, decisions, conflicts, and handoffs.
- `.codex/agents/` — Legacy Codex CLI agent definitions (Pi does not load them; use the `.agents/skills/` equivalents).

## Available Pi skills

- `/skill:bago-core` — lifecycle, state, evidence-first execution, closure discipline. Load this for any non-trivial or continuation work.
- `/skill:bago-auditors <mode>` — read-only audit swarm. Modes: `architecture`, `backend`, `frontend`, `contracts`, `security`, `performance`, `tests`, `hygiene`, `truth`, `code-map`.
- `/skill:bago-workers <mode>` — implementation. Modes: `implement`, `mechanical`.
- `/skill:bago-final-verifier` — independent verification pass.

## Conventions

- Read `.bago/` state before editing when it exists (`python .bago/bin/bago.py status`).
- Separate canon, verified state, inference, proposal, and experimental material.
- Mark changes `EXECUTED` until final evidence exists; do not call them `VERIFIED` or `VALIDATED` prematurely.
- Make the smallest defensible change and preserve existing architecture unless the request changes it.
- Run repository-defined checks after material edits (tests, typecheck, build).

## Pi-specific notes

- Pi 0.84.2 supports `AGENTS.override.md` for per-directory overrides and `defaultTools` configuration.
- Project trust is required to load project-local `.pi/` settings and `.agents/skills/`.
- Use `/tree`, `/fork`, `/compact`, or `/clone` to manage long-running BAGO sessions.

## BAGOx behavior overlay (ACTIVE_CANON)

This is a scoped projection of the Codex fragment from
`BAGOx Behavior Package v1.3-RC1-FIX2`, anchored to the external
`MANIFEST.sha256` SHA-256
`f916e385ba55cff4b27dd9696c42b3d22dbb83ad00595572e77385766c9fb3eb`.
It adopts only stable agent-behavior rules; package templates, schemas,
hooks, and BAGOx-only state mechanisms remain outside this repository until
separately adopted. BAGOx behavior rules do not themselves modify BAGO canon
or state: BAGO changes require explicit repository operations and BAGO-native
evidence. This overlay does not override explicit user instructions,
repository-local authority, or verified BAGO state.

### Resolve state before material work

- Never use conversational memory as repository authority.
- Resolve repository identity, branch, HEAD, worktree state, canonical version,
  active decisions, conflicts, and current evidence before material mutations
  OR claims about repository state.
- Resolve remote state before claims about GitHub or any remote: run
  `git fetch origin` and verify `origin/main`, PR merge status, and branch
  state against the actual remote. Local tracking refs are last-known, not
  current.
- `.bago/` state files are local projections of last-known state, not remote
  authority. Reconcile with remote before any claim about PRs, merges, or
  GitHub state. Internal coherence of a local file is not evidence of
  current remote truth.
- Resolve the canonical product version from `release_version.txt`; package
  manifests and runtime output are derived checks and never belong in
  `AGENTS.md` as mutable values.
- Treat current-state artifacts as reproducible projections of their
  authorities, not as independent truth.
- On state drift, rehydrate and replan; never reset, restore, or revert merely
  to match remembered state.
- If a tool needed to verify state is unavailable, find an alternative path
  (shell, API, fetch). Tool failure is never permission to skip verification.

### Authority, review, and evidence

- One critical property has one authority; other occurrences are derived.
- Preserve superseded decisions as history.
- `PREPARED`, `EXECUTED`, `VERIFIED`, and `VALIDATED` are distinct states.
- `CRIT_PASS` does not imply `CANON`.
- Reviewers do not silently modify code. Fix agents do not certify their own
  changes. Verification agents do not modify during certification.
- Findings require rule, observed behavior, violation, impact, evidence,
  proposed correction, and verification method.
- Bind claims and receipts to the current candidate. Evidence from another
  candidate is stale unless applicability is explicitly proved.
- Do not claim complete test success when relevant suites were skipped or
  omitted.
- For every material assertion, distinguish the proposition, its authoritative
  source, the evidence actually observed, the scope that evidence covers, and
  remaining uncertainty. Use `UNKNOWN` when a required fact is unavailable;
  do not fill the gap with a plausible explanation.
- Conversation order is not event chronology. A message adjacent to a command
  does not prove when its attachment was captured, which version a target had
  loaded, or whether the command changed what the target displayed. Establish
  time/order from explicit timestamps or provenance; otherwise label it
  `UNKNOWN`.
- Keep each boundary in a claim chain distinct: intended action, command/tool
  execution, produced artifact or response, target acceptance/loading, and
  observed final state. Evidence at one boundary proves only that boundary
  unless a separate observation demonstrates propagation to the next one.
- Before crossing a material-effect or trust boundary, bind authorization to
  the specific operation, actor/session, target resource, and current relevant
  state. Revalidate those bindings immediately before dispatch when they may
  have changed; never treat visibility, successful transport, a prior permit,
  or an agent/tool self-report as authorization or enforcement evidence.
- Verification must observe the system at the boundary named by the claim.
  Source/structure checks do not establish runtime behavior; command success
  does not establish target state; target state does not establish downstream
  acceptance. Bind checks to the exact target and relevant candidate identity
  (path/hash/version/session/resource as applicable), and revalidate after
  changes that could make evidence stale.
- Do not report a task `VERIFIED` or `VALIDATED` from an indirect proxy when
  the required target observation was not made. If a required observation or
  capability is unavailable, mark that scope `NOT_RUN` or `UNKNOWN`, report
  the blocker, and continue with independent checks that remain possible.
- For visual evidence, compare the screenshot's visible URL/state and content
  with the current artifact, reload the identified artifact after regeneration,
  reproduce the affected state, and inspect the rendered result. Structural,
  geometry, or minimal-DOM checks alone do not verify browser rendering.

## Global runtime sink closure

When the objective is to reduce `strict-runtime` or close effect sinks
globally, Codex must complete a read-only partition before repairing any sink.
Do not use the repeated `find one sink -> patch -> test` loop as the global
remediation strategy.

1. Freeze branch, HEAD, porcelain worktree status, changed paths and a
   reproducible worktree fingerprint before scanning. Record scanner identity
   and configuration plus the canonical effect-registry contract/version.
2. Run the repository's official full sink inventory and strict gates on that
   exact candidate. Do not reuse historical counts. Recheck HEAD and fingerprint
   at the end; if either changes, stop and recapture instead of combining runs.
3. Test scanner coverage separately from classification. A zero
   `strict-classification` count means discovered sinks are classified; it does
   not prove every material-effect form is scanned. Incomplete or inconsistent
   coverage blocks planning closure.
4. Trace every runtime-unbound finding from the decision-making caller through
   its call chain to the material effect and affected resource. Partition by
   common responsibility, correct owner and repair, not by line count or effect
   type alone. Report compression as:

   `sinks -> material callsites -> root causes -> repair clusters -> owners -> lanes`.

5. Assign exactly one primary class to each sink: `REUSE`, `EXTEND`,
   `NEW_OWNER`, `DELETE`, `RECLASSIFY` or `BLOCKED`. Apply the order
   `REUSE -> EXTEND -> NEW_OWNER`; justify why existing owners cannot correctly
   own an operation before proposing new infrastructure. Prove reachability
   before `DELETE`. Prove exclusive ownership before `RECLASSIFY`, and keep the
   sink visible to the scanner as `gateway_owned`.
6. Build a dependency DAG and candidate parallel lanes. Treat authorization,
   permits, `ExecutionGateway`, adapter/effect registries, claims, governed
   pipeline, shared contracts and security tests as serialized integration
   points whenever multiple lanes touch them. Do not recommend concurrent edits
   to shared authority files.
7. For every cluster, map only canonical authorization modes and assess
   operation/session/resource identity, fingerprint, TOCTOU, retry, replay,
   delegation and nested execution. Mark routes relevant to history, memory,
   RL, learning, confidence, trusted state, cached decisions, retries,
   reputation or prior success for a later habituation trace. Do not infer a
   global habituation verdict during partition.

The partition is `READ-ONLY`, `DRY-RUN`, with no code changes, patches, commits,
refactors, registry changes or auto-fixes. On a P0, scanner gap, inconsistent
inventory, changed candidate, unreproducible sink, unclassified material
effect, conflicting owners or `ExecutionGateway` bypass, stop and document the
evidence; do not repair it in the partition phase.

Use `PASS_FOR_PLANNING` only when the snapshot and scanner coverage are sound,
every runtime-unbound sink belongs to exactly one cluster, every cluster has a
target owner, any `NEW_OWNER` is justified, and dependencies, shared-core
conflicts and parallel lanes are complete. That verdict permits planning only;
it does not claim repairs or acceptance. The next phase is
`CRIT-BAGO-HABITUATION-01-RUNTIME-TRACE`. Do not start parallel repairs until
that trace closes and the user explicitly authorizes implementation.

Never optimize away findings with exclusions, ignore patterns, lowered
confidence or code movement. The question is which authority owns each effect.
