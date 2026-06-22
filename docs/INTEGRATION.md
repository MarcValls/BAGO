# BAGO v4 Integration

This document defines how BAGO v4 connects to installed runtimes, advanced backends, state folders, and optional UI surfaces.

## BAGO Mode Activation

The shared base prompt is `.bago/BOOTSTRAP.md`.
The canonical agent entrypoint is `.bago/AGENT_START.md`.
`START_AGENT.md` is only a compatibility alias.

| Surface | Hook | Provider responsibility |
|---|---|---|
| Codex CLI/app inside the repo | `AGENTS.md` loads `.bago/AGENT_START.md` | Codex is already the provider; BAGO does not replace it |
| GitHub Copilot inside the repo | `.github/copilot-instructions.md` loads `.bago/AGENT_START.md` | Copilot is already the provider; BAGO does not replace it |
| BAGO chat runtime | `.bago/chat/system_prompt.py` loads `.bago/BOOTSTRAP.md` + `.bago/AGENT_START.md` | `SessionManager` manages provider, model, and session |
| Another chat or API | Inject `.bago/BOOTSTRAP.md` + `.bago/AGENT_START.md` as the system/developer prompt | The host keeps its provider |

Inside the BAGO runtime, `agent_gateway` specializes behavior without changing
provider, model, or context. Use `/mode B|A|G|O` for the operating mode and
`/agent <name>` separately for specialization.

There is no portable mechanism that makes every provider detect BAGO only by
name. Each host requires its native hook or explicit bootstrap injection.

## Local Workspace

```text
C:\Users\AMTEC_Terminal_1º\bago_fw
```

Role:

- editable source tree for current development.
- primary target for implementation work.
- source used first before syncing to the installed runtime.

## Installed Runtime

```text
C:\Program Files\BAGO
```

Role:

- installed runtime target.
- should receive clean release content only.

Rule:

- never patch installed runtime blindly.
- backup before update.
- rollback path required.
- install uses `install-v4.ps1` or `bago install`.
- uninstall uses `bago uninstall` or `bago-uninstall.ps1` and creates a backup first.
- `install_config.json` is generated per installation and must not be committed as a static package file.

## Mutable User State

```text
C:\ProgramData\BAGO\user
```

Role:

- live sessions.
- credentials.
- routing/runtime data.
- audit/history.

Rule:

- never package.
- never overwrite without migration logic.
- credentials are session-only by default.
- persistent credentials require explicit opt-in and are stored outside the repo/package.
- external credential export must be encrypted.

## `bago_true`

```text
C:\bago_true\.bago
```

Role:

- external advanced backend source.
- agents/tools/workflows/supervision/knowledge.

Command:

```powershell
python bago_core\cli.py engine status
```

Rule:

- integrate by bridge.
- do not copy whole folder.
- do not import `state`, `logs`, `backups`, checkpoints, or credentials.

## `bago_true` RL

```text
C:\bago_true\.bago\rl
```

Role:

- RL source material.
- shadow adapter.
- LinUCB/BC policy sources.

Rule:

- start with shadow mode.
- `numpy` optional.
- PPO/QMIX experimental.

## AppData BAGO

```text
C:\Users\AMTEC_Terminal_1º\AppData\Local\Programs\BAGO
```

Role:

- source for `cmd-rl` and Spiral signals.
- migration reference.

Rule:

- detect and migrate only what is needed.
- v4 must not depend on AppData to start.

Commands:

```powershell
python bago_core\cli.py appdata status
python bago_core\cli.py cmd-rl status
```

## React UI

```text
C:\Bago_v4\ui-react
```

Role:

- optional control surface.
- talks to local API.

Rule:

- no embedded credentials.
- build output is optional.
- CLI must work without UI.

## Expo Native UI

```text
C:\Bago_v4\apps\mobile-expo
```

Status: planned optional surface.

Rule:

- Expo Go first.
- no custom native build unless a real native dependency requires it.
- not part of base release unless activated and gated.

## Plan Monitor

```text
C:\Bago_v4\PLAN_VERTICE\monitor
```

Role:

- local HTML monitor for plan execution.
- logs commands/events to JSONL.

Rule:

- monitor plan execution only.
- no keylogging, screen capture, or unrelated surveillance.

## Dot-bago seeding contract

Every BAGO project needs a `.bago/` directory, but `.bago/` is **not a single thing**:

| Category | Lives in `.bago/` | Versioned in project? | Seeded by `bago init`? |
|---|---|---|---|
| **Canonical runtime / prompts** | `AGENT_START.md`, `BOOTSTRAP.md`, `START_AGENT.md`, `core/`, `api/`, `chat/`, `providers/`, `agents/`, `roles/`, `prompts/`, `workflows/`, `tools/`, `mcp/`, `templates/`, `keybinds.json` | **Yes** | **Yes** |
| **Project overrides** | `knowledge/`, `extensions/`, per-project prompts/agents | Optional | Optional (empty scaffold) |
| **Runtime state** | `state/`, `logs/`, `launch/`, `credentials.json`, `config.json`, `session-credentials.json`, `monitor/` | **No** (`*.db`, `state/`, `logs/` are ignored) | Generated empty at runtime |
| **Minimal state example** | `state.example/` | **Yes** | Copied to `state/` on first init |

### Rule

The canonical files are the **seed**. The project repository may carry them directly (as `bago_fw` does today) or derive them from a master package. The mutable state must never be committed, and must be created on first run if missing.

### Seeding checklist

When creating a new BAGO project, the following must be present:

1. `AGENT_START.md`, `BOOTSTRAP.md`, `START_AGENT.md` — agent adoption contract.
2. `core/` — session manager, switch engine, config, tool/intent registry, version.
3. `api/bridge.py` — local HTTP API used by the React UI and external integrations.
4. `chat/` — REPL, commands, system prompt loader.
5. `providers/` — provider adapters (ollama-local, codex, copilot, etc.).
6. `agents/` — agent factory and specialization agents.
7. `roles/` — role definitions for production/supervision/specialists.
8. `prompts/` — canonical prompt templates.
9. `workflows/` — workflow definitions.
10. `tools/` — tool registry and project memory helpers.
11. `mcp/` — MCP server configuration and catalog.
12. `templates/` — Markdown templates for changes, evidence, roles, workflows.
13. `keybinds.json` — default key bindings.
14. `state.example/` — minimal empty state layout copied to `state/` on init.

### Usage example

Create a new project and seed it:

```powershell
New-Item -ItemType Directory -Path "C:\Proyectos\mi-nueva-app" -Force
Set-Location "C:\Proyectos\mi-nueva-app"
bago init
```

Preview without writing:

```powershell
bago init --dry-run
```

Include project-specific templates:

```powershell
bago init --with-knowledge
```

A complete automated demo lives in `examples/init-project/init-demo.ps1`.

### Future direction

To keep the seed separate from per-project drift, the canonical seed should move to a master template (e.g. `bago_core/templates/dot-bago/`) and `bago init` should copy it into the target project. Project repos should then only version intentional overrides, not the full runtime.

## Next Steps

1. Move canonical seed to `bago_core/templates/dot-bago/` and make `bago init` use it as primary source.
2. Implement `bago rl status`.
3. Add packaging checks for all integration boundaries.
4. Add backup/rollback before writing to `C:\Program Files\BAGO`.
