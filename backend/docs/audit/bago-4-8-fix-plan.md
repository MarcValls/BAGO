# BAGO 4.8 fix plan

## Decision

`project_root/.gabo` is the canonical workspace root.
`.bago` inside an external project remains legacy-only.

## Immediate sequence

### 00. Freeze baseline

- Record current failing tests and authority map.
- Do not change behavior yet.

### 01. Repair release evidence

- Align `test_security_release.py` with `release_version.txt`.
- Replace the stale `release_4_7_0` evidence reference with the current release
  evidence directory.
- Keep release packaging verification explicit.

### 02. Validate path normalization

- Keep Code Forge contracts canonical in POSIX-relative form.
- Use `src/demo.py` as the contract form; render Windows separators only when
  strictly needed.
- The current compiler test is already green.

### 03. Cartograph current authority

- Document who detects workspace roots.
- Document who writes legacy `.bago` artifacts.
- Document who derives permissions and chat gating.
- Keep this step read-only.

## Corrected near-term roadmap

### 04. Workspace service

- Introduce canonical `.gabo` workspace handling only after the map is stable.

### 05. Legacy demotion

- Stop creating new canonical workspace artifacts under `.bago`.

### 06. Chat gate

- Block model calls before thread creation when workspace is not confirmed.

### 07. Context envelopes and receipts

- Promote `workspace_root` as the authority field.

### 08. Backend permissions

- Expose backend-derived `allowed_actions`, `blocked_actions`, and
  `permissions`.

### 09. UI fidelity

- Render backend state; do not infer permissions locally.

## Current validation note

The baseline is not clean yet. The release test currently fails on
`features.auto_allow_tools`, not only on the stale evidence path, so the plan
must address that first failure as well.

