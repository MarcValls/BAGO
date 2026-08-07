@echo off
REM BAGO 4.8.2 Installer Wrapper
REM This script invokes the PowerShell installer with proper permissions
REM
REM Usage: install-bago-setup.cmd [options]
REM        (or double-click to install with defaults)

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Remove trailing backslash if present
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

REM The PowerShell installer script to invoke
set "INSTALL_SCRIPT=!SCRIPT_DIR!\Install-BAGO.ps1"

REM Verify the installer exists
if not exist "!INSTALL_SCRIPT!" (
    echo.
    echo ERROR: Install-BAGO.ps1 not found at:
    echo   !INSTALL_SCRIPT!
    echo.
    echo Please ensure the installer file is in the same directory as this script.
    echo.
    pause
    exit /b 1
)

REM Invoke PowerShell with proper execution policy and no profile
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "!INSTALL_SCRIPT!" %*

REM Capture and exit with the same error level
exit /b %ERRORLEVEL%
