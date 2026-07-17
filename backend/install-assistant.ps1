[CmdletBinding()]
param(
    [string]$SourceRoot = "",
    [string]$PackageZip = "",
    [string]$InstallDir = "",
    [ValidateSet("Express", "Advanced")]
    [string]$Mode = "Express",
    [switch]$SkipTests,
    [switch]$NoPathUpdate,
    [switch]$DryRun,
    [switch]$AssumeYes
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

function Resolve-CurrentTree {
    param([Parameter(Mandatory = $true)][string]$Root)
    $rootFull = Get-FullPath $Root
    foreach ($candidate in @($rootFull, (Join-Path $rootFull "current"))) {
        if ((Test-Path -LiteralPath (Join-Path $candidate "install-v4.ps1")) -and
            (Test-Path -LiteralPath (Join-Path $candidate "bago_core\launcher.py"))) {
            return $candidate
        }
    }
    return $null
}

function Get-ManifestPath {
    param([Parameter(Mandatory = $true)][string]$Root)
    $rootFull = Get-FullPath $Root
    foreach ($candidate in @(
        (Join-Path $rootFull "current.manifest.json"),
        (Join-Path $rootFull "current\current.manifest.json"),
        (Join-Path $rootFull "manifest.json")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installScript = Join-Path $scriptRoot "install-v4.ps1"
if (-not (Test-Path -LiteralPath $installScript)) {
    throw "No se encontro install-v4.ps1 junto a install-assistant.ps1: $installScript"
}

if (-not $SourceRoot) {
    $SourceRoot = $scriptRoot
}

if ($PackageZip) {
    $zipFull = Get-FullPath $PackageZip
    if (-not (Test-Path -LiteralPath $zipFull)) {
        throw "No se encontro el paquete ZIP: $zipFull"
    }
    Write-Host "[install-assistant] PackageZip: $zipFull"
    if ($DryRun) {
        Write-Host "[install-assistant] No se ejecuta el instalador."
        exit 0
    }
    if (-not $AssumeYes) {
        $answer = Read-Host "Ejecutar instalador local sobre $InstallDir? [s/N]"
        if ($answer.Trim().ToLowerInvariant() -notin @("s", "si", "y", "yes")) {
            Write-Host "[install-assistant] Cancelado."
            exit 1
        }
    }

    $argsList = @(
        "-PackageZip", $zipFull,
        "-InstallDir", (Get-FullPath $InstallDir),
        "-Mode", $Mode
    )
    if ($SkipTests) { $argsList += "-SkipTests" }
    if ($NoPathUpdate) { $argsList += "-NoPathUpdate" }

    & powershell.exe -ExecutionPolicy Bypass -File $installScript @argsList
    exit $LASTEXITCODE
}

$resolvedSource = Resolve-CurrentTree -Root $SourceRoot
if (-not $resolvedSource) {
    throw "No se encontro un arbol instalable dentro de: $SourceRoot"
}

$manifestPath = Get-ManifestPath -Root (Split-Path -Parent $resolvedSource)
if ($manifestPath) {
    Write-Host "[install-assistant] Manifest: $manifestPath"
}
Write-Host "[install-assistant] SourceRoot: $resolvedSource"

if ($DryRun) {
    Write-Host "[install-assistant] No se ejecuta el instalador."
    exit 0
}

if (-not $AssumeYes) {
    $answer = Read-Host "Ejecutar instalador local sobre $InstallDir? [s/N]"
    if ($answer.Trim().ToLowerInvariant() -notin @("s", "si", "y", "yes")) {
        Write-Host "[install-assistant] Cancelado."
        exit 1
    }
}

$argsList = @(
    "-SourceRoot", $resolvedSource,
    "-InstallDir", (Get-FullPath $InstallDir),
    "-Mode", $Mode
)
if ($SkipTests) { $argsList += "-SkipTests" }
if ($NoPathUpdate) { $argsList += "-NoPathUpdate" }

& powershell.exe -ExecutionPolicy Bypass -File $installScript @argsList
$profileCandidates = @($PROFILE.CurrentUserAllHosts, $PROFILE.CurrentUserCurrentHost) | Where-Object { $_ }
foreach ($profilePath in $profileCandidates) {
    if (Test-Path -LiteralPath $profilePath) {
        . $profilePath
    }
}
exit $LASTEXITCODE
