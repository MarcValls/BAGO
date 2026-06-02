#Requires -Version 5.1
<#
.SYNOPSIS
  Instalador remoto de BAGO - siempre usa la ultima release de GitHub.

.DESCRIPTION
  Descarga el release oficial de GitHub, lo extrae y ejecuta install-v4.ps1.
  Uso desde terminal (sin descargar nada manualmente):

      iwr -useb https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1 | iex

  O con PowerShell 5:

      (New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1') | Invoke-Expression

.PARAMETER InstallDir
  Directorio de instalacion. Default: C:\Program Files\BAGO

.PARAMETER Mode
  Modo del asistente local: Express o Advanced.

.PARAMETER SkipTests
  Omite tests post-instalacion.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\Program Files\BAGO",
    [ValidateSet("Express", "Advanced")]
    [string]$Mode = "Express",
    [switch]$SkipTests,
    [switch]$NoPathUpdate
)

$ErrorActionPreference = "Stop"
$apiUrl = "https://api.github.com/repos/MarcValls/BAGO/releases?per_page=20"
$releases = Invoke-RestMethod -Uri $apiUrl -Headers @{ Accept = "application/vnd.github+json" } -UseBasicParsing
$release = @($releases) |
    Where-Object { -not $_.draft } |
    Sort-Object { [datetime]$_.published_at } -Descending |
    Select-Object -First 1
if (-not $release) {
    throw "No se encontro ninguna release publicada de BAGO."
}
$version = [string]$release.tag_name
$assetInfo = @($release.assets) | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
if (-not $assetInfo) {
    throw "La ultima release de BAGO no contiene un asset .zip instalable."
}
$asset = [string]$assetInfo.name
$releaseUrl = [string]$assetInfo.browser_download_url
$tempZip = Join-Path $env:TEMP $asset
$safeVersion = $version -replace '[^A-Za-z0-9._-]', '_'
$tempExtract = Join-Path $env:TEMP "bago-$safeVersion-extract"

Write-Host "[install-remote] Descargando BAGO $version ($asset) ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $releaseUrl -OutFile $tempZip -UseBasicParsing

Write-Host "[install-remote] Extrayendo ..." -ForegroundColor Cyan
if (Test-Path $tempExtract) { Remove-Item -Recurse -Force $tempExtract }
Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

$sourceRoot = $tempExtract
$installScript = Join-Path $sourceRoot "install-v4.ps1"
if (-not (Test-Path $installScript)) {
    $package = Get-ChildItem $tempExtract -Directory | Select-Object -First 1
    if ($package) {
        $sourceRoot = $package.FullName
        $installScript = Join-Path $sourceRoot "install-v4.ps1"
    }
}
if (-not (Test-Path $installScript)) {
    throw "No se encontro install-v4.ps1 dentro del paquete descargado."
}

Write-Host "[install-remote] Ejecutando instalador local ..." -ForegroundColor Cyan
$argsList = @("-SourceRoot", $sourceRoot, "-InstallDir", $InstallDir, "-Mode", $Mode)
if ($SkipTests) { $argsList += "-SkipTests" }
if ($NoPathUpdate) { $argsList += "-NoPathUpdate" }
& powershell.exe -ExecutionPolicy Bypass -File $installScript @argsList

Write-Host "[install-remote] Limpieza temporal ..." -ForegroundColor Cyan
Remove-Item -Force $tempZip -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue

Write-Host "[install-remote] BAGO $version instalado en $InstallDir" -ForegroundColor Green
