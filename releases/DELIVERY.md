# BAGO 4.9.0 - Historical delivery snapshot (obsolete)

> Not current-candidate evidence. The commit/tag values below are retained as
> historical claims and conflict with the verified tag identity documented in
> `releases/INDEX.md`. They must not be used to validate this remediation.

## Release Information

| Property | Value |
|----------|-------|
| **Version** | 4.9.0 |
| **Release Date** | August 18, 2026 |
| **Build Status** | ✓ Stable |
| **Installer Status** | ✓ Ready |
| **Git Commit** | 4ad27a0a4a154d20740d62bfbc20c888a0f2f3cc |
| **Git Tag** | v4.9.0 (f1dcd765f63989e1a66a774c8fba9805fdfef3ee) |

## What's Included

### 🚀 Main Deliverable

**BAGO-Installation-Manager-4.9.0-win-x64.exe** (97.64 MB)
- Official Electron-builder NSIS installer
- Single-click installation for Windows users
- Automatic admin elevation (UAC)
- Built-in backend + frontend + Electron viewer payload
- SHA256: `9AE9507F435DEBF978A3D268E5B59FC98BD37F45567E652DD976B4B85A012230`

### 📦 Update Package

**bago-v4.9.0.zip** (1.72 MB)
- Thin update package used by the installer/auto-updater
- SHA256: `7D67CCDE3BF77702DAF0F79941DA662F316AF7FFF1DF48CBAFFD902CAFCD8F65`

### 📦 Offline / Legacy Alternatives

| File | Usage | Best For |
|------|-------|----------|
| `bago-4.9.0-setup.exe` | Double-click offline installer (143.6 MB) | Air-gapped or slow connections |
| `Install-BAGO.ps1` | `powershell -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1` | Power users, CI/CD |
| `install-bago-setup.cmd` | `install-bago-setup.cmd` | Command line, batch scripts |
| `install-v4.ps1` | `install-v4.ps1 [-PackageZip bago-v4.9.0.zip]` | Package-driven installation |

### 📚 Documentation

| Document | Purpose |
|----------|---------|
| `INSTALL.md` | Quick start guide with installation methods |
| `README-INSTALLERS.md` | Comprehensive installer documentation |
| `RELEASE_NOTES_REAL.md` | Feature release notes |
| `MANIFEST.md` | Detailed file manifest |

### 🧹 Cleanup

Legacy/superseded files in the `releases/` folder:
- `bago-install.ps1` - Old script (use `Install-BAGO.ps1` or `install-v4.ps1`)
- `bago-installer.nsi` - Original NSIS installer (replaced by official NSIS target)
- `bago-4.9.0-installer.ps1` - Renamed to `Install-BAGO.ps1`
- `run-install.cmd` - Old batch wrapper (use `install-bago-setup.cmd`)

## Installation

### Recommended: Official EXE Method (Easiest)
```
1. Download BAGO-Installation-Manager-4.9.0-win-x64.exe
2. Double-click to start installation
3. Accept the admin prompt (UAC)
4. Wait 5-10 minutes for completion
5. Launch BAGO from Start Menu or Desktop
```

### Alternative: PowerShell / Package Method
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```

## What Gets Installed

**Location**: `%LOCALAPPDATA%\BAGO` (typically `C:\Users\Username\AppData\Local\BAGO`)

**Contents**:
- ✓ Backend Python environment (`backend/`)
- ✓ Built frontend assets
- ✓ Packaged Electron application (`BAGO.exe`)
- ✓ Runtime wrapper `backend/.bago/bin/bago.py`
- ✓ Windows shortcuts (Start Menu + Desktop)
- ✓ Registry entries (uninstall support)

**Total Size**: ~800 MB (including Electron + dependencies)

**Installation Time**: 5-10 minutes

## System Requirements

- **OS**: Windows 10/11 (Windows 7/8.x no longer supported)
- **Architecture**: x64 (x86 not supported)
- **RAM**: Minimum 4 GB (8 GB recommended)
- **Disk Space**: 2 GB free space (for installation)
- **Internet**: Required for first installation unless using offline installer
- **Prerequisites**: Git, Node.js 20+, Python 3.14+

## Verification

### After Installation
```powershell
# Verify BAGO is installed
Test-Path "$env:LOCALAPPDATA\BAGO\backend\.bago\bin\bago.py"
Test-Path "$env:LOCALAPPDATA\BAGO\BAGO.exe"

# Should return: True
```

### Checksum Verification
```powershell
$hash = (Get-FileHash BAGO-Installation-Manager-4.9.0-win-x64.exe -Algorithm SHA256).Hash
$expected = "9AE9507F435DEBF978A3D268E5B59FC98BD37F45567E652DD976B4B85A012230"
$hash -eq $expected  # Should be: True
```

## Support

### Uninstall
```powershell
# Use Windows Settings → Apps, or run:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

### Update
Download and run the latest `BAGO-Installation-Manager-{version}-win-x64.exe` to update.

### Troubleshooting
See `INSTALL.md` troubleshooting section for:
- Installation failures
- Prerequisites issues
- Runtime problems
- Port conflicts

### Issues & Support
- **GitHub Issues**: https://github.com/MarcValls/BAGO/issues
- **GitHub Discussions**: https://github.com/MarcValls/BAGO/discussions

## Technical Details

### Installation Pipeline (Official NSIS)

The official installer performs these steps in order:

1. ✓ Extract bundled backend, frontend, and Electron payload
2. ✓ Validate prerequisites (Git, Node.js, Python)
3. ✓ Install Python backend environment
4. ✓ Install npm dependencies (root + electron-viewer)
5. ✓ Build frontend assets
6. ✓ Package Electron application
7. ✓ Create Windows shortcuts
8. ✓ Register in Windows registry
9. ✓ Verify all components

### Build Specifications

- **Node Version**: 20.14.0+
- **Python Version**: 3.14+
- **Electron Version**: 42.3.0 (embedded in electron-viewer)
- **Backend**: Python FastAPI
- **Frontend**: React
- **UI Framework**: Custom React components
- **CI numpy pin**: 2.4.4 (fixes Python 3.14 Windows import crash)

## Release Notes

See `RELEASE_NOTES_REAL.md` for:
- Features new in 4.9.0
- Bug fixes
- Known limitations
- Migration notes from 4.8.x

## Distribution

### For Public Release
- `BAGO-Installation-Manager-4.9.0-win-x64.exe` ← Main file
- `BAGO-Installation-Manager-4.9.0-win-x64.exe.sha256` (verification)
- `bago-v4.9.0.zip` (thin update package)
- `bago-v4.9.0.zip.sha256` (verification)
- `INSTALL.md` (quick guide)
- `README-INSTALLERS.md` (complete guide)

### For GitHub Release
All of the above plus:
- `RELEASE_NOTES_REAL.md`
- `MANIFEST.md`
- `latest.yml` (auto-update metadata)

### For Offline Distribution
Include the legacy offline installer if needed:
- `bago-4.9.0-setup.exe` (SHA256: `D2DD1004230346CB2648E2070408AE2C6DEF65AB6F9DB9822BAB4ABBCEBB8C72`)

---

**Status**: ✓ Ready for Distribution

**Installer Quality**: ✓ Verified via canonical release gate

**Documentation**: ✓ Complete

**Version**: BAGO 4.9.0 - August 18, 2026
