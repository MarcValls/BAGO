# Getting Started with BAGO v3.2-kernel

This guide walks you through your first BAGO-powered work session.

---

## Prerequisites

- **Python 3.9+** (standard library only — no external dependencies)
- **Git** (optional, but recommended)
- An AI agent: GitHub Copilot CLI, Claude Code, or any LLM with file access

---

## Installation

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .          # installs 'bago' console script
```

---

## Step 1 — Verify the installation

```bash
bago validate
```

Expected output:
```
GO manifest
GO state
GO pack
```

If you see `KO`, run `bago health` for diagnostics.

---

## Step 2 — Check system health

```bash
bago health
```

BAGO health measures 5 dimensions:

| Dimension | What it measures |
|---|---|
| Integridad | pack.json + validator consistency |
| Disciplina workflow | Workflow usage per session |
| Captura decisiones | Average decisions per session |
| Estado stale | No stale tasks or outdated state |
| Consistencia inventario | Declared inventory matches reality |

A fresh installation shows `initializing`. After a few sessions, you'll see a score like `87/100 🟢`.

---

## Step 3 — Bootstrap your AI agent

Open `.bago/AGENT_START.md` — this is the entry point for any AI agent. It bootstraps the agent with:
- The active workflow context
- Current task and sprint status
- Operational protocols

**Example prompt to your AI agent:**
```
Read .bago/AGENT_START.md first, then help me implement [feature].
```

---

## Step 4 — Choose a workflow

```bash
bago workflow
```

Or manually pick based on your task type:

| If you want to... | Use |
|---|---|
| Explore freely (no structure) | `W0 · Free Session` |
| Start a new project | `W1 · Cold Start` |
| Implement a feature | `W2 · Controlled Implementation` |
| Refactor existing code | `W3 · Sensitive Refactor` |
| Debug a complex issue | `W4 · Multi-cause Debug` |
| Wrap up a session | `W5 · Closure & Continuity` |
| Generate new ideas | `W6 · Applied Ideation` |
| Stay focused on one goal | `W7 · Session Focus` |
| Explore something new | `W8 · Exploration` |
| Harvest artifacts | `W9 · Cosecha` |
| Audit for unverified claims | `W10 · Auditoría de Sinceridad` |

---

## Step 5 — Work with BAGO discipline

During a session:

1. **Start**: `bago session open` → logs session start with context
2. **Work**: Make changes; the agent records decisions and artifacts
3. **Check**: `bago health` → full system check mid-session
4. **Ideas**: `bago ideas` → prioritized improvements to implement

---

## Step 6 — Close the session properly

```bash
# Harvest artifacts and decisions
bago session harvest

# Full audit of the session
bago audit full

# Validate everything is consistent
bago validate
```

---

## Step 7 — Track your work

After several sessions:

```bash
bago audit          # Review session trail
bago context map    # Workspace overview
```

---

## Common patterns

### Daily work routine
```bash
bago health             # Morning check
bago status             # Active flow + pending task
bago ideas              # Pick today's focus
# ... work with AI agent ...
bago validate           # End-of-session check
```

### When something feels wrong
```bash
bago context stale      # Check for stale tasks
bago audit scan         # Context drift detection
bago audit full         # Full session audit
```

### When you want to evolve BAGO
```bash
bago ideas              # See scored improvement ideas
# Implement an idea
bago health             # Measure system impact
```

---

## File structure reference

```
.bago/
├── AGENT_START.md          ← Start here (for AI agent)
├── pack.json               ← System manifest
├── state/                  ← Runtime state (gitignored)
│   ├── global_state.json   ← Current system state
│   ├── sessions/           ← Session records
│   ├── changes/            ← BAGO-CHG artifacts
│   └── evidences/          ← Evidence files
├── state.example/          ← Clean-install templates (versioned)
├── tools/                  ← Python utilities
├── workflows/              ← W0–W10 operational protocols
└── core/                   ← Autonomous loop + core engine
```

---

## Troubleshooting

**`KO version mismatch`**: `pack.json` version and `global_state.json` `bago_version` must match.

**`Health: initializing`**: Normal for a fresh install. After the first full session it transitions to `stable`.

**`Stale task detected`**: A task in `pending_w2_task.json` is older than 3 days. Clear with `bago task --clear`.

---

*More documentation in `docs/` — see `ARCHITECTURE.md` and `COMMAND_AUDIT.md` for reference.*

