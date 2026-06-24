@echo off
rem Wrapper: relanza promote_and_update.ps1 en una ventana PowerShell elevada.
rem Se auto-eleva via UAC. Si ya estamos elevados, sigue sin prompt.

setlocal
set "SCRIPT=%~dp0promote_and_update.ps1"
if not exist "%SCRIPT%" (
    echo [ERROR] No se encuentra "%SCRIPT%" 1>&2
    exit /b 1
)

net session >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo [OK] Ya estamos en una consola elevada. Ejecutando...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
    exit /b %ERRORLEVEL%
)

echo [INFO] Solicitando elevacion UAC...
powershell -NoProfile -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c cd /d \"%~dp0\" && powershell -NoProfile -ExecutionPolicy Bypass -File \"%SCRIPT%\"' -Verb RunAs -Wait"
exit /b %ERRORLEVEL%