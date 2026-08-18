# BAGO 4.9.0 Installers

## Available Installation Packages

| File | Method | For Users | Notes |
|------|--------|-----------|-------|
| **BAGO-Installation-Manager-4.9.0-win-x64.exe** | NSIS GUI | ✓ Recommended | Official installer, all-in-one |
| **bago-v4.9.0.zip** | Thin update package | ✓ Automation | Used with `install-v4.ps1` |
| **install-v4.ps1** | PowerShell Package | ✓ CI/CD / Fast installs | Reproducible, scriptable |
| **Install-BAGO.ps1** | PowerShell Source | ✓ Power Users | Clones and builds from source |
| **install-bago-setup.cmd** | Batch File | ✓ Developers | Legacy command-line wrapper |
| **install-bago-setup.vbs** | VBS Launcher | ✓ Alternative | GUI-based, WSH alternative |
| **bago-installer-launcher.ps1** | PowerShell GUI | ✓ Automation | Pretty output wrapper |

## Installation Files

### Official EXE installer requirements
For end users, `BAGO-Installation-Manager-4.9.0-win-x64.exe` is self-contained:

1. Download `BAGO-Installation-Manager-4.9.0-win-x64.exe`
2. Double-click it
3. Accept the UAC prompt
4. Wait 5-10 minutes

No extra ZIPs or `.ps1` files are required from the user.

### Package-driven requirements
For automation or fast installs, pair `bago-v4.9.0.zip` with `install-v4.ps1`.

## How to Use Each Method

### 1. Official EXE Installer (Recommended for End Users)

```
1. Download BAGO-Installation-Manager-4.9.0-win-x64.exe
2. Double-click it
3. Accept the admin prompt (UAC) if requested
4. Wait for installation to complete
```

**Advantages:**
- No technical knowledge required
- Single clickable file
- Automatic admin elevation
- Full payload bundled (no extra downloads)

**Checksum:**
```powershell
(Get-FileHash BAGO-Installation-Manager-4.9.0-win-x64.exe -Algorithm SHA256).Hash
# Should equal: 9AE9507F435DEBF978A3D268E5B59FC98BD37F45567E652DD976B4B85A012230
```

### 2. Package-Driven PowerShell (Recommended for Automation)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```

**Advantages:**
- Fast (thin package)
- Reproducible
- Full transparency
- Easy to debug
- Perfect for CI/CD
- Scriptable parameters

**Parameters:**
```powershell
# Custom install directory
-InstallDir "C:\MyBAGO"

# Custom package source
-PackageZip "\\server\share\bago-v4.9.0.zip"
```

### 3. Legacy PowerShell Script (Source Install)

```powershell
# Open PowerShell as Administrator
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```

**Advantages:**
- Direct, no wrapper
- Clones repo at runtime
- Full transparency
- Scriptable parameters

**Parameters:**
```powershell
# Custom install directory
-InstallDir "C:\MyBAGO"

# Custom git reference
-AppGitRef "develop"
-AppGitSha "abc123def456..."

# Custom repository
-AppRepo "https://github.com/custom/repo.git"
```

### 4. Batch Wrapper (Command Line)

```cmd
cd C:\path\to\installers
install-bago-setup.cmd
```

**Advantages:**
- No PowerShell configuration needed
- Simple for batch scripts
- Legacy Windows compatible

### 5. VBS Launcher (Alternative GUI)

```
1. Place install-bago-setup.vbs with other installer files
2. Double-click install-bago-setup.vbs
3. Windows will run it through Windows Script Host
4. Follow the installation prompts
```

**Advantages:**
- GUI feedback
- Alternative if PowerShell is restricted
- Shows installation status

## What Happens During Installation

### Official NSIS installer

1. ✓ Extract bundled backend, frontend and Electron payload
2. ✓ Install Python backend environment
3. ✓ Install npm dependencies
4. ✓ Build frontend assets
5. ✓ Create Windows shortcuts (Start Menu, Desktop)
6. ✓ Register application in Windows registry
7. ✓ Verify all components are present

### Package-driven installer

1. ✓ Validate package checksum
2. ✓ Extract `bago-v4.9.0.zip` to install directory
3. ✓ Install runtime dependencies
4. ✓ Build/package as needed
5. ✓ Create shortcuts and registry entries
6. ✓ Verify all components

### Legacy source installer

1. ✓ Validate prerequisites (Git, Node.js, Python)
2. ✓ Clone BAGO repository from GitHub
3. ✓ Install all npm dependencies (root + electron-viewer)
4. ✓ Install backend dependencies (Python environment)
5. ✓ Build frontend assets
6. ✓ Package Electron application
7. ✓ Create Windows shortcuts (Start Menu, Desktop)
8. ✓ Register application in Windows registry
9. ✓ Verify all components are present

**Installation Time**:
- Official EXE: 5-10 minutes
- Package-driven: 3-5 minutes
- Source install: 10-15 minutes (depends on internet speed and hardware)

**Installed Location**: `%LOCALAPPDATA%\BAGO` (usually `C:\Users\YourUsername\AppData\Local\BAGO`)

## After Installation

### Launch BAGO
- Double-click the desktop shortcut
- Or search for "BAGO" in Windows Start Menu
- The executable is `%LOCALAPPDATA%\BAGO\BAGO.exe`

### Uninstall BAGO
Use Windows Settings → Apps → BAGO → Uninstall, or run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

### Update BAGO
Download the latest `BAGO-Installation-Manager-{version}-win-x64.exe` from GitHub Releases and run it.

## Troubleshooting

### "Windows protected your PC" Warning

If Windows SmartScreen blocks the EXE:
1. Click "More info"
2. Click "Run anyway"
3. This is normal for new applications

### Prerequisites Not Found

Run the installer again—it will clearly report what's missing:

```
ERROR: Git not found in PATH
  Please install from: https://git-scm.com
```

Install the missing tool and try again.

### Installation Fails Halfway

Common causes and solutions:

| Error | Solution |
|-------|----------|
| `ENOENT` or file not found | Check internet connection, ensure ZIP files are accessible |
| Port 5000/3000 in use | Close other applications using those ports |
| Python not in PATH | Reinstall Python and ensure "Add to PATH" is checked |
| Disk space | Free up at least 2 GB |
| Antivirus blocks | Temporarily disable antivirus during installation |

### Running as Administrator

All methods require administrator privileges because they:
- Install to Program Data
- Create Windows shortcuts
- Modify registry
- Open network ports

On Windows 11:
1. Right-click the EXE → "Run as administrator"
2. Or PowerShell → Right-click → "Run as Administrator"

## File Checksums

Verify installation package integrity:

```powershell
# Official installer
(Get-FileHash BAGO-Installation-Manager-4.9.0-win-x64.exe -Algorithm SHA256).Hash

# Update package
(Get-FileHash bago-v4.9.0.zip -Algorithm SHA256).Hash
```

Compare against the corresponding `.sha256` files.

## Version Information

- **BAGO Version**: 4.9.0
- **Release Date**: August 18, 2026
- **Node.js Required**: 20.0 or later
- **Python Required**: 3.14 or later
- **Git Required**: 2.20 or later
- **Windows**: Windows 10/11 x64

## Support

For installation issues:
- **GitHub Issues**: https://github.com/MarcValls/BAGO/issues
- **GitHub Discussions**: https://github.com/MarcValls/BAGO/discussions
- **Check INSTALL.md**: Troubleshooting section

---

**Note:** The official EXE and the package-driven method produce identical installations. Use whichever is most convenient for your situation.
