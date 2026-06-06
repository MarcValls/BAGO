@echo off
rem BAGO global launcher: keep cmd and PowerShell behavior identical.
setlocal EnableExtensions
set "SCRIPT=%~dp0bago.ps1"
if not exist "%SCRIPT%" (
    echo bago: no se encontro %SCRIPT% 1>&2
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
exit /b %ERRORLEVEL%
