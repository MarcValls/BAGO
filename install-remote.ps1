#Requires -Version 5.1
<#
.SYNOPSIS
  Bootstrap estable del instalador remoto de BAGO.

.DESCRIPTION
  Mantiene una URL pública estable aunque el instalador completo viva en
  backend/install-remote.ps1 dentro del monorepo.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [ValidateSet("Express", "Advanced")]
    [string]$Mode = "Express",
    [string]$Tag = "",
    [switch]$SkipTests,
    [switch]$NoPathUpdate,
    [switch]$NoShellIntegration,
    [switch]$RequireSignature
)

$ErrorActionPreference = "Stop"
$installerUrl = "https://raw.githubusercontent.com/MarcValls/BAGO/main/backend/install-remote.ps1"
$tempInstaller = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-install-remote-" + [Guid]::NewGuid().ToString("N") + ".ps1")

try {
    Invoke-WebRequest -Uri $installerUrl -OutFile $tempInstaller -UseBasicParsing
    $installerArgs = @("-Mode", $Mode)
    if ($InstallDir) { $installerArgs += @("-InstallDir", $InstallDir) }
    if ($Tag) { $installerArgs += @("-Tag", $Tag) }
    if ($SkipTests) { $installerArgs += "-SkipTests" }
    if ($NoPathUpdate) { $installerArgs += "-NoPathUpdate" }
    if ($NoShellIntegration) { $installerArgs += "-NoShellIntegration" }
    if ($RequireSignature) { $installerArgs += "-RequireSignature" }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $tempInstaller @installerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "El instalador remoto de BAGO falló con código $LASTEXITCODE."
    }
} finally {
    Remove-Item -LiteralPath $tempInstaller -Force -ErrorAction SilentlyContinue
}
