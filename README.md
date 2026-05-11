# BAGO — Structured AI Work Framework

[![BAGO Code Health](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml)

> **Version 3.4.0b1** · 110 CLI commands · 77 public commands

Public command contract (CI-checked): **12 core** · **58 experimental** · **7 dangerous** · **28 legacy**

---

## Quick start

```bash
bago validate     # verify clean install
bago status       # active flow + pending task + health
bago next         # pick highest-priority idea and open a task
# <implement>
bago health       # verify nothing broke
bago done         # close task, record evidence
bago audit full   # session audit trail
```

---

## 1. What BAGO is

**BAGO** (Balanceado · Adaptativo · Generativo · Organizativo) is a **repo-local operating layer for AI-assisted development**.

It keeps:
- persistent context,
- workflow state,
- and audit trail
between agent sessions.

También incluye un modelo local-first de rutas cognitivas: el sistema de workflows está definido como grafo (`.bago/workflows/WORKFLOW_GRAPH.json`) y el estado se puede separar/fusionar por capas (`state_manager --split/--materialize`) sin borrar historial.

This README is an **operational contract**.

---

## 2. Installation

**Requirements:** Python 3.9+ · No external dependencies in core runtime (stdlib-only)

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .
bago validate
```

- Security model and reporting: [SECURITY.md](SECURITY.md)

---

## 3. Core commands (stable, CI-tested)

These commands form the **stable public interface**.

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

## 4. Dangerous commands (requires explicit flags)

| Command | Description | Required flag(s) |
|---|---|---|
| `auto` | Automatic evaluation + action loop | `--yes` |
| `autonomous` | Full SENSE→PLAN→ACT→OBSERVE→LEARN loop | `--yes` |
| `cabinet` | Multi-agent parallel orchestration | `--yes` |
| `db` | Manage `bago.db` (ideas state, guardian history) | `--yes` |
| `install` | Auto-launch on pendrive insert (macOS/Linux) | `--unsafe` |
| `orchestrate` | Multi-tool workflow sequencer | `--yes` |
| `peer` | LAN peer-to-peer communication | `--unsafe` |

---

## 5. Legacy commands (deprecated, redirect-only)

`check` · `code-quality` · `commit` · `consistency` · `cosecha` · `detector`
`doctor` · `efficiency` · `git` · `heal` · `learn` · `map` · `pre-push`
`project-init` · `project-link` · `project-state` · `project-unlink` · `promote`
`repo-clone` · `repo-list` · `repo-switch` · `report` · `scan` · `session_close`
`sincerity` · `stability` · `stale` · `v2`

---

## 6. Experimental commands (not part of the contract)

`ableton-template` · `advisor` · `agent` · `ask` · `autonomy` · `build-clean` · `build-run` · `chronicle` · `config-check` · `dashboard` · `deactivate` · `debt` · `deps` · `diff`
`docs` · `find-tool` · `goals` · `habit` · `hardcode` · `heal-paths` · `ideas` · `image-studio` · `image_gen` · `inbox` · `insights` · `llm` · `llm-node` · `lsp` · `music`
`naming` · `neural` · `next` · `notify-bago` · `notify-desktop` · `notify-whatsapp` · `npath` · `preflight-check` · `recientes` · `reopen` · `repo` · `research` · `review` · `risk` · `route` · `rubber-duck` · `rules`
`select` · `siembra` · `snapshot` · `spanish` · `sprint` · `sprite-studio` · `toolsmith` · `types` · `version` · `why` · `work_matrix` · `workflow`

---

## 6.1 Review reports (`bago review`)

`bago review` is the canonical review entrypoint for local checks and PR-oriented reports.

```bash
# Local machine-readable report
bago review . --format json

# PR-friendly markdown artifact
bago review . --format md --out bago-review.md

# Review only files changed against a base ref
bago review . --changed-only --base origin/main --format md

# CI gate: stricter threshold + fail unless mergeable
bago review . --ci --changed-only --base origin/main --format json

# Include external SARIF / CodeQL findings in the same report
bago review . --sarif results.sarif --format md --out bago-review.md
```

---

## 7. Workflows (W0–W10)

BAGO ships with **11 operational workflows** (W0–W10).

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

## 8. Domain workflows

| Domain workflow | Purpose |
|---|---|
| [Music score transposition pipeline](docs/music-score-transposition-pipeline.md) | Parse or recognize a score, select a target, transpose only that target, and reconstruct the full score. |
| [Music score transposition operational workflow](.bago/workflows/music-score-transposition.md) | Operational checklist for route selection and validation honesty. |

---

## 9. Runtime state (`state/` vs `state.example/`)

BAGO separates **versioned code** from **runtime state**.

```text
.bago/state/           ← runtime (gitignored except templates)
.bago/state.example/   ← clean-install templates (versioned)
```

---

## 10. CI guarantees

A green badge means all **gate jobs** pass hard (no `continue-on-error`).

---

## License

MIT — see [LICENSE](LICENSE)

---

*BAGO 3.4.0b1 · Built with BAGO · May 2026*
