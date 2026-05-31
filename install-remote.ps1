#Requires -Version 5.1
<#
.SYNOPSIS
  Instalador remoto de BAGO v4.1.0 — sin descarga manual.

.DESCRIPTION
  Descarga el release oficial de GitHub, lo extrae y ejecuta install-v4.ps1.
  Uso desde terminal (sin descargar nada manualmente):

      iwr -useb https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1 | iex

  O con PowerShell 5:

      (New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1') | Invoke-Expression

.PARAMETER InstallDir
  Directorio de instalación. Default: C:\BAGO

.PARAMETER SkipTests
  Omite tests post-instalación.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\BAGO",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$releaseUrl = "https://github.com/MarcValls/BAGO/releases/download/v4.1.0/bago-v4.1.0.zip"
$tempZip = Join-Path $env:TEMP "bago-v4.1.0.zip"
$tempExtract = Join-Path $env:TEMP "bago-v4.1.0-extract"

Write-Host "[install-remote] Descargando BAGO v4.1.0 ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $releaseUrl -OutFile $tempZip -UseBasicParsing

Write-Host "[install-remote] Extrayendo ..." -ForegroundColor Cyan
if (Test-Path $tempExtract) { Remove-Item -Recurse -Force $tempExtract }
Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

$package = Get-ChildItem $tempExtract | Select-Object -First 1
$installScript = Join-Path $package.FullName "install-v4.ps1"
if (-not (Test-Path $installScript)) {
    throw "No se encontró install-v4.ps1 dentro del paquete descargado."
}

Write-Host "[install-remote] Ejecutando instalador local ..." -ForegroundColor Cyan
$argsList = @("-InstallDir", $InstallDir)
if ($SkipTests) { $argsList += "-SkipTests" }
& powershell.exe -ExecutionPolicy Bypass -File $installScript @argsList

Write-Host "[install-remote] Limpieza temporal ..." -ForegroundColor Cyan
Remove-Item -Force $tempZip -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $tempExtract -ErrorAction SilentlyContinue

Write-Host "[install-remote] BAGO v4.1.0 instalado en $InstallDir" -ForegroundColor Green
