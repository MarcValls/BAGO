# BAGO large-file audit

Date: 2026-08-16  
Scope: repository files tracked under `backend/`  
Gate: `.bago/tools/auto_heal.py` rule `RLARGE` (>250 KB)

## Actions taken

- Deleted stale `bago-v4.9.0.zip` and local `bago-v4-local-*.zip` sidecars from `release/v4/`.
- Deleted stale `backend/dist/` build tree.
- Moved old evidence snapshots `provider_validation_4_8_1/` and `release_4_8_1/` from `docs/evidence/` to `docs/archive/evidence/` (already excluded from the release package).
- Updated `tests/test_evidence_report_paths.py` to use the archived path.

## Result

Source-tree files larger than 250 KB (excluding `node_modules` and transient build output) reduced from several old evidence bundles to the four intentional files below:

| File | Size class | Reason |
|------|------------|--------|
| `.gabo/context/index.json` | ~8 MB | Generated symbol/context index used by the `gabo` search layer. Re-created on demand; safe to regenerate. |
| `.gabo/context/symbols.json` | ~8 MB | Generated cross-reference index; same regeneration rule as above. |
| `ui-react/dist/assets/index-*.js` | ~1 MB | Production React/Vite bundle shipped with the release. |
| `release/v4/current/ui-react/dist/assets/index-*.js` | ~1 MB | Release staging copy of the same bundle; re-created by `scripts/package_v4.py`. |

`node_modules`, `dist`, `build`, `.gabo/context` and `docs/archive` are already excluded from the distribution ZIP by the packaging allow-lists in `scripts/package_v4.py`.

## Recommendations

1. Do not commit additional `.gabo/context/` dumps; keep them in `.gitignore` or regenerate via CI.
2. For future releases, produce source maps externally if bundle debugging is needed, so the shipped `index-*.js` can stay minified.
3. Re-run `auto_heal.py` after every release build to confirm no new build artifacts leak into the package.
