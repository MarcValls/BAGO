#!/usr/bin/env powershell
<#
.SYNOPSIS
    BAGO 4.9.0 Installer Launcher
    
.DESCRIPTION
    This script launches the main BAGO installer (Install-BAGO.ps1)
    with proper error handling and user feedback.
    
.NOTES
    This script must be placed in the same directory as Install-BAGO.ps1
#>

# Get the directory where this script is located
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$installerScript = Join-Path $scriptDir "Install-BAGO.ps1"

# Verify the main installer exists
if (-not (Test-Path $installerScript)) {
    Write-Host ""
    Write-Host "ERROR: Install-BAGO.ps1 not found!" -ForegroundColor Red
    Write-Host "Expected location: $installerScript" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure the installer file is in the same directory as this script." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Display welcome message
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BAGO 4.9.0 Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting installation..." -ForegroundColor Green
Write-Host ""

# Execute the main installer with any passed arguments
try {
    & $installerScript @args
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host ""
    Write-Host "ERROR: Installation failed!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Exit with the same code as the installer
exit $exitCode
