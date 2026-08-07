#Requires -Version 5.1
<#
.SYNOPSIS
  Instalador autónomo de BAGO 4.8.2 para Windows.

.DESCRIPTION
  Descarga el paquete de backend de la release v4.8.2, lo descomprime en una
  carpeta temporal y ejecuta backend/install-v4.ps1 desde ese paquete.

.USAGE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\bago-4.8.2-installer.ps1
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [ValidateSet("Express", "Advanced")]
    [string]$Mode = "Express",
    [string]$Profile = "",
    [string]$BackupRoot = "",
    [string]$UserStateDir = "",
    [switch]$SkipTests,
    [switch]$RepairOnly,
    [switch]$NoPathUpdate,
    [switch]$NoShellIntegration,
    [switch]$ExplorerContextMenu
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repo = "MarcValls/BAGO"
$tag = "v4.8.2"
$backendZipUrl = "https://github.com/$repo/releases/download/$tag/bago-4.8.2-backend.zip"
$backendZipShaUrl = "$backendZipUrl.sha256"

$tempZip = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-4.8.2-backend-" + [Guid]::NewGuid().ToString("N") + ".zip")
$tempSha = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-4.8.2-backend-" + [Guid]::NewGuid().ToString("N") + ".sha256")
$tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-4.8.2-install-" + [Guid]::NewGuid().ToString("N"))

function Invoke-BagoInstaller {
    param([Parameter(Mandatory = $true)][string]$InstallerPath)

    $args = @("-SourceRoot", (Join-Path $tempExtract "backend"), "-Mode", $Mode)
    if ($InstallDir) { $args += @("-InstallDir", $InstallDir) }
    if ($Profile) { $args += @("-Profile", $Profile) }
    if ($BackupRoot) { $args += @("-BackupRoot", $BackupRoot) }
    if ($UserStateDir) { $args += @("-UserStateDir", $UserStateDir) }
    if ($SkipTests) { $args += "-SkipTests" }
    if ($RepairOnly) { $args += "-RepairOnly" }
    if ($NoPathUpdate) { $args += "-NoPathUpdate" }
    if ($NoShellIntegration) { $args += "-NoShellIntegration" }
    if ($ExplorerContextMenu) { $args += "-ExplorerContextMenu" }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $InstallerPath @args
    if ($LASTEXITCODE -ne 0) {
        throw "El instalador de BAGO falló con código $LASTEXITCODE."
    }
}

try {
    Invoke-WebRequest -Uri $backendZipUrl -OutFile $tempZip -UseBasicParsing
    Invoke-WebRequest -Uri $backendZipShaUrl -OutFile $tempSha -UseBasicParsing

    $declaredSha = ((Get-Content -LiteralPath $tempSha -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
    if (-not $declaredSha -or $declaredSha.Length -ne 64) {
        throw "No se pudo leer un SHA-256 válido desde $backendZipShaUrl."
    }

    $actualSha = (Get-FileHash -LiteralPath $tempZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha -ne $declaredSha) {
        throw "Checksum inválido para bago-4.8.2-backend.zip. Esperado: $declaredSha. Actual: $actualSha."
    }

    Expand-Archive -LiteralPath $tempZip -DestinationPath $tempExtract -Force

    $installerPath = Join-Path $tempExtract "backend\install-v4.ps1"
    if (-not (Test-Path -LiteralPath $installerPath)) {
        throw "No se encontró backend/install-v4.ps1 dentro del paquete descargado."
    }

    Invoke-BagoInstaller -InstallerPath $installerPath
}
finally {
    Remove-Item -LiteralPath $tempZip -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempSha -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}
