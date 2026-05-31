#Requires -Version 5.1
<#
.SYNOPSIS
  Instalador remoto de BAGO v4.1.4 - sin descarga manual.

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
$version = "v4.1.4"
$asset = "bago-v4.1.4.zip"
$releaseUrl = "https://github.com/MarcValls/BAGO/releases/download/$version/$asset"
$tempZip = Join-Path $env:TEMP $asset
$tempExtract = Join-Path $env:TEMP "bago-$version-extract"

Write-Host "[install-remote] Descargando BAGO $version ..." -ForegroundColor Cyan
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
