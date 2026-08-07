# BAGO 4.8.2 - Installation Methods Comparison

## Quick Decision Guide

| Need | Use | File |
|------|-----|------|
| **"Just let me install it"** | EXE Installer | `bago-4.8.2-setup.exe` |
| **"I need to automate this"** | PowerShell Script | `Install-BAGO.ps1` |
| **"I prefer command line"** | Batch Wrapper | `install-bago-setup.cmd` |
| **"I need documentation"** | Read First | `INSTALL.md` or `README-INSTALLERS.md` |

---

## Detailed Comparison

### 1. ⭐ EXE Installer (Easiest)

**File**: `bago-4.8.2-setup.exe` (36.8 KB)

**How to use**:
```
Just double-click the file and follow prompts
```

**Pros**:
- ✓ Single file, no setup needed
- ✓ Automatic admin elevation
- ✓ Full installation output shown
- ✓ No PowerShell configuration needed
- ✓ Standard Windows executable
- ✓ Works with Windows SmartScreen
- ✓ Easy for non-technical users

**Cons**:
- ✗ No scriptable parameters
- ✗ Can't run silently
- ✗ Slightly larger than PowerShell script

**Best for**: End users, GUI-preferred, first-time installers

**Installation time**: 10-15 minutes

---

### 2. 🔧 PowerShell Script (Best for Automation)

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
- ✓ Best for CI/CD pipelines
- ✓ Easy to debug
- ✓ Transparent—see all output
- ✓ Can be run silently with -ErrorAction SilentlyContinue
- ✓ Smallest file size (6.5 KB)

**Cons**:
- ✗ Requires PowerShell knowledge
- ✗ Need to run as Administrator manually
- ✗ Requires ExecutionPolicy adjustment

**Best for**: DevOps, CI/CD, automation, developers

**Installation time**: 10-15 minutes

**Example in CI/CD**:
```yaml
# GitHub Actions example
- name: Install BAGO
  run: |
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File Install-BAGO.ps1 `
      -InstallDir "D:\BAGO-CI" `
      -AppGitRef "main"
```

---

### 3. 📟 Batch Wrapper (Command Line)

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

### 4. 🪟 VBS Launcher (Alternative GUI)

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

| Feature | EXE | PowerShell | Batch | VBS |
|---------|-----|------------|-------|-----|
| **File Size** | 36.8 KB | 6.5 KB | 1.06 KB | 1.39 KB |
| **Double-click** | ✓ | ✗ | ✗ | ✓ |
| **Command-line** | ✓ | ✓ | ✓ | ✗ |
| **Scriptable** | ✗ | ✓ | ✗ | ✗ |
| **Custom Parameters** | ✗ | ✓ | Limited | ✗ |
| **Silent Execution** | ✗ | ✓ | ✓ | ✗ |
| **Admin Auto-Elevate** | ✓ | ✗ | ✗ | ✓ |
| **PowerShell Required** | ✗ | ✓ | ✓ | ✗ |
| **Transparent Output** | ✓ | ✓ | ✓ | ✗ |
| **CI/CD Friendly** | ✗ | ✓ | ✓ | ✗ |
| **Legacy Windows** | ✓ | ~ | ✓ | ✓ |

---

## Recommended Usage Scenarios

### Scenario 1: End User on Windows 11
```
→ Use: bago-4.8.2-setup.exe
✓ Single click, automatic admin elevation, easiest experience
```

### Scenario 2: Developer Running Locally
```
→ Use: Install-BAGO.ps1 with parameters
✓ Full control, scriptable, easy to debug custom installations
```

### Scenario 3: CI/CD Pipeline (GitHub Actions)
```
→ Use: Install-BAGO.ps1 in PowerShell step
✓ Fully automated, customizable, CI-friendly
```

### Scenario 4: Batch Deployment Script
```
→ Use: install-bago-setup.cmd in batch file
✓ Works in batch context, simple error handling
```

### Scenario 5: PowerShell Restricted Environment
```
→ Use: install-bago-setup.vbs or bago-4.8.2-setup.exe
✓ Bypasses PowerShell execution policy issues
```

### Scenario 6: Automation with Parameters
```
→ Use: Install-BAGO.ps1 with -InstallDir and -AppGitRef
✓ Only PowerShell script supports custom parameters
```

---

## Which File to Distribute?

### Public Release (GitHub, Web)
**Recommended**:
- `bago-4.8.2-setup.exe` ← Main file (easiest for users)
- `bago-4.8.2-setup.exe.sha256` (for verification)
- `INSTALL.md` (quick start)
- `README-INSTALLERS.md` (comprehensive guide)

### Enterprise/Corporate
**Recommended**:
- `Install-BAGO.ps1` (for SCCM, Intune, etc.)
- `install-bago-setup.cmd` (for batch scripts)
- `DELIVERY.md` (official documentation)

### Developer Release
**Include**:
- `Install-BAGO.ps1` (direct access)
- `install-bago-setup.cmd` (for CI/CD)
- All source documentation
- ZIP packages (for offline installation)

---

## Troubleshooting by Method

### EXE Won't Run
- ✓ Try: Run as Administrator (right-click → "Run as administrator")
- ✓ Try: Disable antivirus temporarily
- ✓ Try: Check Windows SmartScreen (click "Run anyway")

### PowerShell Script Won't Execute
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
Test-Path "$env:LOCALAPPDATA\BAGO\electron-viewer\dist\win-unpacked\BAGO.exe"
# Should return: True

# Check if shortcuts were created
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BAGO"
# Should return: True

# Launch BAGO
& "$env:LOCALAPPDATA\BAGO\electron-viewer\dist\win-unpacked\BAGO.exe"
```

---

## Summary

| Goal | Method | File |
|------|--------|------|
| **Simplest** | Double-click | `bago-4.8.2-setup.exe` |
| **Most Control** | PowerShell | `Install-BAGO.ps1` |
| **CI/CD** | PowerShell Script | `Install-BAGO.ps1` |
| **Batch/Legacy** | Batch Wrapper | `install-bago-setup.cmd` |
| **Alternative GUI** | VBS Launcher | `install-bago-setup.vbs` |

**All methods produce identical installations.** Choose based on your preference and use case.

---

For more details: See `INSTALL.md` or `README-INSTALLERS.md`
