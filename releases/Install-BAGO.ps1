#!/usr/bin/env powershell
<#
.SYNOPSIS
BAGO 4.8.2 Windows Installer
.DESCRIPTION
Instala BAGO y todas sus dependencias en C:\Users\{user}\AppData\Local\BAGO
#>

param(
    [switch]$Help,
    [string]$InstallDir = "$env:LOCALAPPDATA\BAGO",
    [string]$GitRef = "main",
    [string]$GitSha = "9e1c49bb3f5388b991ed21ad0287059f4d4d9875"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($Help) {
    Write-Host @"
BAGO 4.8.2 Installation Script

Usage:
  .\Install-BAGO.ps1 [options]

Options:
  -InstallDir <path>    Directory to install BAGO (default: $env:LOCALAPPDATA\BAGO)
  -GitRef <ref>         Git ref to install (default: main)
  -GitSha <sha>         Git commit SHA (default: 9e1c49bb3f5388b991ed21ad0287059f4d4d9875)
  -Help                 Show this help

Requirements:
  - Git
  - Node.js 20+
  - Python 3.11+

"@
    exit 0
}

Write-Host "BAGO 4.8.2 Installation" -ForegroundColor Cyan
Write-Host "Installation directory: $InstallDir" -ForegroundColor Gray
Write-Host ""

# Verify prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Cyan
@("git", "node", "python") | ForEach-Object {
    $cmd = $_
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: $cmd not found. Please install it first." -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ $cmd" -ForegroundColor Green
}

# Clean install directory
Write-Host ""
Write-Host "Preparing install directory..." -ForegroundColor Cyan
if (Test-Path $InstallDir) {
    Write-Host "  Removing existing installation..."
    Remove-Item $InstallDir -Recurse -Force
}
New-Item -ItemType Directory -Path $InstallDir | Out-Null
Write-Host "  ✓ Directory ready" -ForegroundColor Green

# Clone repository
Write-Host ""
Write-Host "Cloning repository..." -ForegroundColor Cyan
Push-Location $env:TEMP
try {
    git clone --depth 1 --branch $GitRef "https://github.com/MarcValls/BAGO.git" $InstallDir
    Push-Location $InstallDir
    if ($GitSha) {
        Write-Host "  Checking out commit..." -ForegroundColor Cyan
        git checkout --force $GitSha
    }
    Write-Host "  ✓ Repository cloned" -ForegroundColor Green
} finally {
    Pop-Location
}

# Install Node dependencies
Write-Host ""
Write-Host "Installing Node.js dependencies..." -ForegroundColor Cyan
Push-Location $InstallDir
try {
    npm install --quiet
    Write-Host "  ✓ Root dependencies installed" -ForegroundColor Green
    
    Push-Location electron-viewer
    npm install --quiet
    Write-Host "  ✓ Electron dependencies installed" -ForegroundColor Green
    Pop-Location
} finally {
    Pop-Location
}

# Install backend
Write-Host ""
Write-Host "Installing backend..." -ForegroundColor Cyan
Push-Location $InstallDir
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $InstallDir "backend\install-v4.ps1") -Mode Express -SkipTests -ErrorAction Stop | Select-Object -Last 5
    Write-Host "  ✓ Backend installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# Build frontend
Write-Host ""
Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location $InstallDir
try {
    npm run build --silent
    Write-Host "  ✓ Frontend built" -ForegroundColor Green
} finally {
    Pop-Location
}

# Package with electron-builder
Write-Host ""
Write-Host "Packaging application..." -ForegroundColor Cyan
Push-Location $InstallDir\electron-viewer
try {
    npx electron-builder --dir --config.directories.output="$InstallDir/electron-viewer/dist" 2>&1 | Where-Object { $_ -match "(packaging|successfully|ERROR)" }
    Write-Host "  ✓ Application packaged" -ForegroundColor Green
} finally {
    Pop-Location
}

# Verify installation
Write-Host ""
Write-Host "Verifying installation..." -ForegroundColor Cyan
$exePath = Join-Path $InstallDir "electron-viewer\dist\win-unpacked\BAGO.exe"
if (Test-Path $exePath) {
    Write-Host "  ✓ BAGO.exe found at $exePath" -ForegroundColor Green
} else {
    Write-Host "  ERROR: BAGO.exe not found" -ForegroundColor Red
    exit 1
}

# Create shortcuts
Write-Host ""
Write-Host "Creating shortcuts..." -ForegroundColor Cyan
$shortcutDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\BAGO"
New-Item -ItemType Directory -Path $shortcutDir -Force | Out-Null

$shell = New-Object -COM WScript.Shell
$shortcut = $shell.CreateShortcut("$shortcutDir\BAGO.lnk")
$shortcut.TargetPath = $exePath
$shortcut.IconLocation = "$InstallDir\electron-viewer\bago.ico"
$shortcut.Save()

$desktopShortcut = $shell.CreateShortcut("$env:USERPROFILE\Desktop\BAGO.lnk")
$desktopShortcut.TargetPath = $exePath
$desktopShortcut.IconLocation = "$InstallDir\electron-viewer\bago.ico"
$desktopShortcut.Save()

Write-Host "  ✓ Shortcuts created" -ForegroundColor Green

# Register in Windows
Write-Host ""
Write-Host "Registering application..." -ForegroundColor Cyan
$regPath = "HKCU:\Software\BAGO"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "InstallPath" -Value $InstallDir
Set-ItemProperty -Path $regPath -Name "Version" -Value "4.8.2"

$uninstallPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
New-Item -Path $uninstallPath -Force | Out-Null
Set-ItemProperty -Path $uninstallPath -Name "DisplayName" -Value "BAGO 4.8.2"
Set-ItemProperty -Path $uninstallPath -Name "Publisher" -Value "MarcValls"
Set-ItemProperty -Path $uninstallPath -Name "UninstallString" -Value "PowerShell -NoProfile -ExecutionPolicy Bypass -Command `"Remove-Item '$InstallDir' -Recurse -Force`""
Set-ItemProperty -Path $uninstallPath -Name "DisplayVersion" -Value "4.8.2"

Write-Host "  ✓ Application registered" -ForegroundColor Green

Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  BAGO 4.8.2 Installed Successfully!    ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Location: $InstallDir" -ForegroundColor Cyan
Write-Host "Shortcut: $env:USERPROFILE\Desktop\BAGO.lnk" -ForegroundColor Cyan
Write-Host ""
Write-Host "To uninstall, run:" -ForegroundColor Yellow
Write-Host "  Remove-Item '$InstallDir' -Recurse -Force" -ForegroundColor Gray
