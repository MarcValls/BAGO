[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$Publisher,
    [Parameter(Mandatory = $true)][string]$PackageName,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [switch]$AllowDirtyCandidate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($Version -ne (Get-Content (Join-Path $repo 'release_version.txt') -Raw).Trim()) {
    throw 'Requested version does not match release_version.txt.'
}
if ($Publisher -notmatch '^CN=') { throw 'Production publisher must be an exact CN= subject.' }

$build = Join-Path $repo 'releases/build-installer.ps1'
$payloadOutput = @(& $build -RuntimeOnly -Version $Version)
$payloadJson = $payloadOutput | Where-Object { $_ -is [string] -and $_.TrimStart().StartsWith('{') } | Select-Object -Last 1
$payloadResult = $payloadJson | ConvertFrom-Json
if (-not $payloadResult.ok -or -not (Test-Path -LiteralPath $payloadResult.runtime)) {
    throw 'Runtime payload construction did not produce a usable candidate.'
}

$out = [IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $out) { throw "OutputRoot already exists: $out" }
$candidateRoot = Join-Path ([IO.Path]::GetTempPath()) ("bago-msix-source-" + [guid]::NewGuid().ToString('N'))
try {
    New-Item -ItemType Directory -Path (Join-Path $candidateRoot 'backend') -Force | Out-Null
    Copy-Item (Join-Path $payloadResult.runtime '*') (Join-Path $candidateRoot 'backend') -Recurse -Force
    & (Join-Path $repo 'scripts/build-msix-bootstrap.ps1') `
        -PayloadRoot $candidateRoot `
        -Publisher $Publisher `
        -PackageName $PackageName `
        -OutputRoot $out `
        -AllowDirtyCandidate:$AllowDirtyCandidate
    if ($LASTEXITCODE -ne 0) { throw 'MSIX bootstrap construction failed.' }
} finally {
    if (Test-Path -LiteralPath $candidateRoot) { Remove-Item -LiteralPath $candidateRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

$receipt = Get-Content (Join-Path $out 'build-receipt.json') -Raw | ConvertFrom-Json
if ($receipt.signature -ne 'NOT_SIGNED') { throw 'Unsigned build receipt unexpectedly claims a signature.' }
Write-Output (Join-Path $out 'build-receipt.json')
