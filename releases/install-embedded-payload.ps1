[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$ZipPath
)

$ErrorActionPreference = "Stop"

function Assert-SafeInstallRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $root = [System.IO.Path]::GetPathRoot($full).TrimEnd('\')
    if ($full -eq $root) {
        throw "Ruta de instalación insegura: no se permite usar la raíz del disco ($full)."
    }

    $leaf = [System.IO.Path]::GetFileName($full)
    if ($leaf -ne "BAGO") {
        throw "Ruta de instalación insegura: debe terminar en 'BAGO'. Ruta recibida: $full"
    }
}

function Test-IsSameOrChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$CandidatePath
    )

    $baseNorm = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\')
    $candNorm = [System.IO.Path]::GetFullPath($CandidatePath).TrimEnd('\')
    if ($candNorm.Equals($baseNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    $prefix = $baseNorm + [System.IO.Path]::DirectorySeparatorChar
    return $candNorm.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Stop-BagoProcessesForPath {
    param([Parameter(Mandatory = $true)][string]$TargetRoot)

    $normalized = [System.IO.Path]::GetFullPath($TargetRoot).TrimEnd('\')
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'BAGO.exe'" -ErrorAction SilentlyContinue
    foreach ($proc in $procs) {
        $exePath = $proc.ExecutablePath
        if (-not $exePath) { continue }
        if (Test-IsSameOrChildPath -BasePath $normalized -CandidatePath $exePath) {
            Write-Host "Cerrando proceso BAGO en uso: PID $($proc.ProcessId)"
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Remove-TreeWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$Attempts = 5
    )

    for ($i = 1; $i -le $Attempts; $i++) {
        if (-not (Test-Path -LiteralPath $Path)) { return }
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($i -eq $Attempts) { throw }
            Start-Sleep -Seconds 1
        }
    }
}

function Resolve-SourceRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExtractRoot
    )

    $candidates = @(
        (Join-Path $ExtractRoot "compiled"),
        $ExtractRoot
    )

    foreach ($candidate in $candidates) {
        $backendPath = Join-Path $candidate "backend"
        $viewerPath = Join-Path $candidate "electron-viewer"
        if ((Test-Path $backendPath) -and (Test-Path $viewerPath)) {
            return $candidate
        }
    }

    $nested = Get-ChildItem -Path $ExtractRoot -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            (Test-Path (Join-Path $_.FullName "backend")) -and
            (Test-Path (Join-Path $_.FullName "electron-viewer"))
        } |
        Select-Object -First 1

    if ($nested) {
        return $nested.FullName
    }

    throw "No se encontraron carpetas backend y electron-viewer en el payload extraído."
}

if (-not (Test-Path -LiteralPath $ZipPath)) {
    throw "No existe el ZIP embebido: $ZipPath"
}

Assert-SafeInstallRoot -Path $RepoRoot
Stop-BagoProcessesForPath -TargetRoot $RepoRoot
if (Test-Path -LiteralPath $RepoRoot) {
    Write-Host "Eliminando instalación previa..."
    Remove-TreeWithRetry -Path $RepoRoot
}
New-Item -ItemType Directory -Path $RepoRoot -Force | Out-Null

$tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-dist-tmp-" + [Guid]::NewGuid().ToString("N"))
try {
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $tempExtract -Force

    $sourceRoot = Resolve-SourceRoot -ExtractRoot $tempExtract

    Copy-Item -Path (Join-Path $sourceRoot "backend") -Destination (Join-Path $RepoRoot "backend") -Recurse -Force
    Copy-Item -Path (Join-Path $sourceRoot "electron-viewer") -Destination (Join-Path $RepoRoot "electron-viewer") -Recurse -Force

    $exeCandidates = @(
        (Join-Path $RepoRoot "electron-viewer\BAGO.exe"),
        (Join-Path $RepoRoot "electron-viewer\dist\win-unpacked\BAGO.exe")
    )
    $exe = $exeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) {
        throw "No se encontró BAGO.exe tras instalar el payload."
    }
}
finally {
    Remove-Item -LiteralPath $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}
