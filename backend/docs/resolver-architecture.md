# BAGO Resolver Architecture

This is the architecture overview for the resolver layer. The live authority is in the resolver code and contracts, not here.

## Live Authority

- `docs/contracts/resolver_contract.json`
- `docs/contracts/workspace_seed_contract.md`
- `bago_core/resolver/`
- `tests/test_resolver_contract.py`
- `tests/test_workspace_seed_contract.py`

## Responsibilities

- canonical path resolution
- alias and fallback compatibility
- depth-independent discovery
- policy enforcement and diagnostics

## Notes

- Do not hardcode paths outside the resolver layer.
- Legacy roots are adapters, not authorities.
- Installer, launcher, and workspace seed should consume the same resolver contract.
