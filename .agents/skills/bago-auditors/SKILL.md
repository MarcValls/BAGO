---
name: bago-auditors
description: Read-only audit swarm for BAGO. Use when asked to review architecture, backend routes, frontend React/state, contracts, security, performance, tests, hygiene, or truth/evidence. Pass the audit mode as the first argument.
compatibility: Pi 0.84.2+. Runs read-only; never edits files. Uses the built-in read and bash tools to trace code and run repository-defined checks.
metadata:
  targetHarness: pi
  minPiVersion: 0.84.2
  sourceRepo: MarcValls/BAGO
---

# BAGO Auditors for Pi

Read-only audit skill for the BAGO monorepo. Map the first argument to an audit mode and follow the corresponding discipline.

## Modes

| Argument | Focus |
|----------|-------|
| `architecture` | ownership, dependency direction, sources of truth, contracts, invariants, domain boundaries, God Components/Modules |
| `backend` | endpoints, handlers, validation, persistence, subprocess, trust boundaries |
| `frontend` | React state, effects, navigation, panels, composition, render ownership |
| `contracts` | frontend → backend call chains, types, route compatibility, obsolete methods |
| `security` | filesystem, subprocess, credentials, Electron/IPC, tools/plugins, destructive actions |
| `performance` | renders, effects, IO, trees, parsing, listeners, timers, caches |
| `tests` | CI, build, runtime checks, coverage vs real capabilities |
| `hygiene` | dead code, legacy, dependencies, CSS, divergent docs |
| `truth` | state/evidence separation, false closures, UI claims without evidence |
| `code-map` | flow reconstruction, ownership, API calls, tests, cross-dependencies |

If no argument is given, default to `architecture`.

## Universal rules

- Inspect before concluding. Trace from real entrypoints to real effects/persistence.
- Distinguish `HECHO`, `INFERENCIA`, `HIPÓTESIS`, and `RECOMENDACIÓN`.
- Distinguish a legitimate large dispatcher/orchestrator from a real God Module; require evidence of responsibility concentration.
- Do not edit files. Do not declare `VERIFIED` without executed evidence.
- Use `/skill:bago-core` first for lifecycle and state context if the task is continuation, conflict, or closure work.
- Return findings with file paths, symbols, and line numbers when possible.
