[CmdletBinding()]
param(
    [string]$BackupZip = "",
    [string]$InstallDir = "C:\Program Files\BAGO",
    [string]$BackupRoot = "$env:ProgramData\BAGO\backups",
    [switch]$RestoreBackedUpState,
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-SafeTarget {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = Get-FullPath $Path
    $root = [System.IO.Path]::GetPathRoot($full)
    if ([string]::IsNullOrWhiteSpace($full) -or $full -eq $root) {
        throw "Unsafe rollback target: $full"
    }
    return $full
}

function Move-PreservedRuntimeState {
    param(
        [Parameter(Mandatory = $true)][string]$InstallPath,
        [Parameter(Mandatory = $true)][string]$PreservePath
    )
    $preserved = @()
    foreach ($rel in @(".bago\state", ".bago\logs", "state", "logs")) {
        $src = Join-Path $InstallPath $rel
        if (Test-Path -LiteralPath $src) {
            $dst = Join-Path $PreservePath $rel
            New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
            Move-Item -LiteralPath $src -Destination $dst -Force
            $preserved += $rel
        }
    }
    return $preserved
}

function Restore-PreservedRuntimeState {
    param(
        [Parameter(Mandatory = $true)][string]$InstallPath,
        [Parameter(Mandatory = $true)][string]$PreservePath
    )
    if (-not (Test-Path -LiteralPath $PreservePath)) {
        return
    }
    foreach ($rel in @(".bago\state", ".bago\logs", "state", "logs")) {
        $src = Join-Path $PreservePath $rel
        if (-not (Test-Path -LiteralPath $src)) {
            continue
        }
        $target = Join-Path $InstallPath $rel
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Move-Item -LiteralPath $src -Destination $target -Force
    }
}

$installFull = Assert-SafeTarget $InstallDir
$backupFull = Get-FullPath $BackupRoot

if (-not $BackupZip) {
    $latest = Get-ChildItem -LiteralPath $backupFull -Filter "bago-programfiles-backup-*.zip" -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No backup zip found in $backupFull"
    }
    $BackupZip = $latest.FullName
}

$backupZipFull = (Resolve-Path -LiteralPath $BackupZip).Path
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$safetyZip = Join-Path $backupFull "bago-pre-rollback-safety-$stamp.zip"

New-Item -ItemType Directory -Path $backupFull -Force | Out-Null
if (Test-Path -LiteralPath $installFull) {
    $children = Get-ChildItem -LiteralPath $installFull -Force
    if ($children.Count -gt 0) {
        Compress-Archive -Path (Join-Path $installFull "*") -DestinationPath $safetyZip -CompressionLevel Optimal -Force
    }
} else {
    New-Item -ItemType Directory -Path $installFull -Force | Out-Null
}

$preserved = @()
$preserveTemp = Join-Path ([System.IO.Path]::GetTempPath()) "bago-v4-rollback-preserve-$stamp"
if (-not $RestoreBackedUpState) {
    New-Item -ItemType Directory -Path $preserveTemp -Force | Out-Null
    $preserved = Move-PreservedRuntimeState -InstallPath $installFull -PreservePath $preserveTemp
}

Get-ChildItem -LiteralPath $installFull -Force | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

Expand-Archive -LiteralPath $backupZipFull -DestinationPath $installFull -Force

if (-not $RestoreBackedUpState) {
    Restore-PreservedRuntimeState -InstallPath $installFull -PreservePath $preserveTemp
}

if (-not $SkipTests) {
    $launcher = Join-Path $installFull "bago_core\launcher.py"
    if (Test-Path -LiteralPath $launcher) {
        Push-Location $installFull
        try {
            & python "bago_core\launcher.py" "--test"
            if ($LASTEXITCODE -ne 0) { throw "launcher.py --test failed with exit code $LASTEXITCODE" }
        } finally {
            Pop-Location
        }
    }
}

$result = [ordered]@{
    ok = $true
    restored_to = $installFull
    backup_zip = $backupZipFull
    safety_zip = $safetyZip
    preserved_current_runtime_state = $preserved
    restored_backed_up_state = [bool]$RestoreBackedUpState
    timestamp = $stamp
}

$result | ConvertTo-Json -Depth 4
