# BAGO 4.8.7 Release Readiness Checklist

## Release Status: 🔄 IN PROGRESS

### What's Complete

| Component | Status | Details |
|-----------|--------|---------|
| **Bug fixes** | ✅ | GitHub detection endpoint routed to handler that exposes `installed`; sidebar drawers for tools/pipeline/capabilities registered |
| **Backend Tests** | ✅ | 928 passed / 13 skipped |
| **Frontend Tests** | ✅ | 99 passed |
| **Version Coherence** | ✅ | Repo, `release_version.txt`, installer, and README all at `4.8.7` |
| **Installation Manager** | ⬜ | `BAGO-Installation-Manager-4.8.7-win-x64.exe` pending rebuild |
| **Distribution Package** | ⬜ | `bago-v4.8.7.zip` pending rebuild |
| **Local Installer Smoke** | ⬜ | `bago doctor` on installed runtime pending |
| **CI Source Checks** | ⬜ | `validate`, `Validate source`, and CodeQL pending |

### Files NOT in Git (Generated Release Artifacts)

| Artifact | Purpose |
|----------|---------|
| `backend/release/v4/BAGO-Installation-Manager-4.8.7-win-x64.exe` | Windows setup (download + install) |
| `backend/release/v4/BAGO-Installation-Manager-4.8.7-win-x64.exe.sha256` | SHA256 sidecar |
| `backend/release/v4/bago-v4.8.7.zip` | Thin runtime payload for the manager / remote install |
| `backend/release/v4/bago-v4.8.7.zip.sha256` | SHA256 sidecar |

These live under `backend/release/v4/` (gitignored) and are uploaded to the GitHub Release.

### Release Workflow

**For Users (recommended path):**

1. Download `BAGO-Installation-Manager-4.8.7-win-x64.exe` from [GitHub Releases v4.8.7](https://github.com/MarcValls/BAGO/releases/tag/v4.8.7).
2. Run it. It installs backend, frontend build, Electron viewer, and creates Desktop / Start Menu shortcuts.
3. Double-click the shortcut. Backend starts on `http://127.0.0.1:8080` and the Electron viewer opens. Closing the window stops the backend.

**For Maintainers:**

```powershell
# Full build
npm run build

# Distribution package
cd backend
python scripts/package_v4.py --output-dir release/v4 --release-version 4.8.7

# Installation Manager
cd ../electron-viewer
npm run dist
```

### Post-Release Checklist

- [x] Bump all canonical version files to `4.8.7`
- [x] Update README badges, release table, and installer references
- [ ] Rebuild release artifacts and verify checksums
- [ ] Run backend tests and integral smoke
- [ ] Merge `fix/drift-4.8.6` into `main`
- [ ] Create and push Git tag `v4.8.7`
- [ ] Create GitHub Release `v4.8.7` and upload artifacts + sidecars
- [ ] Set release as latest

---

**Release Date:** 2026-08-16  
**Next Update:** When BAGO source code changes
