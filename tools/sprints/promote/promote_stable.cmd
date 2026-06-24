@echo off
setlocal
set "ZIP=%TEMP%\bago-v4.7-qwen.zip"
if not exist "%ZIP%" (
    echo [INFO] Building source zip...
    pushd "C:\Program Files\BAGO"
    python make_source_zip.py
    popd
)
echo [INFO] Promoting to stable profile (Program Files)...
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Program Files\BAGO\install-v4.ps1" -PackageZip "%ZIP%" -Profile stable -Mode Express -NoPathUpdate
exit /b %ERRORLEVEL%