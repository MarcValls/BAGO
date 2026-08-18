#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Root,
    [string]$ExpectedVersion = "4.9.0"
)

$ErrorActionPreference = "Stop"
$rootFull = (Resolve-Path -LiteralPath $Root).Path
$required = @(
    "release_version.txt",
    "bago.ps1",
    "bago_core\cli.py",
    "ui-react\dist\index.html",
    "scripts\runtime-service.ps1",
    "scripts\global-install-shell.ps1",
    "electron-viewer\BAGO.exe",
    "electron-viewer\resources\app.asar",
    "electron-viewer\resources\scripts\dev.ps1",
    "electron-viewer\locales\en-US.pak"
)

$missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $rootFull $_)) })
if ($missing.Count -gt 0) {
    throw "Payload global incompleto: $($missing -join ', ')"
}

$releaseVersion = (Get-Content -LiteralPath (Join-Path $rootFull "release_version.txt") -Raw).Trim()
if ($releaseVersion -ne $ExpectedVersion) {
    throw "Version de runtime inesperada: $releaseVersion != $ExpectedVersion"
}

$exeVersion = (Get-Item -LiteralPath (Join-Path $rootFull "electron-viewer\BAGO.exe")).VersionInfo.ProductVersion
if (-not $exeVersion.StartsWith($ExpectedVersion)) {
    throw "Version de BAGO.exe inesperada: $exeVersion != $ExpectedVersion"
}

[ordered]@{
    ok = $true
    root = $rootFull
    version = $releaseVersion
    executable_version = $exeVersion
    required_files = $required.Count
} | ConvertTo-Json -Compress
