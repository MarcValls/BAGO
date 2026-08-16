---
applyTo: "frontend/**"
---

# BAGO Frontend Engineering v1.0

Use the `bago-frontend-engineering` skill for material frontend work.

Authority:
- backend-confirmed session/provider/model/security/capability/execution state wins;
- frontend contracts/stores may represent or cache that state, not silently redefine it;
- current BAGO `ui-canonical-contract`, visual grammar and state taxonomy are authoritative for their declared scopes.

Engineering rules:
- trace material behavior as interaction → component → state owner → API/transport → backend authority when applicable → response → render → test;
- use shared UI state only for genuinely shared presentation concerns; keep ephemeral state local;
- preserve secret/token non-persistence;
- keep one canonical destination-navigation mechanism;
- use the existing API client layer rather than ad-hoc HTTP in components;
- prefer semantic CSS tokens when an applicable token exists;
- implement loading, empty, error and blocked states according to functional scope;
- do not split large files by size alone; refactor when responsibility/coupling/testability evidence supports it;
- do not create visible UI for a capability whose functional contract cannot be established.

Lifecycle:
AUDIT/TRACE are read-only. IMPLEMENT may edit only authorized scope. VERIFY requires real evidence on the exact final state. Build success alone is not validation.

Current preferred root gates when applicable: `npm run typecheck`, `npm run test:frontend`, `npm run build`. Refresh repository scripts before relying on them.
