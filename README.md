# BAGO

BAGO runtime engine, cleaned for v3.5.0.

This repo now keeps only:

- BAGO engine/runtime (`bago_core`, `.bago/tools`, workflows, roles, prompts)
- `projects/music`
- `projects/image_generation`

Everything that is memory, sessions, learning, archived state, telemetry notes,
spiral history or project knowledge belongs in:

https://github.com/MarcValls/bago-knowledge

## Validate

```bash
python bago_core/launcher.py validate
python -m pytest projects/music/tests -q
python projects/image_generation/generators/image_gen.py --test
```

## Project Commands

```bash
python bago_core/launcher.py music --help
python bago_core/launcher.py image_gen --help
python bago_core/launcher.py image-studio --help
python bago_core/launcher.py sprite-studio --help
```

## Policy

- Do not commit runtime state, DBs, logs, tokens, generated caches or local knowledge.
- Keep new product work under `projects/music` or `projects/image_generation`.
- Sync durable knowledge through `bago-knowledge`, not through this repo.
