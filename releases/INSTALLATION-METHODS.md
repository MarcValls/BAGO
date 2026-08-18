# BAGO 4.9.0 - Installation Methods Comparison

## Quick Decision Guide

| Need | Use | File |
|------|-----|------|
| **"Just let me install it"** | Official NSIS EXE | `BAGO-Installation-Manager-4.9.0-win-x64.exe` |
| **"I need fast/reproducible automation"** | Package-driven PowerShell | `install-v4.ps1 -PackageZip bago-v4.9.0.zip` |
| **"I want to clone and build from source"** | PowerShell Script | `Install-BAGO.ps1` |
| **"I prefer command line"** | Batch Wrapper | `install-bago-setup.cmd` |
| **"I need documentation"** | Read First | `INSTALL.md` or `README-INSTALLERS.md` |

---

## Detailed Comparison

### 1. ⭐ Official NSIS EXE Installer (Easiest)

**File**: `BAGO-Installation-Manager-4.9.0-win-x64.exe` (97.64 MB)

**How to use**:
```
Double-click the file and follow prompts
```

**Pros**:
- ✓ Single file, no setup needed
- ✓ Automatic admin elevation
- ✓ Full installation output shown
- ✓ No PowerShell configuration needed
- ✓ Standard Windows executable
- ✓ Full payload bundled (no extra downloads)
- ✓ Easy for non-technical users

**Cons**:
- ✗ No scriptable parameters
- ✗ Larger file size (~98 MB)
- ✗ Must download full installer each update

**Best for**: End users, GUI-preferred, first-time installers

**Installation time**: 5-10 minutes

---

### 2. 📦 Package-Driven PowerShell (Best for Automation)

**File**: `install-v4.ps1` + `bago-v4.9.0.zip` (1.72 MB)

**How to use**:
```powershell
# Option A: Simple execution
powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip

# Option B: With parameters
powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 `
  -PackageZip bago-v4.9.0.zip `
  -InstallDir "C:\CustomBAGO"
```

**Available Parameters**:
```powershell
-PackageZip "path"         # Path to bago-v4.9.0.zip
-InstallDir "path"         # Custom installation directory
```

**Pros**:
- ✓ Fast, reproducible deployment
- ✓ Fully scriptable and customizable
- ✓ Best for CI/CD pipelines
- ✓ Small payload to transfer
- ✓ Transparent—see all output
- ✓ Can be run silently

**Cons**:
- ✗ Requires PowerShell knowledge
- ✗ Need two files (script + zip)
- ✗ Need to run as Administrator manually

**Best for**: DevOps, CI/CD, automation, fast deployments

**Installation time**: 3-5 minutes

**Example in CI/CD**:
```yaml
# GitHub Actions example
- name: Install BAGO
  run: |
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 `
      -PackageZip bago-v4.9.0.zip `
      -InstallDir "D:\BAGO-CI"
```

---

### 3. 🔧 Legacy PowerShell Script (Source Install)

**File**: `Install-BAGO.ps1` (6.5 KB)

**How to use**:
```powershell
# Option A: Simple execution
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1

# Option B: With parameters
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1 `
  -InstallDir "C:\CustomBAGO" `
  -AppGitRef "develop"
```

**Available Parameters**:
```powershell
-InstallDir "path"        # Custom installation directory
-AppGitRef "branch"       # Git branch (default: main)
-AppGitSha "sha1234..."   # Specific commit hash
-AppRepo "git-url"        # Custom repository URL
```

**Pros**:
- ✓ Direct execution, no wrapper
- ✓ Fully scriptable and customizable
- ✓ Easy to debug
- ✓ Transparent—see all output
- ✓ Can be run silently
- ✓ Smallest file size (6.5 KB)

**Cons**:
- ✗ Requires internet + Git clone
- ✗ Requires PowerShell knowledge
- ✗ Need to run as Administrator manually
- ✗ Requires ExecutionPolicy adjustment

**Best for**: Developers, custom source builds

**Installation time**: 10-15 minutes

---

### 4. 📟 Batch Wrapper (Command Line)

**File**: `install-bago-setup.cmd` (1.06 KB)

**How to use**:
```cmd
# Option A: Open cmd.exe and run
cd C:\path\to\installer
install-bago-setup.cmd

# Option B: Run from elsewhere
C:\path\to\install-bago-setup.cmd
```

**Pros**:
- ✓ No PowerShell configuration needed
- ✓ Works in cmd.exe and batch scripts
- ✓ Extremely small file
- ✓ Legacy Windows compatible
- ✓ Simple error handling
- ✓ Good for batch automation

**Cons**:
- ✗ Less powerful than PowerShell
- ✗ Can't use advanced parameters easily
- ✗ Still requires admin privileges

**Best for**: Batch scripts, command-line users, legacy systems

**Installation time**: 10-15 minutes

**Example**:
```batch
@echo off
REM Install BAGO in a batch script
call C:\installers\install-bago-setup.cmd
if %ERRORLEVEL% NEQ 0 (
    echo Installation failed
    exit /b 1
)
echo Installation successful
```

---

### 5. 🪟 VBS Launcher (Alternative GUI)

**File**: `install-bago-setup.vbs` (1.39 KB)

**How to use**:
```
1. Double-click install-bago-setup.vbs
2. Windows Script Host will execute it
3. Follow the installation prompts
```

**Pros**:
- ✓ GUI feedback
- ✓ Alternative if PowerShell is restricted
- ✓ Works on all Windows versions
- ✓ Automatic admin elevation
- ✓ Lightweight (1.39 KB)

**Cons**:
- ✗ Less transparent than PowerShell
- ✗ Limited error details
- ✗ WSH must be enabled (usually is)
- ✗ No parameters supported

**Best for**: Users with PowerShell restrictions, GUI preference

**Installation time**: 10-15 minutes

**Note**: Requires Windows Script Host enabled (default in most Windows)

---

## Feature Comparison Table

| Feature | NSIS EXE | Package PS | Source PS | Batch | VBS |
|---------|----------|------------|-----------|-------|-----|
| **File Size** | 97.64 MB | 6.5 KB + zip | 6.5 KB | 1.06 KB | 1.39 KB |
| **Double-click** | ✓ | ✗ | ✗ | ✗ | ✓ |
| **Command-line** | ✓ | ✓ | ✓ | ✓ | ✗ |
| **Scriptable** | ✗ | ✓ | ✓ | ✗ | ✗ |
| **Custom Parameters** | ✗ | ✓ | ✓ | Limited | ✗ |
| **Silent Execution** | ✗ | ✓ | ✓ | ✓ | ✗ |
| **Admin Auto-Elevate** | ✓ | ✗ | ✗ | ✗ | ✓ |
| **PowerShell Required** | ✗ | ✓ | ✓ | ✓ | ✗ |
| **Transparent Output** | ✓ | ✓ | ✓ | ✓ | ✗ |
| **CI/CD Friendly** | ✗ | ✓ | ✓ | ✓ | ✗ |
| **Fastest Install** | ~ | ✓ | ✗ | ✗ | ✗ |

---

## Recommended Usage Scenarios

### Scenario 1: End User on Windows 11
```
→ Use: BAGO-Installation-Manager-4.9.0-win-x64.exe
✓ Single click, automatic admin elevation, easiest experience
```

### Scenario 2: Fast CI/CD Deployment
```
→ Use: install-v4.ps1 -PackageZip bago-v4.9.0.zip
✓ Fast, reproducible, small payload
```

### Scenario 3: Developer Building from Source
```
→ Use: Install-BAGO.ps1 with parameters
✓ Full control, scriptable, easy to debug custom installations
```

### Scenario 4: Batch Deployment Script
```
→ Use: install-bago-setup.cmd in batch file
✓ Works in batch context, simple error handling
```

### Scenario 5: PowerShell Restricted Environment
```
→ Use: install-bago-setup.vbs or BAGO-Installation-Manager-4.9.0-win-x64.exe
✓ Bypasses PowerShell execution policy issues
```

### Scenario 6: Automation with Parameters
```
→ Use: install-v4.ps1 with -PackageZip and -InstallDir
✓ Only package-driven script supports thin payload parameters
```

---

## Which File to Distribute?

### Public Release (GitHub, Web)
**Recommended**:
- `BAGO-Installation-Manager-4.9.0-win-x64.exe` ← Main file (easiest for users)
- `BAGO-Installation-Manager-4.9.0-win-x64.exe.sha256` (for verification)
- `bago-v4.9.0.zip` (update package)
- `bago-v4.9.0.zip.sha256` (for verification)
- `latest.yml` (auto-update metadata)
- `INSTALL.md` (quick start)
- `README-INSTALLERS.md` (comprehensive guide)

### Enterprise/Corporate
**Recommended**:
- `install-v4.ps1` + `bago-v4.9.0.zip` (for SCCM, Intune, etc.)
- `Install-BAGO.ps1` (for source-based deployments)
- `install-bago-setup.cmd` (for batch scripts)
- `DELIVERY.md` (official documentation)

### Developer Release
**Include**:
- `Install-BAGO.ps1` (direct access)
- `install-v4.ps1` (package-driven)
- `install-bago-setup.cmd` (for CI/CD)
- All source documentation
- ZIP packages (for offline installation)

---

## Troubleshooting by Method

### EXE Won't Run
- ✓ Try: Run as Administrator (right-click → "Run as administrator")
- ✓ Try: Disable antivirus temporarily
- ✓ Try: Check Windows SmartScreen (click "Run anyway")
- ✓ Verify SHA256: `9AE9507F435DEBF978A3D268E5B59FC98BD37F45567E652DD976B4B85A012230`

### Package-Driven PowerShell Won't Execute
- ✓ Try: Open PowerShell as Administrator first
- ✓ Try: Run entire command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip`
- ✓ Check if `bago-v4.9.0.zip` is in the same directory or use full path

### Legacy PowerShell Script Won't Execute
- ✓ Try: Open PowerShell as Administrator first
- ✓ Try: Run entire command: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1`
- ✓ Try: Check if PowerShell Execution Policy is set: `Get-ExecutionPolicy`

### Batch File Won't Run
- ✓ Try: Open cmd.exe as Administrator first
- ✓ Try: Use full path: `C:\path\to\install-bago-setup.cmd`
- ✓ Try: Check %ERRORLEVEL% for specific error codes

### VBS Won't Run
- ✓ Try: Enable Windows Script Host (usually enabled by default)
- ✓ Try: Double-click and choose "Run"
- ✓ Try: Use PowerShell fallback if WSH is disabled

---

## Installation Verification

After any installation method, verify success:

```powershell
# Check if BAGO.exe exists
Test-Path "$env:LOCALAPPDATA\BAGO\BAGO.exe"
# Should return: True

# Check if shortcuts were created
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BAGO"
# Should return: True

# Launch BAGO
& "$env:LOCALAPPDATA\BAGO\BAGO.exe"
```

---

## Summary

| Goal | Method | File |
|------|--------|------|
| **Simplest** | Double-click | `BAGO-Installation-Manager-4.9.0-win-x64.exe` |
| **Fastest / CI/CD** | Package PowerShell | `install-v4.ps1 -PackageZip bago-v4.9.0.zip` |
| **Most Control** | Source PowerShell | `Install-BAGO.ps1` |
| **Batch/Legacy** | Batch Wrapper | `install-bago-setup.cmd` |
| **Alternative GUI** | VBS Launcher | `install-bago-setup.vbs` |

**Official and package-driven methods produce identical installations.** Choose based on your preference and use case.

---

For more details: See `INSTALL.md` or `README-INSTALLERS.md`
