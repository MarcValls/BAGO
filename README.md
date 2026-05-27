# BAGO CLI â€” Orquestador de IA Â· A.M. TECHNOLOGIES

[![BAGO Code Health](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/bago.yml)

> Version: 3.5.0b1 Â· 179 CLI commands Â· 144 public commands

Public command contract (CI-checked): **119 core** Â· **17 experimental** Â· **8 dangerous** Â· **30 legacy**

---

## Empieza aquÃ­

BAGO es un orquestador local-first para trabajar con modelos locales y cloud desde una sola CLI. Sirve para:

- hablar con BAGO y dejar que enrute a Ollama, GPT, Copilot, Claude u otros providers disponibles;
- mantener memoria de trabajo y `bago-knowledge`;
- sincronizar tu entorno con un dispositivo BAGO portable;
- gestionar proyectos, agentes, routing, validaciones y tareas de desarrollo.

InstalaciÃ³n rÃ¡pida:

```powershell
# Windows
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
.\install-bago.cmd
```

```bash
# macOS / Linux
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
./install-bago.sh
```

Si `bago` no aparece tras instalar, cierra y abre la terminal para refrescar el `PATH`.

Primer arranque:

```bash
bago
```

En el primer arranque BAGO detecta si hay un dispositivo BAGO conectado. Si existe, lo usa como fuente de verdad para credenciales y memoria. Si hay un pendrive sin BAGO, te ofrece convertirlo. Si no hay pendrive, te recomienda crear uno; como alternativa menos recomendada puedes usar un directorio local de credenciales.

```
             â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
             â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â•â• â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—
             â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘
             â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘
             â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•
             â•šâ•â•â•â•â•â• â•šâ•â•  â•šâ•â• â•šâ•â•â•â•â•â•  â•šâ•â•â•â•â•â•

             â£¾  INICIANDO DESDE EL DISPOSITIVO BAGO...
```

`bago launch` abre la interfaz conversacional. El usuario habla con BAGO; BAGO decide quÃ© motores internos usar.

```bash
bago                               # menÃº / primer arranque
bago launch                        # autodetecta provider
bago launch --provider copilot     # fuerza GitHub Copilot
bago launch --provider ollama      # fuerza Ollama local
bago launch --model qwen2.5:14b    # modelo especÃ­fico
bago portable detect               # detecta dispositivos BAGO
bago portable create E:            # crea un dispositivo BAGO en Windows
```

DocumentaciÃ³n:
[`INSTALL.md`](INSTALL.md) Â· [`QUICKSTART.md`](QUICKSTART.md) Â· [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) Â· [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md) Â· [`docs/SPONSORS.md`](docs/SPONSORS.md) Â· [`docs/INSTALL_DEEP.md`](docs/INSTALL_DEEP.md)

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

## 1. QuÃ© es BAGO CLI

**BAGO CLI** (Balanceado Â· Adaptativo Â· Generativo Â· Organizativo) es una **interfaz de lÃ­nea de comandos para desarrollo asistido por IA**, desarrollada por **A.M. TECHNOLOGIES**.

El comando principal es `bago launch`:

```
El usuario  â”€â”€â–º  BAGO  â”€â”€â–º  [Qwen / GPT / Claude / Llama / ...]
                  â–²                        â”‚
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
              BAGO recibe, decide y responde
```

Todos los modelos de IA son **motores internos** del framework. El usuario siempre habla con **BAGO**.

AdemÃ¡s del chat, BAGO CLI incluye:
- contexto persistente entre sesiones,
- estado de workflow y audit trail,
- 159 comandos registrados para desarrollo.

TambiÃ©n incluye un modelo local-first de rutas cognitivas: el sistema de workflows estÃ¡ definido como grafo (`.bago/workflows/WORKFLOW_GRAPH.json`) y el estado se puede separar/fusionar por capas (`state_manager --split/--materialize`) sin borrar historial.

This README is an **operational contract**.

---

## ðŸ” El Bucle de Shepard

> *Un tono de Shepard sube infinitamente sin llegar nunca al lÃ­mite. BAGO funciona igual.*

El **Bucle de Shepard** es el meta-ciclo que mantiene el framework en mejora continua. Cada iteraciÃ³n parece subir, y siempre sube â€” porque nunca para.

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                                                 â”‚
â”‚   SCAN â”€â”€â–¶ ALERT â”€â”€â–¶ REMEDIATE â”€â”€â–¶ VERIFY      â”‚
â”‚     â–²                                  â”‚        â”‚
â”‚     â””â”€â”€â”€â”€â”€â”€â”€â”€ EVOLVE â—€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜        â”‚
â”‚                                                 â”‚
â”‚  SCAN:      orphan_shield Â· file_size_guard     â”‚
â”‚  ALERT:     guardian_findings Â· health_score    â”‚
â”‚  REMEDIATE: heal Â· promote Â· cosecha Â· merge    â”‚
â”‚  VERIFY:    validate Â· sincerity Â· stability    â”‚
â”‚  EVOLVE:    siembra Â· spiral Â· autonomous       â”‚
â”‚                                                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
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

El bucle se ejecuta automÃ¡ticamente en el pre-push hook y en el guardian nocturno. TambiÃ©n puedes lanzarlo manualmente:

```bash
bago health monolith    # SCAN: monolitos
bago orphan-shield      # SCAN: huÃ©rfanos
bago health             # ALERT: score global
bago validate           # VERIFY: integridad
bago autonomous         # EVOLVE: ciclo autÃ³nomo
```

---

## PADRE / SIEMBRA

`bago siembra` planta una huella minima de BAGO en proyectos externos sin copiar todo el framework. La documentacion operativa vive en [`docs/siembras.md`](docs/siembras.md).

```bash
bago siembra create ../mi-proyecto
bago siembra status
bago siembra sync
```

---

## 2. Installation

**Requirements:** Python 3.10+ Â· Git Â· PowerShell en Windows

Usa los comandos de la secciÃ³n inicial. La ruta por defecto es `C:\Program Files\BAGO` en Windows y `~/.local/share/bago` en macOS/Linux. Puedes cambiarla con `-TargetRoot` en Windows o `BAGO_TARGET_ROOT` en macOS/Linux.

Security model and reporting: [SECURITY.md](SECURITY.md)

---

## 3. Core commands (stable, CI-tested)

These commands form the **stable public interface**.

| Command | Purpose |
|---|---|
| `bago launch` | **Main entry point** â€” talk to BAGO; BAGO orchestrates all agents internally |
| `bago health` | System health score (0â€“100) + stability report |
| `bago status` | Active flow, pending task, current health |
| `bago validate` | Consistency check: manifest + state + pack |
| `bago audit` | Session audit trail (full \| pack \| scan \| commit \| push) |
| `bago task` | Show/manage active W2 pending task |
| `bago flow` | Workflow lifecycle: start \| done \| status \| reset |
| `bago session` | Session lifecycle: open \| close \| harvest |
| `bago project` | Distributed project memory: init \| link \| status |
| `bago context` | Workspace context: detect \| map \| git \| stale |
| `bago supervision` | BAGO Supervision Layer â€” guardianes sistÃ©micos: versiones, tests, docs, registry |
| `bago sync` | Regenerate TREE.txt and CHECKSUMS |
| `bago scope` | Detect script scope (framework / project / both) |
| `bago secrets` | Scan repository for exposed credentials |
| `bago setup` | First-time setup wizard: Telegram, WhatsApp, ntfy config |
| `bago orphans` | Detect unregistered tool modules (orphan daemon) |
| `bago pack-cache` | Hybrid SQLite cache for `.bago/pack.json` |
| `bago doc-agent` | Documentation agent: update COMMANDS.md, LAYERS.md, README |
| `bago devmode` | Toggle developer mode: unlock advanced tools and preflight checks |
| `bago self` | BAGO introspection: identity, version, capabilities |
| `bago menu` | Interactive hierarchical command menu (curses UI) |
| `bago workspace-select` | Select active workspace: framework / parent dir / external repo |
| `bago recent-projects` | History of recent BAGO projects and sessions |
| `bago ask` | Natural language router â†’ BAGO tools (CONSUMO) |
| `bago ideas` | W2 ideas loop â€” central to the BAGO workflow (MEMORIA) |
| `bago sprint` | Sprint management: create, list, close (MEMORIA) |
| `bago goals` | Project objectives with progress tracking (MEMORIA) |
| `bago dashboard` | Pack dashboard: health, velocity, risks (MEMORIA) |
| `bago dashboard --public` | Public-facing dashboard summary for demos and release notes |
| `bago route` | Hybrid LLM router: local â†” cloud (MOTOR) |
| `bago review` | Automated fail-closed code review (GENERACIÃ“N) |
| `bago docs` | Generate COMMANDS.md from registry (GENERACIÃ“N) |
| `bago version` | Version management: bump \| beta \| release \| tag (MEMORIA) |
| `bago version-check` | Version Truth Lock: check | sync <ver> | audit --json |
| `bago bootstrap-state` | Bootstrap clean runtime state from template |
| `bago git-dirty` | Detect git dirty state: --json |
| `bago test` | Run pytest suite |
| `bago integrity` | Full integrity sensor sweep: --json |
| `bago workflow` | Interactive workflow selector (MOTOR) |
| `bago next` | Meta-cycle: pick top idea + open task (MOTOR) |
| `bago advisor` | Adaptive LLM advisor: ask \| next \| explain \| run (GENERACIÃ“N) |
| `bago snapshot` | Compare two BAGO state snapshots (MEMORIA) |
| `bago why` | Explain what a BAGO command does and when to use it (GENERACIÃ“N) |
| `bago diff` | Show files modified between last BAGO sessions (CONSUMO) |
| `bago risk` | Project risk matrix: impact Ã— probability (MEMORIA) |

---

## 4. Dangerous commands (requires explicit flags)

| Command | Description | Required flag(s) |
|---|---|---|
| `auto` | Automatic evaluation + action loop | `--yes` or `--unsafe` |
| `autonomous` | Full SENSEâ†’PLANâ†’ACTâ†’OBSERVEâ†’LEARN loop | `--yes` or `--unsafe` |
| `cabinet` | Multi-agent parallel orchestration | `--yes` or `--unsafe` |
| `db` | Manage `bago.db` (ideas state, guardian history) | `--yes` or `--unsafe` |
| `install` | Auto-launch on pendrive insert (macOS/Linux) | `--yes` or `--unsafe` |
| `orchestrate` | Multi-tool workflow sequencer | `--yes` or `--unsafe` |
| `peer` | LAN peer-to-peer communication | `--yes` or `--unsafe` |
| `spiral` | Bucle espiral cromÃ¡tico: 12 pasos de auto-redescripciÃ³n AGI | `--yes` or `--unsafe` |

---

## 5. Legacy commands (deprecated, redirect-only)

`check` Â· `code-quality` Â· `commit` Â· `consistency` Â· `cosecha` Â· `detector` Â· `doctor` Â· `efficiency` Â· `git` Â· `heal` Â· `learn` Â· `map` Â· `pre-push` Â· `project-init` Â· `project-link` Â· `project-state` Â· `project-unlink` Â· `promote` Â· `repo-clone` Â· `repo-list` Â· `repo-switch` Â· `report` Â· `scan` Â· `session_close` Â· `sincerity` Â· `stability` Â· `stale` Â· `v2`

---

## 6. Experimental commands (not part of the contract)

Usa `BAGO_LABS=1` para suprimir avisos. Ver `docs/COMMANDS.md` para la lista completa generada desde el registry.

Marketing/demo helpers: `bago publish-kit` genera textos de publicacion beta/stable y `bago demo` muestra las entradas publicas disponibles. `publish-kit` esta promovido al contrato estable; `demo` sigue experimental porque no tiene autotest dedicado.

Siguen experimentales: `agent` Â· `agent-config` Â· `canon` Â· `deactivate` Â· `demo` Â· `field` Â· `gateway` Â· `infra-scan` Â· `instance` Â· `lint-runner` Â· `list` Â· `music` Â· `music-saas` Â· `net-scan` Â· `notify-whatsapp` Â· `script-runner` Â· `toolsmith`.

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

## 7. Workflows (W0â€“W10)

BAGO ships with **11 operational workflows** (W0â€“W10).

| Workflow | Purpose |
|---|---|
| `W0 Â· Free Session` | Unstructured exploration |
| `W1 Â· Cold Start` | New project bootstrap |
| `W2 Â· Controlled Implementation` | Feature delivery with evidence |
| `W3 Â· Sensitive Refactor` | High-risk code changes |
| `W4 Â· Multi-cause Debug` | Complex bug investigation |
| `W5 Â· Closure & Continuity` | Session close + handoff |
| `W6 Â· Applied Ideation` | Innovation + idea management |
| `W7 Â· Session Focus` | Scoped single-objective sessions |
| `W8 Â· Exploration` | Research and discovery |
| `W9 Â· Cosecha` | Artifact harvest and consolidation |
| `W10 Â· AuditorÃ­a de Sinceridad` | Sincerity audit â€” detect unverified claims |

---

## 8. Domain workflows

| Domain workflow | Purpose |
|---|---|
| [Music score transposition pipeline](docs/music-score-transposition-pipeline.md) | Parse or recognize a score, select a target, transpose only that target, and reconstruct the full score. |
| [Music score transposition operational workflow](.bago/workflows/music-score-transposition.md) | Operational checklist for route selection and validation honesty. |

## 9. Example projects

Real projects built with BAGO workflows (W1 â†’ W2 cycles, tracked via `bago ideas` + `bago next`):

| Project | Description |
|---|---|
| [ISO_GAME](https://github.com/MarcValls/ISO_GAME) | Isometric game world pipeline in Python â€” A* pathfinding, pygame renderer, autotile, chunking, lighting. Built in 12 pipeline steps across W2 sessions. |
| [BAGO_MUSIC_PIPELINE](https://github.com/MarcValls/BAGO_MUSIC_PIPELINE) | Music score pipeline â€” PDF/MIDI/MusicXML transposition engine, Karpovich + Disc Superstar synths, Ableton Live integration, MIDI device setup (loopMIDI + teVirtualMIDI). |
| [BAGO_TELEGRAM_BOT](https://github.com/MarcValls/BAGO_TELEGRAM_BOT) | Full-featured Telegram bot â€” inline keyboards, task management, intent detection, MiniApp, WhatsApp + ntfy notifications. |
| [BAGO_SPRITE_STUDIO](https://github.com/MarcValls/BAGO_SPRITE_STUDIO) | Procedural sprite generator for games â€” HF Spaces / Codex CLI backends, animation sheets, gallery. No API key required. |
| [BAGO_WALLET_TRACKER](https://github.com/MarcValls/BAGO_WALLET_TRACKER) | Read-only crypto portfolio tracker + TON airdrop scanner. CoinGecko live prices, zero-custody model, stdlib only. |
| [BAGO_NEURAL_FABRIC](https://github.com/MarcValls/BAGO_NEURAL_FABRIC) | Dynamic agent orchestration engine â€” SENSE/PLAN/ACT/OBSERVE/LEARN/DECIDE loop, dot-product tool activation, intent routing. |
| [BAGO_WINDOWS_AUTOMATION](https://github.com/MarcValls/BAGO_WINDOWS_AUTOMATION) | Battle-tested Windows automation â€” Win32 mouse simulation, UAC auto-elevation, Task Scheduler, MIDI/ASIO audio setup. |
| [BIANCA_THE_GAME](https://github.com/MarcValls/BIANCA_THE_GAME) | Narrative game engine â€” BIANCA: La Tejedora de Universos. 47 visual FX, procedural sprites, AudioManager (9 SFX), literary worlds. |

---

## 10. Runtime state (`state/` vs `state.example/`)

BAGO separates **versioned code** from **runtime state**.

```text
.bago/state/           â† runtime (gitignored except templates)
.bago/state.example/   â† clean-install templates (versioned)
```

---

## 11. CI guarantees

A green badge means all **gate jobs** pass hard (no `continue-on-error`).

---

## License

MIT â€” see [LICENSE](LICENSE)

---

*BAGO 3.4.4 Â· Built with BAGO Â· May 2026*


## InstalaciÃ³n en disco local

- Disco: C:\bago_true
- USB: E:\bago_fw
- Sync: python .bago/tools/bago_sync_bidirectional.py
