---
applyTo: "releases/**,backend/release/**,install*.ps1,install*.sh,ARRANCAR_BAGO.bat,package.json,frontend/package.json,electron-viewer/package.json"
---

# BAGO release instructions

Release work must keep version sources coherent and build from an immutable/tagged reference when producing publishable artifacts. Never package credentials, live sessions, operational state, caches, logs or unrelated local artifacts. Installation/runtime claims require checks appropriate to the produced artifact; source tests alone do not prove an installer. Preserve rollback/backup behavior for installed runtime changes.
