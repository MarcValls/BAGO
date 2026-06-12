# BAGO Public Release Policy

This document defines the public publication gate for BAGO 4.6.1 and later. It is the single public checklist for release readiness.

## Publication Order

1. Freeze scope.
2. Close all `P0` items.
3. Pass CI green.
4. Generate a signed release artifact.
5. Publish release notes and usage limits.
6. Run a clean-install smoke test.
7. Publish only if `validate` and `pytest` are still green on the final artifact.

## Required Release Gates

- `python bago_core\cli.py validate`
- `python -m pytest -q`
- `python scripts\clean_install_smoke.py`
- `python scripts\verify_release_drift.py`
- `python scripts\verify_docs.py --repo .`
- `python scripts\package_v4.py --test`
- UI build, if UI assets are shipped

## Public Guarantees

- BAGO is released as a local-first control plane.
- The stable MVP boundary is the one documented in `docs/MVP.md` and `README.md`.
- Experimental surfaces stay labeled as experimental unless they have an explicit proof path.
- Public claims must map to proof in `docs/CLAIMS.md`.

## Public Limits

- No experimental module is promoted as stable.
- No live state, credentials, or caches are packaged in the release artifact.
- No arbitrary PowerShell execution is exposed through public UI or API surfaces.
- No non-localhost API bind is allowed without the documented token gate.
- RL, agents, and autopilot remain off by default unless explicitly authorized.

## Release Notes Must Say

- What changed.
- Which gates passed.
- Which limits still apply.
- Which features are experimental or unavailable.
- Which install path is official.
- The canonical 4.6.1 notes live in `docs/RELEASE_NOTES_4.6.1.md`.

## Stop Conditions

Stop the publication if any of these fail:

- `validate`
- `pytest`
- signed artifact generation
- clean-install smoke
- documentation/version drift checks

## Public Release Note Template

```text
BAGO v4.6.1

Status: stable release candidate

Passed gates:
- validate
- pytest
- clean-install smoke
- release drift check
- docs check

Known limits:
- RL and autopilot stay experimental.
- Browser automation is policy-gated.
- API remains localhost-first.
- No live state or credentials are packaged.

Install:
- GitHub Releases only
```
