#!/usr/bin/env powershell
# BAGO 4.8.2 Installation Script
# Ejecuta el workflow completo de instalación

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\BAGO",
    [string]$AppGitRef = "main",
    [string]$AppGitSha = "",
    [string]$AppRepo = "https://github.com/MarcValls/BAGO.git"
)

$ErrorActionPreference = "Stop"
$LogFile = "$env:TEMP\BAGO-Install-Log.txt"

function Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logLine = "[$timestamp] $Message"
    Write-Host $logLine
    Add-Content $LogFile $logLine -ErrorAction SilentlyContinue
}

try {
    Log "=== BAGO 4.8.2 Installation Started ==="
    Log "Install Directory: $InstallDir"
    Log "Git Ref: $AppGitRef"
    Log "Git SHA: $AppGitSha"
    
    # Limpiar (o crear) el directorio de instalación
    Log "Preparando directorio de instalación..."
    if (Test-Path $InstallDir) {
        Remove-Item $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
    
    # Clone
    $stagingDir = Join-Path $env:TEMP "BAGO-stage"
    if (Test-Path $stagingDir) {
        Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Path $stagingDir | Out-Null

    Log "Clonando repositorio..."
    git clone --depth 1 --branch $AppGitRef $AppRepo $stagingDir 2>&1 | Tee-Object -FilePath $LogFile -Append
    $LASTEXITCODE -eq 0 -or $(throw "Git clone failed with exit code $LASTEXITCODE")
    
    if ($AppGitSha) {
        Log "Fijando SHA: $AppGitSha..."
        Push-Location $stagingDir
        git checkout --force $AppGitSha 2>&1 | Tee-Object -FilePath $LogFile -Append
        $LASTEXITCODE -eq 0 -or $(throw "Git checkout failed with exit code $LASTEXITCODE")
        Pop-Location
    }
    
    # npm install root
    Log "npm install (root)..."
    Push-Location $stagingDir
    npm install 2>&1 | Tee-Object -FilePath $LogFile -Append
    $LASTEXITCODE -eq 0 -or $(throw "npm install (root) failed with exit code $LASTEXITCODE")
    
    # npm install electron-viewer
    Log "npm install (electron-viewer)..."
    Push-Location electron-viewer
    npm install 2>&1 | Tee-Object -FilePath $LogFile -Append
    $LASTEXITCODE -eq 0 -or $(throw "npm install (electron-viewer) failed with exit code $LASTEXITCODE")
    Pop-Location
    
    # Backend install
    Log "Backend install..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File backend\install-v4.ps1 -Mode Express -SkipTests 2>&1 | Tee-Object -FilePath $LogFile -Append
    $LASTEXITCODE -eq 0 -or $(throw "Backend install failed with exit code $LASTEXITCODE")
    
    # Build frontend
    Log "npm run build..."
    npm run build 2>&1 | Tee-Object -FilePath $LogFile -Append
    $LASTEXITCODE -eq 0 -or $(throw "npm run build failed with exit code $LASTEXITCODE")
    
    # Electron builder
    Log "electron-builder --dir..."
    Push-Location electron-viewer
    npx electron-builder --dir 2>&1 | Tee-Object -FilePath $LogFile -Append
    $LASTEXITCODE -eq 0 -or $(throw "electron-builder failed with exit code $LASTEXITCODE")
    Pop-Location
    Copy-Item -Path $stagingDir\* -Destination $InstallDir -Recurse -Force
    Pop-Location
    
    # Verify BAGO.exe exists
    $exePath = Join-Path $InstallDir "electron-viewer\dist\win-unpacked\BAGO.exe"
    if (!(Test-Path $exePath)) {
        throw "BAGO.exe not found at $exePath"
    }
    
    Log "BAGO.exe successfully generated at $exePath"
    Log "=== Installation Completed Successfully ==="
    exit 0
}
catch {
    Log "ERROR: $_"
    Log "Stack trace: $($_.ScriptStackTrace)"
    exit 1
}
