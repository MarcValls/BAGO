# BAGO — Structured AI Work Framework

[![BAGO Code Health](https://github.com/MarcValls/BAGO_v3.1/actions/workflows/bago.yml/badge.svg)](https://github.com/MarcValls/BAGO_v3.1/actions/workflows/bago.yml)

> **Version 3.1** · 83 CLI commands · 207 tools · 17 operational workflows · Clean-install state: `healthy`

---

**BAGO** (Balanceado · Adaptativo · Generativo · Organizativo) is an operational framework that brings structure, traceability, and continuity to AI-assisted technical work.

It works as a **persistent operational layer** alongside any AI agent (GitHub Copilot, Claude, GPT) — keeping context alive across sessions, enforcing structured workflows, and recording every decision and change.

---

## Installation

**Requirements:** Python 3.9+ · No external dependencies (standard library only)

```bash
git clone https://github.com/MarcValls/BAGO_v3.1.git
cd BAGO_v3.1
pip install -e .          # installs 'bago' console script
# or: alias bago='python3 /path/to/bago'
```

Verify clean install:

```bash
bago validate
bago health
```

---

## Core Commands (stable)

These 12 commands form the stable public interface. They are tested on every CI run and have a `preflight_policy=required` contract.

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

```bash
# Minimum working session
bago status               # what is the current state?
bago flow start W2 "task description"
# ... work ...
bago flow done
bago audit
```

---

## Experimental Commands

These commands work but may change. Not covered by CI gate-tests. Use with awareness.

`ask` · `chronicle` · `config-check` · `dashboard` · `debt` · `deps` · `diff`
`find-tool` · `goals` · `habit` · `ideas` · `inbox` · `insights` · `llm` · `lsp`
`naming` · `next` · `reopen` · `repo` · `research` · `review` · `risk` · `rules`
`select` · `sprint` · `types` · `why` · `workflow`

---

## Dangerous Commands

These commands mutate state, spawn processes, or have irreversible effects.
They require `--yes`, `--unsafe`, or explicit confirmation before executing.

| Command | Description | Requires |
|---|---|---|
| `auto` | Automatic evaluation + action loop | `--yes` |
| `autonomous` | Full SENSE→PLAN→ACT→OBSERVE→LEARN loop | `--yes` |
| `cabinet` | Multi-agent parallel orchestration | `--yes` |
| `db` | Manage bago.db: ideas state, guardian history | `--yes` |
| `install` | Auto-launch on pendrive insert (macOS/Linux) | `--unsafe` |
| `orchestrate` | Multi-tool workflow sequencer | `--yes` |
| `peer` | LAN peer-to-peer communication | `--unsafe` |

```bash
bago autonomous --dry-run       # safe: plan only, no mutations
bago autonomous --yes           # run one autonomous cycle
bago autonomous --loop --yes    # run until quiescent
```

---

## Legacy Commands

These commands are deprecated. They redirect to their current equivalents.
Not developed further. Will be removed in a future version.

`check` · `code-quality` · `commit` · `consistency` · `cosecha` · `detector`
`doctor` · `efficiency` · `git` · `heal` · `learn` · `map` · `pre-push`
`project-init` · `project-link` · `project-state` · `project-unlink` · `promote`
`repo-clone` · `repo-list` · `repo-switch` · `report` · `scan` · `session_close`
`sincerity` · `stability` · `stale` · `v2` · `validate`

---

## Workflows

BAGO ships with **11 operational workflows** (W0–W10) plus an orchestration layer (`WORKFLOW_MAESTRO_BAGO`) that routes between them automatically.

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

## Runtime State

BAGO separates **versionable code** from **runtime state**:

```
.bago/state/           ← runtime (gitignored except templates)
  global_state.json    ← session, flow, health counters
  sessions/            ← per-session artifacts
  changes/             ← BAGO-CHG evidence records
  evidences/           ← validation evidence

.bago/state.example/   ← clean-install templates (versioned)
```

On a clean install, `bago validate` copies `state.example/` → `state/` automatically.
State from previous sessions is never included in the distributable pack.

Override paths:
```bash
BAGO_ROOT=/custom/path bago health
BAGO_STATE_DIR=/tmp/state bago validate
```

---

## CI Guarantees

The green badge means **all gate jobs pass**. Gate jobs fail hard (no `continue-on-error`):

| Gate | What it checks |
|---|---|
| `gate-registry` | All 83 registry entries have valid `stability`, `risk`, `preflight_policy` |
| `gate-syntax` | All Python modules compile without error |
| `gate-security` | No `bandit` HIGH-severity findings |
| `gate-tests` | All 36 core tests pass (`pytest tests/ --ignore=tests/test_packaging.py`) |
| `gate-package` | Pack builds clean; no dist/, no state/, no binary blobs inside |
| `gate-validate` | `bago validate` exits 0 on a clean checkout |

Report jobs (`report-health`, `report-audit`) run after gates and upload artifacts but do not affect the badge.

---

## Architecture

```
bago-framework/
├── bago                    ← CLI entry point (Python 3, no deps)
├── bago_core/              ← pip-installable package (bago console script)
├── pyproject.toml          ← pip install -e . support
├── tests/                  ← 36 core tests (gate-tests CI)
└── .bago/
    ├── pack.json           ← manifest + version
    ├── AGENT_START.md      ← AI agent entry point
    ├── core/               ← preflight_engine, command_contract, runtime, paths
    ├── tools/              ← tool modules + tool_registry (single source of truth)
    ├── workflows/          ← W0–W10 + orchestration layer
    ├── roles/              ← Role definitions (9 agents)
    ├── state.example/      ← Clean-install templates
    └── state/              ← Runtime state (gitignored)
```

### Using with an AI agent

Point your AI agent (GitHub Copilot, Claude, etc.) to `.bago/AGENT_START.md` as context:

```
Read .bago/AGENT_START.md first. Then proceed with the task.
```

---

## Known Limitations

- `--dry-run` is implemented for `autonomous` and `auto`. Not all `mutating` commands support it yet.
- `test_packaging.py` is excluded from `gate-tests` (runs separately in `gate-package` due to build time).
- Legacy commands redirect but do not validate their arguments before redirecting.
- Runtime state is in-memory for the event bus; events do not persist across process boundaries.
- The pack builder excludes `.bago/.models/` (LLM blobs) and `.bago/bin/` (binaries) — these must be obtained separately for full autonomous functionality.

---

## License

MIT — see [LICENSE](LICENSE)

---

*BAGO 3.1 · Built with BAGO · May 2026*
