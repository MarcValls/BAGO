# BAGO 4.8.2 PowerShell Installer
# Usage: powershell -ExecutionPolicy Bypass -File Install-BAGO-4.8.2.ps1

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\BAGO",
    [string]$SourceZip = $null
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "BAGO 4.8.2 Installation" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Find or download source ZIP
if (-not $SourceZip) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $localZip = Join-Path $scriptDir "bago-4.8.2-distribution.zip"
    
    if (Test-Path $localZip) {
        $SourceZip = $localZip
        Write-Host "✓ Found local package" -ForegroundColor Green
    } else {
        Write-Host "ERROR: bago-4.8.2-distribution.zip not found" -ForegroundColor Red
        Write-Host ""
        Write-Host "Place bago-4.8.2-distribution.zip in the same directory as this script"
        Write-Host "Or download from: https://github.com/MarcValls/BAGO/releases"
        exit 1
    }
}

if (-not (Test-Path $SourceZip)) {
    Write-Host "ERROR: ZIP file not found: $SourceZip" -ForegroundColor Red
    exit 1
}

$zipName = Split-Path -Leaf $SourceZip
Write-Host "✓ Package: $zipName" -ForegroundColor Green
Write-Host ""

# Prepare installation
Write-Host "Installation Directory: $InstallDir" -ForegroundColor Gray
if (Test-Path $InstallDir) {
    Write-Host "  (Existing installation will be replaced)"
    Remove-Item $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "✓ Extracting..."
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Expand-Archive -Path $SourceZip -DestinationPath $InstallDir -Force -ErrorAction Stop

Write-Host "✓ Verifying..."
$bago = "$InstallDir\compiled\electron-viewer\BAGO.exe"
if (-not (Test-Path $bago)) {
    Write-Host "ERROR: BAGO.exe not found" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Restructuring..."
Copy-Item "$InstallDir\compiled\*" -Destination $InstallDir -Recurse -Force
Remove-Item "$InstallDir\compiled" -Recurse -Force

Write-Host ""
Write-Host "✓ Creating shortcuts..."

$desktopDir = [Environment]::GetFolderPath("Desktop")
$startMenuDir = [Environment]::GetFolderPath("StartMenu")

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut("$desktopDir\BAGO.lnk")
$shortcut.TargetPath = "$InstallDir\electron-viewer\BAGO.exe"
$shortcut.IconLocation = "$InstallDir\electron-viewer\bago.ico"
$shortcut.Description = "BAGO 4.8.2"
$shortcut.Save()

$startMenuBago = "$startMenuDir\BAGO"
New-Item -ItemType Directory -Path $startMenuBago -Force | Out-Null

$shortcut2 = $wshShell.CreateShortcut("$startMenuBago\BAGO.lnk")
$shortcut2.TargetPath = "$InstallDir\electron-viewer\BAGO.exe"
$shortcut2.IconLocation = "$InstallDir\electron-viewer\bago.ico"
$shortcut2.Description = "BAGO 4.8.2"
$shortcut2.Save()

Write-Host "✓ Registering in Windows..."
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "DisplayName" -Value "BAGO 4.8.2"
Set-ItemProperty -Path $regPath -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "4.8.2"
Set-ItemProperty -Path $regPath -Name "Publisher" -Value "MarcValls"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "✓ Installation Complete!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "BAGO is ready! Launch from:"
Write-Host "  • Desktop: Double-click BAGO shortcut"
Write-Host "  • Start Menu: BAGO > BAGO"
Write-Host "  • Command: & '$InstallDir\electron-viewer\BAGO.exe'"
Write-Host ""
