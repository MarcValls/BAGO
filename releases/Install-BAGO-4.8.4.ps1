# BAGO 4.8.4 PowerShell Installer
# Usage: powershell -ExecutionPolicy Bypass -File Install-BAGO-4.8.4.ps1

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\BAGO",
    [string]$SourceZip = $null
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "BAGO 4.8.4 Installation" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Find or download source ZIP
if (-not $SourceZip) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $localZip = Join-Path $scriptDir "bago-4.8.4-distribution.zip"
    
    if (Test-Path $localZip) {
        $SourceZip = $localZip
        Write-Host "✓ Found local package" -ForegroundColor Green
    } else {
        Write-Host "ERROR: bago-4.8.4-distribution.zip not found" -ForegroundColor Red
        Write-Host ""
        Write-Host "Place bago-4.8.4-distribution.zip in the same directory as this script"
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
Write-Host "Extracting..." -ForegroundColor Yellow

# Create installation directory
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

# Extract ZIP
try {
    Expand-Archive -Path $SourceZip -DestinationPath $InstallDir -Force
    Write-Host "✓ Package extracted" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Failed to extract package" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

# Restructure: move contents from compiled/ folder up one level
$compiledDir = Join-Path $InstallDir "compiled"
if (Test-Path $compiledDir) {
    Write-Host "✓ Restructuring installation..." -ForegroundColor Yellow
    Get-ChildItem -Path $compiledDir | Move-Item -Destination $InstallDir -Force
    Remove-Item $compiledDir -Force -ErrorAction SilentlyContinue
}

# Verify BAGO.exe exists
$bagoExe = Join-Path $InstallDir "BAGO.exe"
if (-not (Test-Path $bagoExe)) {
    Write-Host "ERROR: BAGO.exe not found in package" -ForegroundColor Red
    exit 1
}
Write-Host "✓ BAGO.exe verified" -ForegroundColor Green

# Create Start Menu folder
$startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\BAGO"
New-Item -ItemType Directory -Path $startMenuPath -Force | Out-Null

# Create shortcuts
Write-Host "✓ Creating shortcuts..." -ForegroundColor Yellow
$WshShell = New-Object -ComObject WScript.Shell

# Desktop shortcut
$desktopPath = [Environment]::GetFolderPath("Desktop")
$desktopShortcut = Join-Path $desktopPath "BAGO.lnk"
$shortcut = $WshShell.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $bagoExe
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = $bagoExe + ", 0"
$shortcut.Save()

# Start Menu shortcut
$startMenuShortcut = Join-Path $startMenuPath "BAGO.lnk"
$shortcut = $WshShell.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $bagoExe
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = $bagoExe + ", 0"
$shortcut.Save()

Write-Host "  Desktop: $desktopShortcut" -ForegroundColor Gray
Write-Host "  Start Menu: $startMenuShortcut" -ForegroundColor Gray

# Register in Windows Add/Remove Programs
Write-Host "✓ Registering application..." -ForegroundColor Yellow
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
Set-ItemProperty -Path $regPath -Name "DisplayName" -Value "BAGO 4.8.4"
Set-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "4.8.4"
Set-ItemProperty -Path $regPath -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $regPath -Name "UninstallString" -Value "powershell -ExecutionPolicy Bypass -Command `"Remove-Item '$InstallDir' -Recurse -Force; Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\BAGO' -Force`""
Set-ItemProperty -Path $regPath -Name "Publisher" -Value "MarcValls"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "✓ BAGO 4.8.4 installed successfully!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now launch BAGO from:"
Write-Host "  • Desktop shortcut"
Write-Host "  • Start Menu → BAGO"
Write-Host "  • Or run: $bagoExe" -ForegroundColor Green
Write-Host ""
Write-Host "Installation Directory: $InstallDir" -ForegroundColor Gray
Write-Host ""

$response = Read-Host "Launch BAGO now? (y/n)"
if ($response -eq "y" -or $response -eq "Y") {
    & $bagoExe
}
