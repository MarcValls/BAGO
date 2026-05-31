# BAGO v4 Integration

This document defines how BAGO v4 connects to installed runtimes, advanced backends, state folders, and optional UI surfaces.

## Local Workspace

```text
C:\Bago_v4
```

Role:

- source of truth for v4 development.
- plan root for `PLAN_VERTICE`.
- release artifact source after gates pass.

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

## Next Steps

1. Implement `bago rl status`.
2. Add packaging checks for all integration boundaries.
3. Add backup/rollback before writing to `C:\Program Files\BAGO`.
