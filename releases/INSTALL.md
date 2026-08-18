# BAGO 4.9.0 Installation Guide

## Quick Start

### Choose Your Installation Method

#### Method 1: Official NSIS Installer (Easiest) ⭐
**File:** `BAGO-Installation-Manager-4.9.0-win-x64.exe`
- Official electron-builder NSIS installer
- Bundles backend, frontend and Electron payload
- Single-file experience for end users
- Automatic administrator elevation
- Best for most users
- SHA256: `9AE9507F435DEBF978A3D268E5B59FC98BD37F45567E652DD976B4B85A012230`

#### Method 2: Package-Driven PowerShell Installer (Recommended for Automation)
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```
- Uses the thin `bago-v4.9.0.zip` update package
- Fast, reproducible deployment
- Best for scripts and CI/CD pipelines
- Full control and transparency

#### Method 3: Legacy PowerShell Script
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```
- Direct execution without wrapper
- Clones repository and builds locally
- Best for development / non-packaged installs

#### Method 4: Batch Wrapper (Command Line)
```cmd
install-bago-setup.cmd
```
- Lightweight wrapper around legacy PowerShell installer
- Best for command-line tools and legacy systems

#### Method 5: VBS Launcher (Alternative GUI)
**File:** `install-bago-setup.vbs`
- Double-click to start
- Windows Script Host based launcher
- Alternative if PowerShell is restricted

#### Method 6: Manual Installation

```powershell
# Clone repository
git clone --depth 1 --branch v4.9.0 https://github.com/MarcValls/BAGO.git
cd BAGO

# Install dependencies
npm install
cd electron-viewer && npm install && cd ..

# Configure backend
powershell -NoProfile -ExecutionPolicy Bypass -File backend\install-v4.ps1 -Mode Express -SkipTests

# Build and package
npm run build
cd electron-viewer && npx electron-builder --dir && cd ..

# Run
.\electron-viewer\dist\win-unpacked\BAGO.exe
```

## Requirements

### For EXE installer (`BAGO-Installation-Manager-4.9.0-win-x64.exe`)
- **Windows 10/11** x64
- Internet connection during installation (unless using offline legacy installer)

### For script/manual methods
- **Git**: https://git-scm.com
- **Node.js 20+**: https://nodejs.org
- **Python 3.14+**: https://python.org

## Installation Directory

Default: `C:\Users\{username}\AppData\Local\BAGO`

## Uninstallation

Use Windows Settings → Apps → BAGO → Uninstall, or run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

Or manually:

```powershell
Remove-Item $env:LOCALAPPDATA\BAGO -Recurse -Force
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BAGO" -Recurse -Force
```

## Troubleshooting

### Installation Fails

1. **Check prerequisites**: Ensure Git, Node.js, and Python are installed and in PATH
   ```powershell
   git --version
   node --version
   python --version
   ```

2. **Check internet connection**: The installer downloads Node modules and Electron

3. **Disable antivirus**: Temporarily disable antivirus during installation

4. **Run as Administrator**: Some installations may require admin privileges

### Runtime Issues

1. **BAGO.exe won't start**: Check Windows firewall settings

2. **Python not found**: Ensure Python is in PATH:
   ```powershell
   $env:PATH -split ";" | Where-Object { $_ -match "Python" }
   ```

3. **Port conflicts**: BAGO uses ports 5000 (backend) and 3000 (frontend)

## Building from Source

If you want to modify BAGO:

```powershell
# Navigate to repository root
cd C:\Users\{username}\AppData\Local\BAGO

# Make changes
# ...

# Rebuild
npm run build

# Repackage
cd electron-viewer
npx electron-builder --dir
```

## Version Info

- **Version**: 4.9.0
- **Release**: August 18, 2026
- **Git Commit**: 4ad27a0a4a154d20740d62bfbc20c888a0f2f3cc
- **Git Tag**: v4.9.0 (f1dcd765f63989e1a66a774c8fba9805fdfef3ee)
- **Build**: Electron 42.3.0

## Support

For issues and questions:
- GitHub Issues: https://github.com/MarcValls/BAGO/issues
- GitHub Discussions: https://github.com/MarcValls/BAGO/discussions
