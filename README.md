# BAGO — Structured AI Work Framework

[![BAGO Code Health](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml)

> **Version 3.3.0** · 87 CLI commands · 222 tools · 18 operational workflows · Clean-install state: `healthy`

---

## 1. What BAGO is

**BAGO** (Balanceado · Adaptativo · Generativo · Organizativo) is a persistent operational layer for AI-assisted technical work.

It provides:
- A **stable CLI surface** for day-to-day operation
- **Operational workflows** (W0–W10) that constrain work into repeatable modes
- A clear separation between **versioned code** and **runtime state**
- **CI gates** that protect the public contract

This README is an **operational contract**. Historical benchmarks, marketing claims, and changelog-style sections are intentionally excluded.

---

## 2. Installation

**Requirements:** Python 3.9+ · No external dependencies (standard library only)

Primary installation method (editable install):

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .          # installs 'bago' console script
# or: alias bago='python3 /path/to/bago'
```

Minimal verification on a clean checkout:

```bash
bago validate
bago health
```

---

## 3. Core commands (stable, CI-tested)

These 12 commands form the **stable public interface**.

Contract:
- They are expected to remain stable across patch releases.
- They are covered by CI gate tests.
- They follow a `preflight_policy=required` contract.

| Command | Purpose |
|---|---|
| `bago health` | System health score (0–100) + stability report |
| `bago status` | Active flow, pending task, current health |
| `bago validate` | Consistency check: manifest + state + pack |
| `bago audit` | Session audit trail (full \| pack \| scan \| commit \| push) |
| `bago task` | Show/manage active W2 pending task |
| `bago flow` | Workflow lifecycle: start \| done \| status \| reset |
| `bago session` | Session lifecycle: open \| close \| harvest |
| `bago project` | Distributed project memory: init \| link \| status |
| `bago context` | Workspace context: detect \| map \| git \| stale |
| `bago sync` | Regenerate TREE.txt and CHECKSUMS |
| `bago scope` | Detect script scope (framework / project / both) |
| `bago secrets` | Scan repository for exposed credentials |

---

## 4. Experimental commands (not part of the contract)

These commands exist and may be useful, but they are **not contractual**:
- Behavior and flags may change.
- They are not covered by CI gate tests.

**Experimental (31):**

`ask` · `chronicle` · `config-check` · `dashboard` · `debt` · `deps` · `diff`
`find-tool` · `goals` · `habit` · `ideas` · `image-studio` · `image_gen` · `inbox` · `insights` · `llm` · `lsp`
`naming` · `next` · `reopen` · `repo` · `research` · `review` · `risk` · `rules`
`select` · `sprint` · `sprite-studio` · `types` · `why` · `workflow`

---

## 5. Dangerous commands (requires explicit flags)

These commands mutate state, spawn processes, or have irreversible effects.

Contract:
- They must require an explicit opt-in flag (examples: `--yes`, `--unsafe`).
- They must support safe exploration (`--dry-run`) when feasible.

| Command | Description | Required flag(s) |
|---|---|---|
| `auto` | Automatic evaluation + action loop | `--yes` |
| `autonomous` | Full SENSE→PLAN→ACT→OBSERVE→LEARN loop | `--yes` |
| `cabinet` | Multi-agent parallel orchestration | `--yes` |
| `db` | Manage `bago.db` (ideas state, guardian history) | `--yes` |
| `install` | Auto-launch on pendrive insert (macOS/Linux) | `--unsafe` |
| `orchestrate` | Multi-tool workflow sequencer | `--yes` |
| `peer` | LAN peer-to-peer communication | `--unsafe` |

Examples:

```bash
bago autonomous --dry-run
bago autonomous --yes
bago autonomous --loop --yes
```

---

## 6. Legacy commands (deprecated, redirect-only)

These commands are deprecated.

Contract:
- They exist for compatibility.
- They **redirect** to current equivalents.
- They are not developed further and may be removed in a future version.

**Legacy (28):**

`check` · `code-quality` · `commit` · `consistency` · `cosecha` · `detector`
`doctor` · `efficiency` · `git` · `heal` · `learn` · `map` · `pre-push`
`project-init` · `project-link` · `project-state` · `project-unlink` · `promote`
`repo-clone` · `repo-list` · `repo-switch` · `report` · `scan` · `session_close`
`sincerity` · `stability` · `stale` · `v2`

---

## 7. Workflows (W0–W10)

BAGO ships with **11 operational workflows** (W0–W10) plus an orchestration layer that can route between them.

| Workflow | Purpose |
|---|---|
| `W0 · Free Session` | Unstructured exploration |
| `W1 · Cold Start` | New project bootstrap |
| `W2 · Controlled Implementation` | Feature delivery with evidence |
| `W3 · Sensitive Refactor` | High-risk code changes |
| `W4 · Multi-cause Debug` | Complex bug investigation |
| `W5 · Closure & Continuity` | Session close + handoff |
| `W6 · Applied Ideation` | Innovation + idea management |
| `W7 · Session Focus` | Scoped single-objective sessions |
| `W8 · Exploration` | Research and discovery |
| `W9 · Cosecha` | Artifact harvest and consolidation |
| `W10 · Auditoría de Sinceridad` | Sincerity audit — detect unverified claims |

---

## 8. Runtime state (`state/` vs `state.example/`)

BAGO separates **versioned code** from **runtime state**.

```
.bago/state/           ← runtime (gitignored except templates)
  global_state.json    ← session, flow, health counters
  sessions/            ← per-session artifacts
  changes/             ← BAGO-CHG evidence records
  evidences/           ← validation evidence

.bago/state.example/   ← clean-install templates (versioned)
```

Contract:
- On a clean install, `bago validate` copies `state.example/` → `state/`.
- Runtime state is never included in the distributable pack.

Override paths:

```bash
BAGO_ROOT=/custom/path bago health
BAGO_STATE_DIR=/tmp/state bago validate
```

---

## 9. CI guarantees

The green badge means **all gate jobs pass**. Gate jobs fail hard (no `continue-on-error`).

| Gate | What it verifies |
|---|---|
| `gate-registry` | All 83 registry entries have valid `stability`, `risk`, `preflight_policy` |
| `gate-syntax` | All Python modules compile without error |
| `gate-security` | No `bandit` HIGH-severity findings |
| `gate-tests` | Core test suite passes (`pytest tests/ --ignore=tests/test_packaging.py`) |
| `gate-package` | Pack builds clean; no dist/, no state/, no binary blobs inside |
| `gate-validate` | `bago validate` exits 0 on a clean checkout |

Non-gate report jobs may run after gates and upload artifacts, but do not affect the badge.

---

## 10. Known limitations (honest)

- `--dry-run` is implemented for `autonomous` and `auto`. Not all mutating commands support it yet.
- `test_packaging.py` is excluded from `gate-tests` (runs separately in `gate-package` due to build time).
- Legacy commands redirect but do not validate their arguments before redirecting.
- Runtime state is in-memory for the event bus; events do not persist across process boundaries.
- The pack builder excludes `.bago/.models/` (LLM blobs) and `.bago/bin/` (binaries) — these must be obtained separately for full autonomous functionality.

---

## License

MIT — see [LICENSE](LICENSE)

---

*BAGO 3.3.0 · Built with BAGO · May 2026*
