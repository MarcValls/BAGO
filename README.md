# BAGO CLI — Orquestador de IA · A.M. TECHNOLOGIES

[![BAGO Code Health](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml)

> **Version 3.4.0b1** · 158 CLI commands · 125 public commands

Public command contract (CI-checked): **9 core** · **146 experimental** · **1 dangerous** · **0 legacy**

---

## 🚀 Empieza aquí

```bash
bago launch       # abre el chat con BAGO — orquestador central
```

```
             ██████╗  █████╗  ██████╗  ██████╗
             ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗
             ██████╔╝███████║██║  ███╗██║   ██║
             ██╔══██╗██╔══██║██║   ██║██║   ██║
             ██████╔╝██║  ██║╚██████╔╝╚██████╔╝
             ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝

             ⣾  INICIANDO DESDE EL DISPOSITIVO BAGO...
```

`bago launch` abre la **interfaz conversacional** donde el usuario habla directamente con **BAGO**.  
BAGO orquesta todos los modelos de IA internamente — el usuario nunca habla con los modelos directamente.

```bash
bago launch                        # autodetecta provider
bago launch --provider copilot     # fuerza GitHub Copilot
bago launch --provider ollama      # fuerza Ollama local
bago launch --model qwen2.5:14b    # modelo específico
```

> **📖 Documentación completa:** [`docs/BAGO_LAUNCH.md`](docs/BAGO_LAUNCH.md) · [`docs/SLASH_MENU.md`](docs/SLASH_MENU.md)

---

## Otros comandos frecuentes

```bash
bago validate     # verify clean install
bago status       # active flow + pending task + health
bago next         # pick highest-priority idea and open a task
bago health       # verify nothing broke
bago done         # close task, record evidence
bago audit full   # session audit trail
```

---

## 1. Qué es BAGO CLI

**BAGO CLI** (Balanceado · Adaptativo · Generativo · Organizativo) es una **interfaz de línea de comandos para desarrollo asistido por IA**, desarrollada por **A.M. TECHNOLOGIES**.

El comando principal es `bago launch`:

```
El usuario  ──►  BAGO  ──►  [Qwen / GPT / Claude / Llama / ...]
                  ▲                        │
                  └────────────────────────┘
              BAGO recibe, decide y responde
```

Todos los modelos de IA son **motores internos** del framework. El usuario siempre habla con **BAGO**.

Además del chat, BAGO CLI incluye:
- contexto persistente entre sesiones,
- estado de workflow y audit trail,
- 150 comandos especializados para desarrollo.

También incluye un modelo local-first de rutas cognitivas: el sistema de workflows está definido como grafo (`.bago/workflows/WORKFLOW_GRAPH.json`) y el estado se puede separar/fusionar por capas (`state_manager --split/--materialize`) sin borrar historial.

This README is an **operational contract**.

---

## 🔁 El Bucle de Shepard

> *Un tono de Shepard sube infinitamente sin llegar nunca al límite. BAGO funciona igual.*

El **Bucle de Shepard** es el meta-ciclo que mantiene el framework en mejora continua. Cada iteración parece subir, y siempre sube — porque nunca para.

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   SCAN ──▶ ALERT ──▶ REMEDIATE ──▶ VERIFY      │
│     ▲                                  │        │
│     └──────── EVOLVE ◀─────────────────┘        │
│                                                 │
│  SCAN:      orphan_shield · file_size_guard     │
│  ALERT:     guardian_findings · health_score    │
│  REMEDIATE: heal · promote · cosecha · merge    │
│  VERIFY:    validate · sincerity · stability    │
│  EVOLVE:    siembra · spiral · autonomous       │
│                                                 │
└─────────────────────────────────────────────────┘
```

Cada nodo del bucle tiene su herramienta:

| Fase | Comando | Script |
|------|---------|--------|
| SCAN | `bago orphan-shield` | `orphan_shield.py` |
| SCAN | `bago size-check` | `file_size_guard.py` |
| ALERT | `bago health` | `health/` |
| ALERT | `bago stale` | `stale_detector.py` |
| REMEDIATE | `bago heal` | `auto_heal.py` |
| REMEDIATE | `bago cosecha` | `cosecha.py` |
| VERIFY | `bago validate` | `validate.py` |
| VERIFY | `bago sincerity` | `sincerity_detector.py` |
| EVOLVE | `bago siembra` | `siembra_manager.py` |
| EVOLVE | `bago spiral` | `spiral_loop.py` |
| EVOLVE | `bago autonomous` | `autonomous_loop.py` |

El bucle se ejecuta automáticamente en el pre-push hook y en el guardian nocturno. También puedes lanzarlo manualmente:

```bash
bago health monolith    # SCAN: monolitos
bago orphan-shield      # SCAN: huérfanos
bago health             # ALERT: score global
bago validate           # VERIFY: integridad
bago autonomous         # EVOLVE: ciclo autónomo
```

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
| `bago launch` | **Main entry point** — talk to BAGO; BAGO orchestrates all agents internally |
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
| `bago setup` | First-time setup wizard: Telegram, WhatsApp, ntfy config |
| `bago orphans` | Detect unregistered tool modules (orphan daemon) |
| `bago doc-agent` | Documentation agent: update COMMANDS.md, LAYERS.md, README |
| `bago devmode` | Toggle developer mode: unlock advanced tools and preflight checks |
| `bago self` | BAGO introspection: identity, version, capabilities |
| `bago launch` | Launch BAGO daemon or background services |
| `bago menu` | Interactive hierarchical command menu (curses UI) |
| `bago workspace-select` | Select active workspace: framework / parent dir / external repo |
| `bago recent-projects` | History of recent BAGO projects and sessions |

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
| `spiral` | Bucle espiral cromático: 12 pasos de auto-redescripción AGI | `--execute` |

---

## 5. Legacy commands (deprecated, redirect-only)

`check` · `code-quality` · `commit` · `consistency` · `cosecha` · `detector` · `doctor` · `efficiency` · `git` · `heal` · `learn` · `map` · `pre-push` · `project-init` · `project-link` · `project-state` · `project-unlink` · `promote` · `repo-clone` · `repo-list` · `repo-switch` · `report` · `scan` · `session_close` · `sincerity` · `stability` · `stale` · `v2`

---

## 6. Experimental commands (not part of the contract)

`ableton-template` · `advisor` · `agent` · `agent-config` · `gateway` · `alias-manager` · `artifact-counter` · `ask` · `assign` · `autonomy` · `benchmark` · `boot` · `build-clean` · `build-run` · `canon` · `chronicle` · `code-metrics` · `code-search`
- `music-saas` — CLI para BAGO Music SaaS (status/dev/webhook/test/open/build/config)
`config-check` · `create` · `dashboard` · `deactivate` · `debt` · `deps` · `diff` · `doc-index` · `docs` · `env-manager` · `field` · `find-tool` · `focus-mode` · `git-status` · `goals` · `habit` · `hardcode`
`heal-paths` · `html-export` · `ideas` · `image-studio` · `image_gen` · `inbox` · `insights` · `lint-runner` · `llm` · `llm-node` · `log-viewer` · `lsp` · `music` · `naming` · `net-scan`
`neural` · `neural-toolbox` · `next` · `notify-bago` · `notify-desktop` · `notify-whatsapp` · `npath` · `orphan-shield` · `personality-panel` · `ping-server` · `placeholder_scan` · `preflight-check` · `project-summary` · `recientes` · `reopen`
`repo` · `research` · `review` · `risk` · `route` · `rubber-duck` · `rules` · `safeguard` · `script-runner` · `search-history` · `seed` · `select` · `siembra` · `size-check` · `skill` · `snapshot`
`spanish` · `spiral-agent` · `sprint` · `sprite-studio` · `state-manager` · `template-gen` · `toolsmith` · `types` · `version` · `weekly-report` · `why` · `work_matrix` · `workflow` · `workflow-navigator`

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

## 9. Example projects

Real projects built with BAGO workflows (W1 → W2 cycles, tracked via `bago ideas` + `bago next`):

| Project | Description |
|---|---|
| [ISO_GAME](https://github.com/MarcValls/ISO_GAME) | Isometric game world pipeline in Python — A* pathfinding, pygame renderer, autotile, chunking, lighting. Built in 12 pipeline steps across W2 sessions. |
| [BAGO_MUSIC_PIPELINE](https://github.com/MarcValls/BAGO_MUSIC_PIPELINE) | Music score pipeline — PDF/MIDI/MusicXML transposition engine, Karpovich + Disc Superstar synths, Ableton Live integration, MIDI device setup (loopMIDI + teVirtualMIDI). |
| [BAGO_TELEGRAM_BOT](https://github.com/MarcValls/BAGO_TELEGRAM_BOT) | Full-featured Telegram bot — inline keyboards, task management, intent detection, MiniApp, WhatsApp + ntfy notifications. |
| [BAGO_SPRITE_STUDIO](https://github.com/MarcValls/BAGO_SPRITE_STUDIO) | Procedural sprite generator for games — HF Spaces / Codex CLI backends, animation sheets, gallery. No API key required. |
| [BAGO_WALLET_TRACKER](https://github.com/MarcValls/BAGO_WALLET_TRACKER) | Read-only crypto portfolio tracker + TON airdrop scanner. CoinGecko live prices, zero-custody model, stdlib only. |
| [BAGO_NEURAL_FABRIC](https://github.com/MarcValls/BAGO_NEURAL_FABRIC) | Dynamic agent orchestration engine — SENSE/PLAN/ACT/OBSERVE/LEARN/DECIDE loop, dot-product tool activation, intent routing. |
| [BAGO_WINDOWS_AUTOMATION](https://github.com/MarcValls/BAGO_WINDOWS_AUTOMATION) | Battle-tested Windows automation — Win32 mouse simulation, UAC auto-elevation, Task Scheduler, MIDI/ASIO audio setup. |
| [BIANCA_THE_GAME](https://github.com/MarcValls/BIANCA_THE_GAME) | Narrative game engine — BIANCA: La Tejedora de Universos. 47 visual FX, procedural sprites, AudioManager (9 SFX), literary worlds. |

---

## 10. Runtime state (`state/` vs `state.example/`)

BAGO separates **versioned code** from **runtime state**.

```text
.bago/state/           ← runtime (gitignored except templates)
.bago/state.example/   ← clean-install templates (versioned)
```

---

## 11. CI guarantees

A green badge means all **gate jobs** pass hard (no `continue-on-error`).

---

## License

MIT — see [LICENSE](LICENSE)

---

*BAGO unknown · Built with BAGO · May 2026*
