# Decisions

Record architectural or product decisions that affect canon here.

## 2026-08-30 — Adopt BAGOx v1.3-RC1-FIX2 Codex overlay

- Decision: adopt the stable Codex behavioral projection of `BAGOx Behavior Package v1.3-RC1-FIX2` as the BAGO repository overlay.
- Authority/provenance: external package status `ACTIVE · CANON`, manifest SHA-256 `f916e385ba55cff4b27dd9696c42b3d22dbb83ad00595572e77385766c9fb3eb`.
- Scope: `AGENTS.md`, the overlay verifier, and its contract fixture only.
- Excluded: BAGO runtime, application canon, persistent state, schemas, templates, hooks, and BAGOx-only state mechanisms.
- Verification: candidate-bound BAGO overlay gate passes on the adopted candidate; the repository-wide state remains subject to its own validation contract.
