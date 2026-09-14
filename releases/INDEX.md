# BAGO Release Documentation Index

## Current candidate

- Current candidate version: `4.10.0` (resolve from `../release_version.txt`).
- Candidate release notes: [RELEASE_NOTES_4.10.0.md](RELEASE_NOTES_4.10.0.md).
- Its publication and signed-release status are defined by the root
  [README](../README.md) and the candidate-bound evidence, not by this index.

## Historical pre-remediation local release index

This snapshot was captured before the AUD-001..010 remediation. It describes
file identities only and is not current candidate, publication or installation evidence.

## Immutable identity

- Source HEAD at historical capture: `e76b01b0a0552d8eee7c536f8c4eef25e3a82a42`
- Tag `v4.9.0` resolves to: `1d046ea30e3efb8a031470deb204e48b4e75b350`
- Working tree at historical capture: `DIRTY`

## Current binary artifacts

| Artifact | Bytes | SHA-256 | Verification scope |
|---|---:|---|---|
| `bago-4.9.0-setup.exe` | 303979891 | `FC5FB8CA0B0137735D31DAECF5EA0668B517E09191D9678E7B0649BD021D2673` | File identity only |
| `bago-4.9.0-distribution.zip` | 319407789 | `B4614FAE0209D67EA6D676A6C5B8F9805479A50D4C017202C2213E7460E89CF9` | File identity only |

The checksum sidecar `bago-4.9.0-setup.exe.sha256` matches the setup executable above.

## Validation state

- Installer build: previously executed; this index does not certify its source identity.
- Installation of the exact setup artifact: `NOT_RUN` for the current remediation candidate.
- Electron visual validation of the installed artifact: `NOT_RUN` for the current remediation candidate.
- Public GitHub release equivalence: `NOT_RUN`.

Do not promote these artifacts to `VALIDATED` until their build logs, installation smoke, runtime verification and candidate identity are captured by the remediation gate registry.
