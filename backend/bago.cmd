@echo off
rem BAGO global launcher: keep cmd and PowerShell behavior identical.
setlocal EnableExtensions
set "SCRIPT=%~dp0bago.ps1"
if not exist "%SCRIPT%" (
    echo bago: no se encontro %SCRIPT% 1>&2
    exit /b 1
)
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" set "POWERSHELL=powershell.exe"
"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
exit /b %ERRORLEVEL%
