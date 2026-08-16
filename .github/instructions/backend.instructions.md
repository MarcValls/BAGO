---
applyTo: "backend/**"
---

# BAGO backend instructions

Before material backend changes, inspect relevant `backend/docs/ARCHITECTURE.md`, `SECURITY.md`, `CLAIMS.md`, `TESTING.md` and the concrete handlers/services/tests in scope. Backend state is authoritative over UI. Preserve local-only API defaults, fail-closed permission checks and separation of sessions/providers/evidence. Do not weaken validation or security gates to make tests pass. For backend claims, map behavior to executable proof.
