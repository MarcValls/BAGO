# BAGO Runtime Contract

> Source of truth: `docs/runtime_contract.json`

This document defines the clean-install boundary between runtime, mutable state,
syncable knowledge, and development residue.

## Scope

- `C:\Program Files\BAGO` is the installed runtime root.
- `C:\ProgramData\BAGO\user` is the mutable user state root.
- `docs/runtime_contract.json` is the machine-readable source consumed by
  `install.ps1`.
- `C:\Program Files\BAGO\runtime_contract.json` is the generated manifest of the
  applied installation.
- `C:\Program Files\BAGO\.bago\knowledge` is the syncable memory layer that
  mirrors the GitHub knowledge repo.
- `install-with-knowledge.ps1` and `install-without-knowledge.ps1` are the two
  installer profiles built on the same runtime contract.
- `docs/PUBLISH_CONTRACT.md` defines the canonical install commands and the
  profile-level publication policy.
- `docs/ENGINE_CONTRACT.md` defines how to keep the installed engine clean
  during development and how to refresh it safely.

## Rules

- Keep the runtime tree minimal and reproducible.
- Prune development residue from the installed tree.
- Redirect mutable user state out of `Program Files`.
- Use the JSON contract as the only editable keep/prune policy.
- If the source contract cannot be read, the installer may fall back to the
  embedded default, but the policy stays the same.
- The publication profile changes only whether `knowledge/` is kept in the
  installed tree; the runtime base and state policy remain the same.
- The engine may be rebuilt at any time from the workspace using
  `bago dev refresh-engine`.

## Keep / prune model

The installer reads three groups from the contract:

- `root.keep`: files and folders that stay in the clean install.
- `state.reset_dirs`: runtime subdirectories that are wiped on install.
- `state.prune_file_patterns`: runtime files that are removed recursively.
- `knowledge`: the syncable knowledge tree that stays inside the runtime.
- `install_profile`: whether the runtime was deployed with or without the
  knowledge tree.

Anything not explicitly kept is treated as development residue and may be
removed from the clean install.

## Subtree `C:\Program Files\BAGO\.bago`

### Se queda

- `.llama/`, `.models/`
- `agents/`, `core/`, `tools/`, `state/`, `roles/`, `workflows/`, `supervision/`
- `config/`, `manifests/`, `mcp/`, `prompts/`, `templates/`, `extensions/`, `bin/`
- `assets/` as runtime UI/icon assets
- `pack.json`, `tools.manifest.json`
- `AGENT_START.md`, `BOOTSTRAP.md`
- `TREE.txt`, `CHECKSUMS.sha256`

### Conocimiento sincronizable

- `knowledge/README.md`
- `knowledge/manifest.json`
- `knowledge/topics/`
- `knowledge/examples/`
- `knowledge/schemas/`
- `knowledge/assets/`

El layout canónico de `knowledge/` replica el repo GitHub `MarcValls/bago-knowledge`:

- `README.md` y `manifest.json` como contrato de índice.
- `topics/` como superficie canónica de memoria.
- `examples/` para planes y casos reproducibles.
- `schemas/` para validación de contrato.
- `assets/` para diagramas y mapas ligeros.

### Se mueve fuera del clean install

- `README.md`, `INDEX.md`, `QUICKSTART.md`
- `docs/`, `examples/`
- `monitor/`, `reports/`, `audits/`, `archive/`
- `state.example/`

### Se elimina del clean install

- `tests/`
- `sprite_studio/`
- `.gitignore`
- `__pycache__/`

### Regla interna de `state/`

- Mantener vivos los JSON/DB que sostienen sesión, routing, modelos, ideas,
  salud, skills y memoria.
- Tratar `*.template.json`, `install_complete.json` y `*.md` de resumen como
  soporte/evidencia, no como motor.

## Change rule

Change the JSON source first, then regenerate the install manifest by running the
installer. Do not edit the generated `runtime_contract.json` by hand.
