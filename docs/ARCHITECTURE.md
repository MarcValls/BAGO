# BAGO Architecture

## Overview

BAGO is a **persistent operational layer** that sits between a developer and their AI agent. It provides structure, traceability, and continuity that the AI agent alone cannot maintain.

```
Developer ──► BAGO CLI ──► AI Agent
                │               │
                ▼               ▼
           .bago/state    .bago/core
           (persists)     (protocols)
```

### Layer model (conceptual)

```
bago-core -> bago-agents -> bago-ui -> bago-labs
```

- **bago-core**: stable operational contract (health/status/validate/audit/task/flow/session/project/context/sync/scope/secrets)
- **bago-agents**: orchestration and agent-facing tools (llm/route/autonomous/auto/ask/research/chronicle)
- **bago-ui**: interface surfaces (hub/dashboard/peer serve)
- **bago-labs**: domain and experimental tools (image/music/studio stack)

---

## Core components

### 1. CLI Entry Point (`bago` script)

A single Python script with no external dependencies. Routes commands to tools in `.bago/tools/`.

```
python3 bago <command>

Commands: dashboard · ideas · cosecha · detector · validate
          health · audit · workflow · stale · task
          stability · session · efficiency
```

### 2. Tools (`/tools/` — 30 Python files)

Each tool is a standalone Python module invoked by the CLI. Key tools:

| Tool | Purpose |
|---|---|
| `health_score.py` | 5-dimension composite health (0–100) |
| `efficiency_meter.py` | Cross-version capability comparison |
| `emit_ideas.py` | Scored idea selector with priority ranking |
| `show_task.py` | Task lifecycle manager |
| `stability_summary.py` | Full system stability report |
| `workflow_selector.py` | Context-aware workflow recommendation |
| `audit_v2.py` | Session audit trail |
| `cosecha.py` | Artifact harvest and consolidation |
| `validate_pack.py` | Pack consistency validator |
| `stale_detector.py` | Detects stale tasks (>3 days) |

### 3. Workflows (`/workflows/` — 12 protocols)

Structured work protocols for different task types. Each workflow defines:
- **Pre-conditions**: what must be true before starting
- **Steps**: ordered actions with roles
- **Artifacts**: what must be produced
- **Exit criteria**: what defines completion

### 4. Core (`/core/` — constitution + protocols)

BAGO's operational constitution. Contains:
- `00_CEREBRO_BAGO.md` — master operational context
- `04_CONTRATOS_DE_ROL.md` — role contract definitions
- `05_GOBERNANZA_DE_SESION.md` — session governance rules
- `07_PROTOCOLO_DE_CAMBIO.md` — change registration protocol

### 5. State (`/state/` — runtime)

All runtime data. Updated by tools during sessions:
- `global_state.json` — current health, version, inventory counts
- `sessions/*.json` — session records (task, workflow, decisions, artifacts)
- `changes/BAGO-CHG-*.json` — immutable change artifacts
- `evidences/*.json` — evidence files attached to changes

### 6. Agents (`/agents/`)

AI agent definitions. `MAESTRO_BAGO.md` is the primary orchestrator agent that coordinates roles and workflows.

### 7. Roles (`/roles/`)

Role definitions used during sessions: Architect, Implementor, Reviewer, Vértice (sensitive changes), etc.

---

## Data flow

### Session lifecycle

```
bago stability
     │
     ▼
(check state, health, stale)
     │
     ▼
bago workflow / bago task
     │
     ▼
AI agent reads AGENT_START.md
     │
     ▼
Work: decisions + artifacts logged
     │
     ▼
bago cosecha → harvest artifacts
     │
     ▼
bago validate → consistency check
     │
     ▼
state/sessions/session_YYYYMMDD.json updated
```

### Change registration

Every significant change goes through:
```
1. Human identifies change
2. BAGO-CHG artifact created (changes/BAGO-CHG-NNN.json)
3. Evidence attached (evidences/EVD-NNN.json)
4. global_state.json inventory updated
5. bago validate confirms consistency
```

---

## Validation system

BAGO has three validators that run in sequence:

```
validate_manifest.py  → pack.json integrity + required fields
validate_state.py     → state files exist + schema compliance
validate_pack.py      → version match + inventory reconciliation
```

All three must return `GO` for a clean system state.

---

## Health score formula

```python
health = (
    integrity_score   × 0.25 +   # validators pass
    workflow_score    × 0.20 +   # workflow usage per session
    decision_score    × 0.20 +   # decisions captured per session
    stale_score       × 0.15 +   # no stale tasks
    inventory_score   × 0.20     # declared vs actual counts match
)
```

Maximum: 100/100

---

## Efficiency index formula

Used by `bago efficiency` to compare versions:

```python
efficiency = (
    commands  × 0.30 +
    tools     × 0.35 +
    docs      × 0.20 +
    workflows × 0.15
) normalized to 100
```

---

## Self-evolution design

BAGO is designed to evolve itself:

1. `bago ideas` surfaces scored improvements
2. Ideas are implemented as BAGO-CHG artifacts
3. `bago efficiency` measures the improvement
4. Implemented ideas are registered in `state/implemented_ideas.json`

This creates a closed improvement loop: **observe → ideate → implement → measure**.

---

*See `.bago/core/00_CEREBRO_BAGO.md` for the full operational specification.*
