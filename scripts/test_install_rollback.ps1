[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PackageZip,
    [string]$WorkRoot = "C:\Bago_v4\release\smoke\rollback-test"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workFull = [System.IO.Path]::GetFullPath($WorkRoot)
$allowedRoot = [System.IO.Path]::GetFullPath("C:\Bago_v4\release\smoke")
if (-not $workFull.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe WorkRoot: $workFull"
}

if (Test-Path -LiteralPath $workFull) {
    Remove-Item -LiteralPath $workFull -Recurse -Force
}

$installDir = Join-Path $workFull "install"
$backupRoot = Join-Path $workFull "backups"
$userState = Join-Path $workFull "userdata"
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $installDir "state") -Force | Out-Null
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

"old-runtime" | Set-Content -LiteralPath (Join-Path $installDir "old_marker.txt") -Encoding UTF8
"preserve-me" | Set-Content -LiteralPath (Join-Path $installDir "state\keep.txt") -Encoding UTF8

& pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\Bago_v4\install-v4.ps1" `
    -PackageZip $PackageZip `
    -InstallDir $installDir `
    -BackupRoot $backupRoot `
    -UserStateDir $userState `
    -SkipTests | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $installDir "install-v4.ps1"))) {
    throw "Install did not copy v4 installer."
}
if (-not (Test-Path -LiteralPath (Join-Path $installDir "state\keep.txt"))) {
    throw "Install did not preserve runtime state."
}

$backup = Get-ChildItem -LiteralPath $backupRoot -Filter "bago-programfiles-backup-*.zip" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $backup) {
    throw "Install did not create rollback backup."
}

& pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\Bago_v4\rollback-v4.ps1" `
    -BackupZip $backup.FullName `
    -InstallDir $installDir `
    -BackupRoot $backupRoot `
    -SkipTests | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $installDir "old_marker.txt"))) {
    throw "Rollback did not restore previous runtime marker."
}
if (-not (Test-Path -LiteralPath (Join-Path $installDir "state\keep.txt"))) {
    throw "Rollback did not preserve current runtime state."
}

[ordered]@{
    ok = $true
    work_root = $workFull
    backup = $backup.FullName
    install_dir = $installDir
} | ConvertTo-Json -Depth 3
