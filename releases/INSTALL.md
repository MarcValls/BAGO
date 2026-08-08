# BAGO 4.8.2 Installation Guide

## Quick Start

### Choose Your Installation Method

#### Method 1: NSIS Installer (Easiest) ⭐
**File:** `bago-4.8.2-setup.exe`
- Windows installer with graphical wizard
- Better antivirus compatibility (NSIS has trusted reputation)
- Single-file experience for end users (no ZIP + PS1 manual steps)
- Best for most users
- No SmartScreen warnings

#### Method 2: PowerShell Script (Recommended for Automation)
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```
- Direct execution without wrapper
- No antivirus warnings
- Best for scripts and CI/CD pipelines
- Full control and transparency

#### Method 3: Batch Wrapper (Command Line)
```cmd
install-bago-setup.cmd
```
- Lightweight wrapper around PowerShell installer
- Best for command-line tools and legacy systems

#### Method 4: VBS Launcher (Alternative GUI)
**File:** `install-bago-setup.vbs`
- Double-click to start
- Windows Script Host based launcher
- Alternative if PowerShell has restrictions

#### Method 5: Manual Installation

```powershell
# Clone repository
git clone --depth 1 --branch main https://github.com/MarcValls/BAGO.git
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

### For EXE installer (`bago-4.8.2-setup.exe`)
- **Windows 7+** or **Windows Server 2008 R2+**
- Internet connection during installation

### For script/manual methods
- **Git**: https://git-scm.com
- **Node.js 20+**: https://nodejs.org
- **Python 3.11+**: https://python.org

## Installation Directory

Default: `C:\Users\{username}\AppData\Local\BAGO`

## Uninstallation

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

Or manually:

```powershell
Remove-Item $env:LOCALAPPDATA\BAGO -Recurse -Force
Remove-Item $env:APPDATA\Microsoft\Windows\Start\ Menu\Programs\BAGO -Recurse -Force
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

- **Version**: 4.8.2
- **Release**: August 7, 2026
- **Git Commit**: 9e1c49bb3f5388b991ed21ad0287059f4d4d9875
- **Build**: Electron 42.3.0

## Support

For issues and questions:
- GitHub Issues: https://github.com/MarcValls/BAGO/issues
- GitHub Discussions: https://github.com/MarcValls/BAGO/discussions
