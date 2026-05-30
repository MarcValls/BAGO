[CmdletBinding()]
param(
    [string]$SourceRoot = "",
    [string]$PackageZip = "",
    [string]$InstallDir = "C:\Program Files\BAGO",
    [string]$BackupRoot = "$env:ProgramData\BAGO\backups",
    [string]$UserStateDir = "$env:ProgramData\BAGO\user",
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
        throw "Unsafe install target: $full"
    }
    return $full
}

function Test-ReleaseExcluded {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $rel = $RelativePath.Replace("\", "/").TrimStart("/")
    $parts = $rel.Split("/", [System.StringSplitOptions]::RemoveEmptyEntries)
    foreach ($part in $parts) {
        if ($part -in @(".git", "__pycache__", ".pytest_cache", "node_modules", ".vite")) {
            return $true
        }
    }
    if ([System.IO.Path]::GetFileName($rel) -in @("credentials.json", ".env", ".env.local")) {
        return $true
    }
    foreach ($prefix in @(".bago/state", ".bago/logs", "state", "logs", "PLAN_VERTICE", "release", "dist", "build")) {
        if ($rel -eq $prefix -or $rel.StartsWith("$prefix/")) {
            return $true
        }
    }
    return $false
}

function Copy-ReleaseTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $sourceFull = Get-FullPath $Source
    $destFull = Get-FullPath $Destination
    Get-ChildItem -LiteralPath $sourceFull -Force -Recurse -File | ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($sourceFull, $_.FullName)
        if (Test-ReleaseExcluded $relative) {
            return
        }
        $target = Join-Path $destFull $relative
        $targetParent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $targetParent -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
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
$userStateFull = Get-FullPath $UserStateDir
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$tempExtract = $null
$backupZip = $null

if ($PackageZip) {
    $zipFull = (Resolve-Path -LiteralPath $PackageZip).Path
    $tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) "bago-v4-install-$stamp"
    New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
    Expand-Archive -LiteralPath $zipFull -DestinationPath $tempExtract -Force
    $SourceRoot = $tempExtract
}

if (-not $SourceRoot) {
    $SourceRoot = $PSScriptRoot
}

$sourceFull = (Resolve-Path -LiteralPath $SourceRoot).Path
if ($sourceFull -eq $installFull) {
    throw "SourceRoot and InstallDir cannot be the same path."
}

New-Item -ItemType Directory -Path $backupFull -Force | Out-Null
New-Item -ItemType Directory -Path $userStateFull -Force | Out-Null

if (Test-Path -LiteralPath $installFull) {
    $backupZip = Join-Path $backupFull "bago-programfiles-backup-$stamp.zip"
    $children = Get-ChildItem -LiteralPath $installFull -Force
    if ($children.Count -gt 0) {
        Compress-Archive -Path (Join-Path $installFull "*") -DestinationPath $backupZip -CompressionLevel Optimal -Force
    } else {
        $backupZip = $null
    }
} else {
    New-Item -ItemType Directory -Path $installFull -Force | Out-Null
}

$preserveTemp = Join-Path ([System.IO.Path]::GetTempPath()) "bago-v4-preserve-$stamp"
New-Item -ItemType Directory -Path $preserveTemp -Force | Out-Null
$preserved = Move-PreservedRuntimeState -InstallPath $installFull -PreservePath $preserveTemp

Get-ChildItem -LiteralPath $installFull -Force | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

Copy-ReleaseTree -Source $sourceFull -Destination $installFull
Restore-PreservedRuntimeState -InstallPath $installFull -PreservePath $preserveTemp

if (-not $SkipTests) {
    Push-Location $installFull
    try {
        & python "bago_core\launcher.py" "--test"
        if ($LASTEXITCODE -ne 0) { throw "launcher.py --test failed with exit code $LASTEXITCODE" }
        & python "test_security_release.py"
        if ($LASTEXITCODE -ne 0) { throw "test_security_release.py failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

$result = [ordered]@{
    ok = $true
    installed_to = $installFull
    source = $sourceFull
    backup_zip = $backupZip
    preserved_runtime_state = $preserved
    user_state_dir = $userStateFull
    timestamp = $stamp
}

$result | ConvertTo-Json -Depth 4
