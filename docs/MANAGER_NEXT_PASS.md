# BAGO Manager - Next Pass

Detected while converting the manager to a Patch-first control surface.

## Completed In This Pass

- Distinguish materialized connectors, detached connectors and available/not-created matrix crossings.
- Correlate installation scan and Node Control registry, and surface version/path drift in Health.
- Show the real evidence ledger tail alongside session UI activity.
- Add connector mutation preflight, explicit confirmation, post-apply validation and automatic rollback on validation failure.
- Make release selection explicit: latest stable, latest prerelease, exact tag and release channel filter.
- Gate release installation actions on a published ZIP + SHA256 asset contract.
- Preflight Python, PowerShell, Git, Ollama and Node/Electron availability.
- Lock concurrent Node Control connector mutations.
- Download release bundles with streaming progress, cancellation and HTTP resume.
- Verify downloaded bytes against the paired SHA256 asset and GitHub digest.
- Validate ZIP type, release version and required runtime files before install.
- Support optional detached signature verification with explicit required-signature policy.
- Persist release jobs, logs and state across Manager restarts.
- Install verified bundles through atomic target backup with automatic and manual rollback.
- Add install/update/uninstall preflight for permissions, elevation, disk and impact.
- Harden `install-remote.ps1` with stable-by-default release selection and the same verification contract.

## Priority 0

No remaining Priority 0 items.

## Priority 1

- Detect drift between source tree, installed runtime, active role, remote installer and published release.
- Manage PieceStore health: disk usage, duplicates, orphan pieces, missing manifests and safe garbage collection.
- Manage overlays: size, changed files, diff, reset, merge and promotion to a shared piece.
- Extend lifecycle locking from verified install/update jobs to uninstall and garbage collection execution.
- Manage supervisor/probe/process state per installation, including logs and restart policy.
- Show provider/model availability and credential presence without exposing secret values.
- Add translator lifecycle management: materialize, validate roundtrip, map, audit and detach.
- Add backup/restore impact preview for installation state, shared pieces and overlays.
- Add uninstall impact analysis so shared pieces and connectors used by other installations remain protected.

## Later

- Remote BAGO hosts as installations with the same connector contract.
- Scheduled maintenance jobs and alerts.
- Policy templates with diff/preview before applying them to multiple installations.
