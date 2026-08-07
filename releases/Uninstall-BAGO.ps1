#!/usr/bin/env powershell
<#
.SYNOPSIS
BAGO 4.8.2 Uninstaller
.DESCRIPTION
Removes BAGO and all its files
#>

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\BAGO"
)

$ErrorActionPreference = "Stop"

Write-Host "BAGO 4.8.2 Uninstaller" -ForegroundColor Cyan
Write-Host ""

# Kill any running BAGO processes
Write-Host "Stopping BAGO processes..." -ForegroundColor Cyan
Get-Process | Where-Object { $_.Name -match "BAGO|bago|python" } | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  Stopped: $($_.Name)" -ForegroundColor Gray
    } catch { }
}
Start-Sleep -Seconds 2

# Remove installation
Write-Host ""
Write-Host "Removing installation directory..." -ForegroundColor Cyan
if (Test-Path $InstallDir) {
    try {
        Remove-Item $InstallDir -Recurse -Force
        Write-Host "  ✓ Installation removed" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Could not remove installation" -ForegroundColor Red
        Write-Host "  Message: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Installation directory not found" -ForegroundColor Yellow
}

# Remove shortcuts
Write-Host ""
Write-Host "Removing shortcuts..." -ForegroundColor Cyan
@(
    "$env:USERPROFILE\Desktop\BAGO.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BAGO"
) | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item $_ -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  ✓ Removed: $_" -ForegroundColor Green
    }
}

# Remove registry
Write-Host ""
Write-Host "Removing registry entries..." -ForegroundColor Cyan
@(
    "HKCU:\Software\BAGO",
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
) | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item $_ -Force -ErrorAction SilentlyContinue
        Write-Host "  ✓ Removed: $_" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  BAGO 4.8.2 Uninstalled Successfully   ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Green
