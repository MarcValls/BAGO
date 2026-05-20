from pathlib import Path

# Fix install-bago.cmd
cmd = Path("install-bago.cmd").read_text(encoding="utf-8")

# Update all hardcoded version references
old = '''set "ZIP_URL=https://github.com/MarcValls/BAGO/releases/download/v3.4.4/BAGO-3.4.1.zip"
set "INSTALL_DIR=%USERPROFILE%\\BAGO"
set "ZIP_FILE=%TEMP%\\BAGO-3.4.1.zip"'''
new = '''set "ZIP_URL=https://github.com/MarcValls/BAGO/releases/download/v3.4.5/BAGO-3.4.5-new.zip"
set "INSTALL_DIR=%USERPROFILE%\\BAGO"
set "ZIP_FILE=%TEMP%\\BAGO-3.4.5-new.zip"'''
cmd = cmd.replace(old, new)

# Fix the extraction check — use dynamic detection instead of hardcoded folder
old2 = '''set "BAGO_ROOT=%INSTALL_DIR%\\BAGO-3.4.1"
if not exist "%BAGO_ROOT%\\bago" (
    echo  [XX] Extraccion fallida. Estructura inesperada.
    pause
    exit /b 1
)'''
new2 = ''':: Detect extracted folder dynamically (ZIP may have root folder or not)
for /d %%D in ("%INSTALL_DIR%\\*") do (
    if exist "%%D\\bago" (
        set "BAGO_ROOT=%%D"
        goto :found_root
    )
)
if exist "%INSTALL_DIR%\\bago" (
    set "BAGO_ROOT=%INSTALL_DIR%"
    goto :found_root
)
echo  [XX] Extraccion fallida. Estructura inesperada.
pause
exit /b 1
:found_root'''
cmd = cmd.replace(old2, new2)

# Also update title
cmd = cmd.replace("BAGO Framework v3.4.4 ?", "BAGO Framework v3.4.5")

Path("install-bago.cmd").write_text(cmd, encoding="utf-8")
print("FIXED install-bago.cmd")

# Fix install-bago.sh
sh = Path("install-bago.sh").read_text(encoding="utf-8")
# Update version references
sh = sh.replace("v3.4.4", "v3.4.5")
sh = sh.replace("BAGO-3.4.1", "BAGO-3.4.5-new")
sh = sh.replace("BAGO_3.4.1", "BAGO_3.4.5")
Path("install-bago.sh").write_text(sh, encoding="utf-8")
print("FIXED install-bago.sh")

# Fix install.ps1
ps = Path("install.ps1").read_text(encoding="utf-8")
ps = ps.replace("v3.4.4", "v3.4.5")
Path("install.ps1").write_text(ps, encoding="utf-8")
print("FIXED install.ps1")
