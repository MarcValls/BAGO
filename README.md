# BAGO — Structured AI Work Framework

[![BAGO Code Health](https://github.com/MarcValls/BAGO_v3.1/actions/workflows/bago.yml/badge.svg)](https://github.com/MarcValls/BAGO_v3.1/actions/workflows/bago.yml)

> **Version 3.1** · 83 CLI commands · 203 tools · 17 operational workflows · Clean-install state: `healthy`

---

**BAGO** (Balanceado · Adaptativo · Generativo · Organizativo) is an operational framework that brings structure, traceability, and continuity to AI-assisted technical work.

It works as a **persistent operational layer** alongside any AI agent (GitHub Copilot, Claude, GPT) — keeping context alive across sessions, enforcing structured workflows, and recording every decision and change.

---

## ¿Qué resuelve? / What does it solve?

| Problema / Problem | Sin BAGO / Without BAGO | Con BAGO / With BAGO |
|---|---|---|
| Pérdida de contexto entre sesiones | El agente no recuerda el estado anterior | Estado persistente: la sesión arranca con contexto completo |
| Arranques improvisados | El agente empieza sin rol ni protocolo | `bago health` + workflow selector antes de cada sesión |
| Cambios sin rastro | Los cambios se hacen sin documentar | Cada cambio genera un artefacto BAGO-CHG con evidencia |
| Deriva entre estado y código | El estado declarado no refleja la realidad | `bago validate` comprueba consistencia en tiempo real |
| Ideas sin gestión | Las mejoras se pierden | `bago ideas` con selector de prioridad y registro de implementadas |

---

## Capabilities at a glance

```
python3 bago health       # System health score (0–100)
python3 bago validate     # Consistency check: manifest + state + pack
python3 bago ideas        # Prioritized idea selector (scored 0–100)
python3 bago task         # Active task management
python3 bago stability    # Full stability report (smoke + VM + soak)
python3 bago workflow     # Workflow inspector
python3 bago efficiency   # Cross-version efficiency metrics
python3 bago audit        # Session audit trail
python3 bago dashboard    # System overview
python3 bago cosecha      # Session harvest (artifacts + decisions)
python3 bago session      # Session opener with context
python3 bago detector     # Context drift detector
python3 bago stale        # Stale task alert
python3 bago sincerity    # Sincerity audit — detects unverified status claims
python3 bago cabinet      # Multi-agent governance cabinet review
```

---

## Evolution — Proven Growth

BAGO has been built using BAGO itself. The following data was collected with `python3 bago efficiency`:

| Version | CLI Commands | Tools | Docs | Workflows | Efficiency Index |
|---|:---:|:---:|:---:|:---:|:---:|
| **2.3-clean** *(baseline)* | 10 | 19 | 68 | 12 | 78.6 |
| **2.4-v2rc** *(Dynamic BAGO)* | 10 | 27 | 73 | 12 | 89.3 |
| **2.5-stable** *(historic)* | **35** | **111** | **77** | **20** | **100.0** |
| **3.1** *(current)* | **83** | **203** | — | **17** | **—** |

**Growth up to 3.1** — measured by weighted index (commands ×0.30, tools ×0.35, docs ×0.20, workflows ×0.15).

> Workflow count in the evolution table (12) includes all files in `.bago/workflows/`: 10 operational workflows + `WORKFLOW_MAESTRO_BAGO.md` + `WORKFLOWS_INDEX.md`.
> The evolution table is **historical benchmark data** measured at each release date. For current health status, see the CI badge above or run `python3 bago health`. These numbers are not live — they reflect point-in-time snapshots and carry no guarantee about the current state of the codebase.

### New in 3.1

**New CLI commands:** `autonomous`, `inbox`

**New core modules:** `autonomous_loop.py`, `learning_writer.py`

**Architecture:** SENSE/PLAN/ACT/OBSERVE/LEARN/DECIDE loop · El Aprendiz (auto-pattern promotion) · BagoContext singleton · Tool-Agent Binding · Agent Dispatcher

**Bug fixes:** audit_v2 health parse · stale_detector timezone TypeError

---

### New in 2.5-stable

**New CLI commands:** `efficiency`, `task`, `stability`, `session`, `sincerity`, `cabinet`

**New tools:**
`audit_v2.py` · `dashboard_v2.py` · `efficiency_meter.py` · `health_score.py` · `reconcile_state.py` · `session_opener.py` · `show_task.py` · `stale_detector.py` · `v2_close_checklist.py` · `vertice_activator.py` · `workflow_selector.py` · `sincerity_detector.py` · `cabinet_orchestrator.py`

---

## Workflows

BAGO ships with **11 operational workflows** (W0–W10) for different types of work, plus a master orchestration protocol (`WORKFLOW_MAESTRO_BAGO`) that routes between them automatically based on session context.

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

> The `.bago/workflows/` directory also contains `WORKFLOW_MAESTRO_BAGO.md` (the orchestration layer) and `WORKFLOWS_INDEX.md` (reference index) — these are system-level protocols, not user-facing workflows.

---

## Quick Start

> 📖 **New user?** See [QUICKSTART.md](QUICKSTART.md) for the full step-by-step guide in Spanish.

### Requirements
- Python 3.9+
- No external dependencies (standard library only for core)

### Installation

```bash
# Clone or download
git clone https://github.com/MarcValls/bago-framework.git
cd bago-framework

# Verify the system
python3 bago validate

# Check current health status
# On a clean install, the initial state is "initializing"
python3 bago health
```

### First session

```bash
# 1. Check stability before working
python3 bago stability

# 2. See prioritized ideas
python3 bago ideas

# 3. Start working with a workflow
# The agent will use .bago/AGENT_START.md as its entry point

# 4. After work: audit and harvest
python3 bago audit
python3 bago cosecha
```

### Flujo de trabajo ideas → implementación

El ciclo estándar para convertir ideas en trabajo registrado:

```bash
# 1. Ver ideas priorizadas (el scorer ajusta según contexto del sistema)
bago ideas

# 2. Aceptar una idea (la guarda en pending_w2_task.json y la registra)
bago ideas --accept 2        # acepta la idea #2 de la lista

# 3. Abrir el workflow de implementación con título descriptivo
bago flow start W2 "Mejorar sistema de scoring dinámico"

# 4. Trabajar... (commits, edits, etc.)

# 5. Cerrar el workflow — registra la idea como implementada
bago flow done

# Verificar estado en cualquier momento
bago flow status             # ⚠️ alerta si la task lleva >3 días sin cerrarse
```

> **Nota**: `bago ideas` ajusta prioridades según el workflow activo (`bago flow status`),
> la salud del guardian (`bago guardian --trend`), y el historial de trabajo ya implementado.

### Using with an AI agent

Point your AI agent (GitHub Copilot, Claude, etc.) to `.bago/AGENT_START.md` as context. This file bootstraps the agent with the full operational state.

```
# In your AI agent prompt:
Read .bago/AGENT_START.md first. Then proceed with the task.
```

---

## Architecture

```
bago-framework/
├── bago                    ← CLI entry point (Python 3, no deps)
├── Makefile                ← pack, validate, install targets
└── .bago/
    ├── pack.json           ← manifest + version
    ├── AGENT_START.md      ← AI agent entry point
    ├── tools/              ← 32 Python tools
    ├── workflows/          ← 10 operational workflows (W0–W9) + orchestration layer
    ├── core/               ← BAGO constitution + protocols
    ├── agents/             ← Agent definitions (MAESTRO, COPILOT_ALIADO)
    ├── roles/              ← Role definitions (Architect, Implementor, Reviewer…)
    ├── docs/               ← 77 documentation files
    ├── templates/          ← Session templates
    ├── prompts/            ← Bootstrap prompts
    └── state/              ← Runtime state (sessions, changes, evidences)
```

### Design principles

- **Balanceado** — Clarify objective, scope, risk, and constraints before acting
- **Adaptativo** — Choose the right workflow for actual repo conditions
- **Generativo** — Produce useful, traceable technical artifacts
- **Organizativo** — Update state, summarize progress, leave continuity

---

## Self-evolution

BAGO tracks its own growth. Every significant change is registered as a `BAGO-CHG` artifact with evidence. The `bago efficiency` command compares performance across versions.

The public snapshot is intentionally distributed as a clean install. Runtime counters and health history begin to accumulate once the framework is used in real sessions.

---

## Makefile targets

```bash
make validate    # Run all validators (manifest + state + pack)
make pack        # Create distributable ZIP with timestamp
make install     # Install 'bago' alias in ~/.zshrc / ~/.bashrc
make clean       # Remove __pycache__ from .bago/
```

---

## License

MIT — see [LICENSE](LICENSE)

---

*BAGO 3.1 · Built with BAGO · May 2026*
