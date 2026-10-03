# Sink inventory reconciliation — 2026-09-27

This receipt preserves the two official scanner outputs used to explain why a dirty local checkout reported more findings than the clean source candidate. It is evidence for inventory interpretation only; it does not close `strict-runtime`, prove complete scanner coverage, or authorize sink repairs.

## Reconciliation

The exact set comparison is:

`4,503 = 1,705 + 2,787 derived_release_snapshot + 12 build_release_admin additions - 1 build_release_admin removal`

The net local editorial difference is 11. Five added findings came from `scripts/editorial/render_markdown.py`; seven came from the dirty comparison copy of `scripts/render_bago_context_audit_pdf.py`; one prior finding at line 105 in that second file was absent in the comparison result. Both snapshots report 265 `runtime_unbound` findings. All 2,787 `derived_release_snapshot` findings are classified as `nonruntime_effect`; they are not additional runtime repairs.

The two comparison-only editorial files were in a dirty local worktree and are not part of this documentation PR. Their scanner observations are preserved in the comparison output; their source files and compiled runtime trees were not copied into this repository.

## Candidate and scanner evidence

The machine-readable receipt records each candidate's HEAD, tree, branch, dirty status, porcelain paths, scanner-input file count and manifest SHA-256, audit worktree fingerprint, scanner/effect-registry hashes, gate exits, and raw/normalized output hashes. It also stores both complete JSON outputs with only `repo_root` replaced by `$REPO_ROOT` so the normalized output is independent of checkout path.

- Clean published-map candidate: HEAD `b990c8b5699ae8429fd8e91f8c977484fbc8d6bd`, clean worktree; 1,705 total, 265 runtime-unbound, 336 gateway-owned, zero unclassified. `strict-classification` exit 0; `strict-runtime` exit 2.
- Separate comparison worktree: HEAD `a21858780615440a775a7989970b8917fc0d6732`, dirty; 4,503 total, 265 runtime-unbound, 336 gateway-owned, zero unclassified. `strict-classification` exit 0; `strict-runtime` exit 2.
- Scanner SHA-256: `59c4d9cc38d2b46acb081dc0083da2c4185866c297ea41070690d384f4896b0a`.
- Registry: `bago.effect-registry.v1` 1.24.0, SHA-256 `ab1edad052f705ae01092b120858c876ce1ec760e88875beb89b37d55fd61f30`.

See [`sink-inventory-reconciliation.v1.json`](sink-inventory-reconciliation.v1.json) for exact counts, identities, roots, timestamps, commands, and artifact hashes. Complete normalized scanner outputs:

- [`sink-inventory-published-map-candidate.json.gz`](sink-inventory-published-map-candidate.json.gz)
- [`sink-inventory-comparison-worktree.json.gz`](sink-inventory-comparison-worktree.json.gz)

To verify a compressed output's recorded normalized SHA-256:

```powershell
python -c "import gzip,hashlib,pathlib; p=pathlib.Path(r'docs/architecture/evidence/sink-inventory/sink-inventory-published-map-candidate.json.gz'); print(hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest())"
```

Use `sink-inventory-comparison-worktree.json.gz` as the path when checking the dirty comparison output. The gzip file hashes are also recorded in the receipt.
