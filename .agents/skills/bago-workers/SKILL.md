---
name: bago-workers
description: "Implementation skill for BAGO. Use for approved, well-scoped PRs or mechanical, repetitive, fully-specified changes. Pass the mode as the first argument: implement or mechanical."
compatibility: Pi 0.84.2+. Edits files only within the approved scope. Requires the full read, bash, edit, write toolset.
metadata:
  targetHarness: pi
  minPiVersion: 0.84.2
  sourceRepo: MarcValls/BAGO
---

# BAGO Workers for Pi

Implementation skill for the BAGO monorepo. Choose the mode from the first argument.

## Modes

### `implement`

Implement only the approved scope.

- Make the smallest defensible change.
- Preserve contracts unless explicitly instructed.
- Avoid collateral refactors.
- Run the repository-defined tests that cover the change.
- Before finishing, show the diff, tests executed, results, and anything not verified.
- Do not declare `VALIDATED` on your own authority.

### `mechanical`

Execute only clear, repetitive transformations with objective criteria.

- Do not make architectural decisions.
- If ambiguity appears, stop and return a BLOCK.
- Keep the scope minimal and run the relevant mechanical checks.

If no argument is given, default to `mechanical` and ask for confirmation before large edits.

## Common rules

- Load `/skill:bago-core` at the start of any non-trivial task to read `.bago/` state and canon.
- Use `git status` before and after to show what changed.
- Never overwrite repository manifests, lockfiles, or source config unless the task explicitly authorizes it.
