# BAGO Manager - Verified Release Jobs

## Contract

The Manager never installs a GitHub release directly from a URL.

1. Select one ZIP with its exact `<bundle>.zip.sha256` asset.
2. Stream the ZIP to a persistent partial file.
3. Allow cancel and HTTP range resume.
4. Calculate SHA256 over the downloaded bytes.
5. Match the paired checksum and, when published, the GitHub asset digest.
6. Verify ZIP magic and extract to isolated staging.
7. Require `install-v4.ps1` and `bago_core/launcher.py`.
8. Match the staged `release_version.txt` to the selected release when present.
9. Run target preflight before installation.
10. Rename an existing target to a same-volume rollback path before mutation.
11. Install and validate the new runtime.
12. Restore the previous runtime automatically on failure or cancellation.

Source/branch updates are a separate local flow: they may pull a selected branch from a checked-out repo and then install from that source, but they do not bypass the release-job contract for GitHub releases.

## Signature Policy

- Detached `.sig` or `.asc` assets are verified with GPG when published.
- A job may explicitly require a valid detached signature.
- If the release does not publish a signature, the default policy records
  `not-published` while still requiring SHA256 and GitHub digest verification.

## Persistent State

Jobs, cache, staging and JSONL logs live under:

```text
~\.bago\manager\release-jobs\
```

Interrupted active jobs reopen as cancelled and can be resumed from their
partial download.

## Locks

- Downloads may run independently.
- Only one install/update/rollback lifecycle mutation may run at a time.
- Connector mutations retain their separate Node Control lock.

## Preflight

Install, update and uninstall impact checks report:

- target existence and current version
- writable path and elevation requirement
- free and required disk space
- backup requirement
- preservation of shared PieceStore, connector registry and evidence
