[CmdletBinding()]
param(
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$version = "4.9.0"
$runtimeDir = Join-Path $scriptDir "compiled\runtime"
$viewerSource = Join-Path $repoRoot "electron-viewer\dist\win-unpacked"
$setupFile = Join-Path $scriptDir "bago-$version-setup.exe"
$nsiFile = Join-Path $scriptDir "bago-installer.nsi"

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
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\validate_global_payload.ps1") -Destination (Join-Path $runtimeDir "scripts\validate_global_payload.ps1") -Force
Copy-Item -LiteralPath $viewerSource -Destination (Join-Path $runtimeDir "electron-viewer") -Recurse -Force

Write-Host "[4/5] Validando payload..."
& (Join-Path $repoRoot "scripts\validate_global_payload.ps1") -Root $runtimeDir -ExpectedVersion $version

$makensis = @(
    "C:\Program Files (x86)\NSIS\makensis.exe",
    "C:\Program Files\NSIS\makensis.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $makensis) { throw "NSIS makensis.exe no encontrado." }

Write-Host "[5/5] Compilando NSIS..."
Push-Location $scriptDir
try {
    & $makensis /V3 `
        "/DAPP_VERSION=$version" `
        "/DAPP_GIT_REF=v$version" `
        "/DDISTRIBUTION_ZIP_FILE=bago-$version-distribution.zip" `
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
