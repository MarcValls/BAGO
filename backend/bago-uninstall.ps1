[CmdletBinding()]
param(
    [Alias("install-dir")]
    [string]$InstallDir = "",
    [Alias("backup-root")]
    [string]$BackupRoot = "",
    [Alias("user-state-dir")]
    [string]$UserStateDir = "",
    [Alias("purge-state")]
    [switch]$PurgeState,
    [Alias("dry-run")]
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DefaultInstallDir {
    [string]$override = [System.Environment]::GetEnvironmentVariable("BAGO_INSTALL_DIR")
    if (-not [string]::IsNullOrWhiteSpace($override)) { return [System.IO.Path]::GetFullPath($override) }
    [string]$programFilesRoot = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::ProgramFiles)
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = [System.Environment]::GetEnvironmentVariable("ProgramFiles") }
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = [System.IO.Path]::GetTempPath() }
    return (Join-Path $programFilesRoot "BAGO")
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Get-DefaultInstallDir
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root "bago_core\cli.py"
if (-not (Test-Path -LiteralPath $script)) {
    throw "No se encontro bago_core\cli.py junto a bago-uninstall.ps1: $script"
}

$installFull = Get-FullPath $InstallDir
$argsList = @($script, "uninstall", "--install-dir", $installFull)
if ($BackupRoot) {
    $argsList += @("--backup-root", (Get-FullPath $BackupRoot))
}
if ($UserStateDir) {
    $argsList += @("--user-state-dir", (Get-FullPath $UserStateDir))
}
if ($PurgeState) {
    $argsList += "--purge-state"
}
if ($DryRun) {
    $argsList += "--dry-run"
}

Push-Location $root
try {
    python @argsList
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
