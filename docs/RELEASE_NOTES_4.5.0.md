# BAGO v4.5.0 Release Notes

Status: release candidate

## Highlights

- Stable MVP boundary is documented and frozen in `docs/MVP.md`.
- Public release gates are centralized in `docs/PUBLIC_RELEASE_POLICY.md`.
- The release checklist now points to the public publication policy and final smoke gates.
- The repo tracks version 4.5.0 across source, docs, manifests, and release metadata.

## Gates Passed

- `python bago_core\cli.py validate`
- `python -m pytest -q`
- `python scripts\clean_install_smoke.py`
- `python scripts\verify_release_drift.py`
- `python scripts\verify_docs.py --repo .`
- `python scripts\package_v4.py --test`
- `python .bago\api\bridge.py --test`

## Public Limits

- RL stays shadow/off by default.
- Agents and autopilot remain experimental.
- Browser automation is policy-gated.
- API access stays localhost-first and token-gated for non-localhost binds.
- No live state, credentials, or caches are included in release artifacts.

## Install Path

- Official distribution path: GitHub Releases only.
- Remote installer must remain pinned to the release tag, not a mutable branch.

## Known Non-Stable Surfaces

- `ui-react` is an optional surface.
- Cloud provider completeness depends on credentials and provider health.
- Advanced knowledge and embedding paths remain partial unless separately proven.

