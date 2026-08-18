# Context Pattern Registry Contract

Canonical authority: `CANON.MD`, section 63.

Status: executable subset for the current context mixin. This document does not certify the full pattern subsystem.

Current maturity: implemented_unverified / partially_tested. Certification remains pending until the full section 63 gate has receipts, negative tests, mutation tests, interface isolation evidence, and clean-environment repetition.

The context mixin must not parse files, infer formats, or own precedence rules.
It consumes only resolved patterns from an immutable `PatternSnapshot`.

## Load Flow

authorized root -> mandatory manifest -> declared files -> safe decode -> canonical normalization -> structural validation -> semantic validation -> precedence resolution -> immutable snapshot -> readonly registry

If a reload fails, the active snapshot is not modified. The failed attempt is kept as diagnostics on the coordinator.

## Required Manifest Fields

Each pack must declare:

- `pack_id`
- `pack_version`
- `required_schema_version`
- `domains`
- `dependencies`
- `priority`
- `trust_level`
- `required`
- `runtime.min`
- `runtime.max`
- `discovery.recursive`
- `discovery.authorized_extensions`
- `discovery.symlinks`
- `discovery.source_kinds`
- `files[].path`
- `files[].format`
- `files[].sha256`

No source file is loaded unless it is listed in the manifest.

## Source Rules

- Roots are explicit and passed to `SourceResolver`.
- Default root is `.bago/core/context_patterns`.
- Recursion is not used for source discovery.
- File paths must be relative and stay inside the authorized root.
- Symlinks are rejected by the core pack policy.
- Duplicate resolved paths are rejected.
- Remote and generated sources are disabled for the core pack.

## Canonical Identity

Pattern identity is:

```text
domain:category:name:version
```

The `name` is derived from normalized content plus a stable content hash suffix, not from the file name.

## Supported Formats

- JSON: object maps or lists, duplicate keys rejected.
- TOML: parsed by `tomllib`, duplicate keys rejected by the parser.
- CSV: UTF-8, comma delimiter, exact headers `category,phrase`.
- Markdown: conventional headings plus bullet lists only.
- YAML simple: maps and scalar lists only; tags, anchors, aliases, merges, and complex tokens rejected.
- Blob/TXT: category header followed by one scalar value per line.

## Merge Semantics

The current effective values use:

- `workspace_markers`: union without duplicates.
- `workspace_followups`: union without duplicates.

Ordering is deterministic:

1. manifest priority descending
2. pack version
3. canonical id ascending

## Public API

Consumers use:

- `load_context_patterns()`
- `load_pattern_registry()`
- `PatternRegistry.get_by_id()`
- `PatternRegistry.list_by_domain()`
- `PatternRegistry.filter_by_state()`
- `PatternRegistry.effective_category()`
- `PatternRegistry.status()`

Consumers must not read pattern files directly.

## Implemented Scope

- Mandatory manifest for the packaged core context pack.
- Declared-file loading only.
- SHA256 integrity per declared file.
- Root escape prevention.
- Symlink rejection for the core pack.
- Duplicate resolved path rejection.
- JSON, TOML, CSV, Markdown, simple YAML, and blob/TXT decoding.
- Duplicate-key rejection for JSON and TOML.
- Deterministic canonical ids independent of source file names.
- Deterministic precedence and union-without-duplicates for active context categories.
- Immutable snapshot object exposed through `PatternRegistry`.
- Rollback-preserving `ReloadCoordinator` for failed reloads.
- Read-only consumer path through `load_context_patterns()`.

## Not Yet Certified / Pending

- Non-interactive CLI family: `bago patterns validate/list/show/explain/diff/migrate/reload/cache/snapshot/doctor`.
- Interactive `/patterns` menu family.
- React views/actions backed by the same backend contracts.
- Full dependency graph activation with topological ordering and cycle diagnostics.
- Field-level provenance for effective values.
- Full migration chain with versioned audit records.
- Cache keys and atomic cache invalidation.
- Structured observability and operational budgets measured on real data.
- Property-based tests, fuzzing, cross-OS hash repeatability, and mutation suite.
- Pattern reload receipts integrated with the general receipt ledger.
