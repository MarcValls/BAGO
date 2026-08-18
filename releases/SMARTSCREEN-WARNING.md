# BAGO 4.9.0 - Windows Defender / SmartScreen Alert Solution

## Problem

When downloading `BAGO-Installation-Manager-4.9.0-win-x64.exe` (or the legacy `bago-4.9.0-setup.exe`), Windows Defender or SmartScreen may show:

> "No se pudo completar la operación porque el archivo contiene un virus o software potencialmente no deseado"
> 
> "The operation could not be completed because the file contains a virus or software potentially unwanted"

## Cause

This is a **false positive** caused by:
- The EXE file is not digitally signed with a certificate
- Newly compiled executables without certificates trigger SmartScreen
- The installer contains bundled binaries and PowerShell code
- Windows doesn't recognize the publisher

**This is completely safe** - it's a protection mechanism that flags unsigned executables.

## Solution 1: Use Package-Driven PowerShell Installer (Recommended)

Instead of the EXE, use the package-driven installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File install-v4.ps1 -PackageZip bago-v4.9.0.zip
```

**Advantages:**
- No antivirus warnings
- Full transparency (see the code)
- Identical installation result
- Works with stricter security policies
- Smaller payload

## Solution 2: Override SmartScreen Warning

If you want to use the EXE:

1. **Download the file** (it will show a warning)
2. **Right-click** the EXE file
3. **Select "Properties"**
4. **At the bottom, check** "Unblock" checkbox
5. **Click "Apply"** → **"OK"**
6. **Double-click** to run

### Visual Steps:
```
Right-click BAGO-Installation-Manager-4.9.0-win-x64.exe
    ↓
Properties
    ↓
General tab
    ↓
[✓] Unblock (at bottom)
    ↓
Apply → OK
    ↓
Double-click to run
```

## Solution 3: Use VBS or Batch Wrapper

Instead of the official EXE, use alternative launchers:

```cmd
install-bago-setup.cmd
```

Or:

```
install-bago-setup.vbs (double-click)
```

These bypass some SmartScreen checks.

## Verify File Integrity

You can verify the downloaded file hasn't been tampered with:

```powershell
$hash = (Get-FileHash BAGO-Installation-Manager-4.9.0-win-x64.exe -Algorithm SHA256).Hash
$expected = "9AE9507F435DEBF978A3D268E5B59FC98BD37F45567E652DD976B4B85A012230"
$hash -eq $expected  # Should show: True
```

## Why It's Safe

- ✓ Open source code (available on GitHub)
- ✓ Official installer built with electron-builder NSIS
- ✓ Legacy installer is a wrapper around `Install-BAGO.ps1`
- ✓ All hashes are published for verification

## Digital Signing (Future)

To remove this warning permanently, the EXE would need to be code-signed with a certificate. This requires:
- Enterprise code-signing certificate (~$300-500/year)
- Or purchasing reputation with Microsoft SmartScreen
- Or waiting for Microsoft to whitelist the file after distribution

These aren't feasible for open-source projects, so the workaround is recommended.

## Antivirus Compatibility

The warning may appear in different ways depending on your security software:

| Software | Warning | Solution |
|----------|---------|----------|
| Windows Defender | SmartScreen alert | Unblock properties or use PS1 |
| Avast | Potentially unwanted | Add to whitelist |
| Kaspersky | Suspicious file | Allow execution |
| McAfee | Generic alert | Exclude from scanning |

## Recommended Installation Method

Given the SmartScreen issue, we recommend:

**For End Users:**
- Use the package-driven installer: `install-v4.ps1 -PackageZip bago-v4.9.0.zip`
- Or batch wrapper: `install-bago-setup.cmd`

**For CI/CD:**
- Use the package-driven installer
- No antivirus issues in automated environments

**If You Prefer EXE:**
- Unblock in Properties (see Solution 2)
- Or download directly from GitHub Releases
- Or build it yourself from source

## Still Having Issues?

1. **Check SHA256 hash** - verify file integrity
2. **Use package-driven PowerShell installer instead** - no warnings
3. **Check your antivirus settings** - may need to whitelist
4. **Disable antivirus temporarily** - during installation only
5. **Report to antivirus vendor** - they can whitelist

## Need Help?

- **GitHub Issues**: https://github.com/MarcValls/BAGO/issues
- **GitHub Discussions**: https://github.com/MarcValls/BAGO/discussions

---

**Important**: This alert is a Windows security feature, not an indication that BAGO is unsafe. The same warning appears with many legitimate, unsigned applications.
