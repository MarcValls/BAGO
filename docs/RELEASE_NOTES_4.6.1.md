# BAGO 4.6.1 - Release Integrity Repair

Corrective release produced from the real `v4.6.0` source lineage after a full runtime and Manager audit.

## Fixed

- Reject release bundles when the filename, source metadata, tag manifest, or ZIP contents disagree.
- Package the current launcher and headless Manager/session/chain/release-job surfaces.
- Fetch GitHub releases through Electron IPC instead of the CSP-constrained preload context.
- Replace missing Manager logo assets with the packaged BAGO wasp SVG.
- Restrict Manager-to-chat messages to the local chat origin and parent window.
- Validate Manager context again in the local API before adding it to model input.
- Run CI on `master`, release branches, and version tags.

## Required assets

- `BAGO-Installation-Manager-4.6.1-win-x64.exe`
- `BAGO-Installation-Manager-4.6.1-win-x64.exe.sha256`
- `bago-v4.6.1.zip`
- `bago-v4.6.1.zip.sha256`
