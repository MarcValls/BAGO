[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [Parameter(Mandatory = $true)]
    [string]$GitRef,
    [Parameter(Mandatory = $true)]
    [string]$GitSha,
    [Parameter(Mandatory = $true)]
    [string]$NsisMakensis
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$versionFile = Join-Path $repoRoot "release_version.txt"
$canonicalVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim()
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "Version canónica inválida: '$Version'"
}
if ($Version -ne $canonicalVersion) {
    throw "Version solicitada '$Version' no coincide con release_version.txt '$canonicalVersion'."
}
if ($GitSha -notmatch '^[0-9a-f]{40}$') {
    throw "GitSha inválido: '$GitSha'."
}
if (-not (Test-Path -LiteralPath $NsisMakensis)) {
    throw "NSIS makensis.exe no encontrado en la ruta fijada: '$NsisMakensis'."
}
$version = $Version
$runtimeDir = Join-Path $scriptDir "compiled\runtime"
$frontendDist = Join-Path $repoRoot "frontend\dist"
$viewerSource = Join-Path $repoRoot "electron-viewer\dist\win-unpacked"
$setupFile = Join-Path $scriptDir "bago-$version-setup.exe"
$nsiFile = Join-Path $scriptDir "bago-installer.nsi"
$zipFile = Join-Path $scriptDir "bago-$version-distribution.zip"

function Add-ZipContents {
    param([string]$ZipPath, [string]$SourceDir)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $compressionLevel = [System.IO.Compression.CompressionLevel]::Optimal
    [System.IO.Compression.ZipFile]::CreateFromDirectory($SourceDir, $ZipPath, $compressionLevel, $false)
}

function Test-ExcludedPath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $normalized = $RelativePath.Replace("/", "\").TrimStart("\")
    if ($normalized.StartsWith("ui-react\dist\", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $parts = $normalized.Split("\", [System.StringSplitOptions]::RemoveEmptyEntries)
    foreach ($part in $parts) {
        if ($part -in @(".git", ".gabo", "__pycache__", ".pytest_cache", "node_modules", ".vite", "dist", "build", "state", "logs")) {
            return $true
        }
    }
    return [System.IO.Path]::GetFileName($RelativePath) -in @("credentials.json", ".env", ".env.local")
}

function Copy-CleanTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $sourceFull = (Resolve-Path -LiteralPath $Source).Path
    foreach ($file in Get-ChildItem -LiteralPath $sourceFull -File -Force -Recurse) {
        $relative = $file.FullName.Substring($sourceFull.Length).TrimStart("\")
        if (Test-ExcludedPath -RelativePath $relative) { continue }
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
    }
}

Write-Host "BAGO $version - constructor de instalador global"

if (-not $SkipBuild) {
    Write-Host "[1/5] Construyendo UI..."
    & python (Join-Path $repoRoot "backend\scripts\build_ui_dist.py")
    if ($LASTEXITCODE -ne 0) { throw "Fallo el build de UI." }

    Write-Host "[2/5] Construyendo Electron..."
    Push-Location $repoRoot
    try {
        & npm run dist --workspace electron-viewer
        if ($LASTEXITCODE -ne 0) { throw "Fallo el build de Electron." }
    } finally {
        Pop-Location
    }
}

Write-Host "[3/5] Preparando payload limpio..."
if (Test-Path -LiteralPath $runtimeDir) {
    $resolvedCompiled = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "compiled"))
    $resolvedRuntime = [System.IO.Path]::GetFullPath($runtimeDir)
    if (-not $resolvedRuntime.StartsWith($resolvedCompiled + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Destino de limpieza inseguro: $resolvedRuntime"
    }
    Remove-Item -LiteralPath $runtimeDir -Recurse -Force
}
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Copy-CleanTree -Source (Join-Path $repoRoot "backend") -Destination $runtimeDir
if (-not (Test-Path -LiteralPath (Join-Path $frontendDist "index.html"))) {
    throw "No existe frontend\\dist\\index.html; construya el frontend antes de empaquetar."
}
$runtimeUiDist = Join-Path $runtimeDir "ui-react\dist"
if (Test-Path -LiteralPath $runtimeUiDist) {
    Remove-Item -LiteralPath $runtimeUiDist -Recurse -Force
}
Copy-Item -LiteralPath $frontendDist -Destination $runtimeUiDist -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\validate_global_payload.ps1") -Destination (Join-Path $runtimeDir "scripts\validate_global_payload.ps1") -Force
Copy-Item -LiteralPath $viewerSource -Destination (Join-Path $runtimeDir "electron-viewer") -Recurse -Force

Write-Host "[3b/5] Comprimiendo payload offline..."
if (Test-Path -LiteralPath $zipFile) { Remove-Item -LiteralPath $zipFile -Force }
Add-ZipContents -ZipPath $zipFile -SourceDir $runtimeDir
$zipHash = (Get-FileHash -LiteralPath $zipFile -Algorithm SHA256).Hash
$zipHashLine = "$zipHash  $([System.IO.Path]::GetFileName($zipFile))"
Set-Content -LiteralPath "$zipFile.sha256" -Value $zipHashLine -Encoding ASCII

Write-Host "[4/5] Validando payload..."
& (Join-Path $repoRoot "scripts\validate_global_payload.ps1") -Root $runtimeDir -ExpectedVersion $version

Write-Host "[5/5] Compilando NSIS..."
Push-Location $scriptDir
try {
    & $NsisMakensis /V3 `
        "/DAPP_VERSION=$version" `
        "/DAPP_GIT_REF=$GitRef" `
        "/DAPP_GIT_SHA=$GitSha" `
        "/DDISTRIBUTION_ZIP_FILE=bago-$version-distribution.zip" `
        "/DDEV_PS1_FILE=..\scripts\dev.ps1" `
        $nsiFile
    if ($LASTEXITCODE -ne 0) { throw "NSIS fallo con codigo $LASTEXITCODE." }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $setupFile)) { throw "No se genero $setupFile" }
$hash = (Get-FileHash -LiteralPath $setupFile -Algorithm SHA256).Hash
$hashLine = "$hash  $([System.IO.Path]::GetFileName($setupFile))"
Set-Content -LiteralPath "$setupFile.sha256" -Value $hashLine -Encoding ASCII
$sizeMb = [Math]::Round((Get-Item -LiteralPath $setupFile).Length / 1MB, 2)

[ordered]@{
    ok = $true
    installer = $setupFile
    version = $version
    size_mb = $sizeMb
    sha256 = $hash
} | ConvertTo-Json -Compress
