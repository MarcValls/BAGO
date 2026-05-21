# BAGO Publish Contract

> Source of truth: `docs/runtime_contract.json`

This contract defines the two publication profiles for the clean install:

- `with-knowledge`: same runtime base, plus the syncable knowledge tree.
- `without-knowledge`: same runtime base, without the knowledge tree mounted.

Both profiles share the same runtime code. The only operational difference is
whether `C:\Program Files\BAGO\.bago\knowledge` is kept in the installed tree.

## Canonical install commands

Use these commands from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-without-knowledge.ps1
```

Base installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -NoKnowledge
```

## Publication rules

- `install-with-knowledge.ps1` is the default publication profile.
- `install-without-knowledge.ps1` publishes the same runtime without the
  knowledge mirror.
- `install.ps1` is the shared implementation behind both wrappers.
- The installed manifest in `C:\Program Files\BAGO\runtime_contract.json`
  records `install_profile`, `knowledge_included`, and the contract hash.
- The source policy remains `docs/runtime_contract.json`; do not edit the
  generated runtime manifest by hand.

## Knowledge sync

When the knowledge profile is enabled, the local memory tree stays compatible
with the GitHub mirror:

```powershell
bago knowledge status
bago knowledge sync
```

The sync target is `MarcValls/bago-knowledge`.

