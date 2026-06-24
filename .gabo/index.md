# BAG4.8 — context seed (`.gabo/`)

- **Captured**: 2026-06-24T10:02:47Z
- **Workspace root**: `.` (all paths below are relative to the workspace root)
- **Tree depth**: 3 (max supported: 8 — re-seed with `python .gabo/seed.py --depth N`)
- **Version**: **4.8.0**
- **Workspace matches active install**: **YES**

## Manifests

| area | path (root-relative) | broken | files |
|---|---|---|---|
| api | `.bago/api` | no | – |
| tools_sprints | `tools/sprints` | no | 113 (10 groups) |
| bago_core | `bago_core` | no | 76 |
| ui_react | `ui-react` | no | 28 |
| agents | `.bago/agents` | no | 11 |
| tools | `.bago/tools` | no | 38 |
| providers | `.bago/providers` | no | 10 |
| roles | `.bago/roles` | no | 4 |
| workflows | `.bago/workflows` | no | 15 |
| knowledge | `.bago/knowledge` | no | 3 |
| prompts | `.bago/prompts` | no | 12 |
| mcp | `.bago/mcp` | no | 5 |
| chat | `.bago/chat` | no | 7 |
| extensions | `.bago/extensions` | no | 0 |
| templates | `.bago/templates` | no | 5 |
| core | `.bago/core` | no | 27 |
| state_example | `.bago/state.example` | no | 1 |

## Diff vs reference

- ref basename: **BAGO**
- missing files (root-relative paths): **604**

Top missing top-level dirs:

| top dir | missing count |
|---|---|
| `ui-react` | 166 |
| `.bago` | 129 |
| `.bago-backup-parity1` | 64 |
| `scripts` | 22 |
| `docs` | 16 |
| `archive` | 12 |
| `bago_core` | 7 |
| `examples` | 4 |
| `backups_2026-06-24` | 3 |
| `tests` | 2 |

## Next step

- Bridge looks intact. Continue with the task at hand.

## How to re-seed deeper

```
python .gabo/seed.py --depth 5
python .gabo/seed.py --depth 8 --root 'D:\other\BAG4.8'
```
