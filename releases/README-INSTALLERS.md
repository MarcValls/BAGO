# BAGO 4.8.2 Installers

## Available Installation Packages

| File | Method | For Users | Notes |
|------|--------|-----------|-------|
| **bago-4.8.2-setup.exe** | GUI Clickable | ✓ Recommended | Easy, requires admin, all-in-one |
| **Install-BAGO.ps1** | PowerShell Script | ✓ Power Users | Direct, full transparency, scriptable |
| **install-bago-setup.cmd** | Batch File | ✓ Developers | Command-line wrapper, CI/CD friendly |
| **install-bago-setup.vbs** | VBS Launcher | ✓ Alternative | GUI-based, WSH alternative |
| **bago-installer-launcher.ps1** | PowerShell GUI | ✓ Automation | Pretty output, easy debugging |

## Installation Files

### EXE installer requirements
For end users, `bago-4.8.2-setup.exe` is self-contained from the user perspective:

1. Download `bago-4.8.2-setup.exe`
2. Double-click it

No extra ZIPs or `.ps1` files are required from the user.

## How to Use Each Method

### 1. EXE Installer (Recommended for End Users)

```
1. Download bago-4.8.2-setup.exe
2. Double-click bago-4.8.2-setup.exe
3. Accept the admin prompt (UAC) if requested
4. Wait for installation to complete
```

**Advantages:**
- No technical knowledge required
- Single clickable file
- Automatic admin elevation
- Full installer output in console

### 2. PowerShell Script (Recommended for Automation)

```powershell
# Open PowerShell as Administrator
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```

**Advantages:**
- Direct, no wrapper
- Full transparency
- Easy to debug
- Perfect for CI/CD
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

### 3. Batch Wrapper (Command Line)

```cmd
cd C:\path\to\installers
install-bago-setup.cmd
```

**Advantages:**
- No PowerShell configuration needed
- Simple for batch scripts
- Legacy Windows compatible

### 4. VBS Launcher (Alternative GUI)

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

## Installation What Happens

Both the EXE and PowerShell installer will:

1. ✓ Validate prerequisites (Git, Node.js, Python)
2. ✓ Clone BAGO repository from GitHub
3. ✓ Install all npm dependencies (root + electron-viewer)
4. ✓ Install backend dependencies (Python environment)
5. ✓ Build frontend assets
6. ✓ Package Electron application
7. ✓ Create Windows shortcuts (Start Menu, Desktop)
8. ✓ Register application in Windows registry
9. ✓ Verify all components are present

**Installation Time**: 10-15 minutes (depends on internet speed and hardware)

**Installed Location**: `%LOCALAPPDATA%\BAGO` (usually `C:\Users\YourUsername\AppData\Local\BAGO`)

## After Installation

### Launch BAGO
- Double-click the desktop shortcut
- Or search for "BAGO" in Windows Start Menu

### Uninstall BAGO
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Uninstall-BAGO.ps1
```

### Update BAGO
```powershell
# Clean reinstall by running the installer again
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1
```

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
$file = "bago-4.8.2-setup.exe"
(Get-FileHash $file -Algorithm SHA256).Hash
```

Compare against `bago-4.8.2-setup.exe.sha256`

## Version Information

- **BAGO Version**: 4.8.2
- **Release Date**: August 7, 2026
- **Node.js Required**: 20.0 or later
- **Python Required**: 3.11 or later
- **Git Required**: 2.20 or later
- **Windows**: Windows 7 SP1 or later

## Support

For installation issues:
- **GitHub Issues**: https://github.com/MarcValls/BAGO/issues
- **GitHub Discussions**: https://github.com/MarcValls/BAGO/discussions
- **Check INSTALL.md**: Troubleshooting section

---

**Note:** All installer methods are equivalent—use whichever is most convenient for your situation.
