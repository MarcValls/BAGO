[CmdletBinding()]
param(
    [string]$RepoRoot = "$env:LOCALAPPDATA\BAGO",
    [string]$ZipPath = "",
    [string]$Sha256Path = "",
    [switch]$Finalize
)

$ErrorActionPreference = "Stop"

function Assert-SafeInstallRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $root = [System.IO.Path]::GetPathRoot($full).TrimEnd('\')
    if ($full -eq $root) {
        throw "Ruta de instalacion insegura: no se permite usar la raiz del disco ($full)."
    }

    $leaf = [System.IO.Path]::GetFileName($full)
    if ($leaf -ne "BAGO") {
        throw "Ruta de instalacion insegura: debe terminar en 'BAGO'. Ruta recibida: $full"
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

function Get-BackupDir {
    param([Parameter(Mandatory = $true)][string]$TargetRoot)

    $parent = Split-Path -Path $TargetRoot -Parent
    return Join-Path $parent ".BAGO-rollback"
}

function Backup-Target {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Backup
    )

    if (-not (Test-Path -LiteralPath $Source)) { return }
    if (Test-Path -LiteralPath $Backup) {
        Remove-TreeWithRetry -Path $Backup
    }
    New-Item -ItemType Directory -Path $Backup -Force | Out-Null
    Get-ChildItem -Path $Source -Force | Copy-Item -Destination $Backup -Recurse -Force
}

function Restore-Backup {
    param(
        [Parameter(Mandatory = $true)][string]$Backup,
        [Parameter(Mandatory = $true)][string]$Target
    )

    if (-not (Test-Path -LiteralPath $Backup)) { return }
    if (Test-Path -LiteralPath $Target) {
        Remove-TreeWithRetry -Path $Target
    }
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    Get-ChildItem -Path $Backup -Force | Copy-Item -Destination $Target -Recurse -Force
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
        $flatBackendMarker = Join-Path $candidate "bago_core/cli.py"
        if ((Test-Path $backendPath) -and (Test-Path $viewerPath)) {
            return @{ Root = $candidate; Backend = $backendPath; Viewer = $viewerPath }
        }
        if ((Test-Path $flatBackendMarker) -and (Test-Path $viewerPath)) {
            return @{ Root = $candidate; Backend = $candidate; Viewer = $viewerPath }
        }
    }

    $nested = Get-ChildItem -Path $ExtractRoot -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            (
                (Test-Path (Join-Path $_.FullName "backend")) -and
                (Test-Path (Join-Path $_.FullName "electron-viewer"))
            ) -or (
                (Test-Path (Join-Path $_.FullName "bago_core/cli.py")) -and
                (Test-Path (Join-Path $_.FullName "electron-viewer"))
            )
        } |
        Select-Object -First 1

    if ($nested) {
        $nestedBackend = Join-Path $nested.FullName "backend"
        if (Test-Path $nestedBackend) {
            return @{ Root = $nested.FullName; Backend = $nestedBackend; Viewer = (Join-Path $nested.FullName "electron-viewer") }
        }
        return @{ Root = $nested.FullName; Backend = $nested.FullName; Viewer = (Join-Path $nested.FullName "electron-viewer") }
    }

    throw "No se encontraron carpetas backend y electron-viewer en el payload extraido."
}

Assert-SafeInstallRoot -Path $RepoRoot

$backupDir = Get-BackupDir -TargetRoot $RepoRoot

if ($Finalize) {
    if (Test-Path -LiteralPath $backupDir) {
        Write-Host "Eliminando rollback finalizado..."
        Remove-TreeWithRetry -Path $backupDir
    }
    return
}

if ([string]::IsNullOrWhiteSpace($ZipPath)) {
    throw "ZipPath es obligatorio para instalar un payload embebido."
}

if (-not (Test-Path -LiteralPath $ZipPath)) {
    throw "No existe el ZIP embebido: $ZipPath"
}

if ([string]::IsNullOrWhiteSpace($Sha256Path)) {
    throw "Sha256Path es obligatorio para instalar un payload embebido."
}

if (-not (Test-Path -LiteralPath $Sha256Path)) {
    throw "No existe el sidecar SHA-256: $Sha256Path"
}

$expectedHash = (Get-Content -LiteralPath $Sha256Path -TotalCount 1).Trim().Split()[0]
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $stream = [System.IO.File]::OpenRead($ZipPath)
    $actualHash = [System.BitConverter]::ToString($sha256.ComputeHash($stream)).Replace("-", "")
}
finally {
    if ($stream) { $stream.Dispose() }
    $sha256.Dispose()
}
if ($expectedHash -ne $actualHash) {
    throw "SHA-256 mismatch: esperado $expectedHash, obtenido $actualHash"
}

$tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ("bago-dist-tmp-" + [Guid]::NewGuid().ToString("N"))
try {
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $tempExtract -Force
    $sourceRoot = Resolve-SourceRoot -ExtractRoot $tempExtract

    $exeCandidates = @(
        (Join-Path $sourceRoot.Viewer "BAGO.exe"),
        (Join-Path $sourceRoot.Viewer "dist\win-unpacked\BAGO.exe")
    )
    $exe = $exeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) {
        throw "No se encontro BAGO.exe en el payload extraido."
    }

    Stop-BagoProcessesForPath -TargetRoot $RepoRoot

    $hasBackup = Test-Path -LiteralPath $backupDir
    $targetExists = Test-Path -LiteralPath $RepoRoot
    $looksUnfinalized = $targetExists -and (Test-Path (Join-Path $RepoRoot "electron-viewer\BAGO.exe"))

    if ($hasBackup -and (-not $targetExists -or $looksUnfinalized)) {
        Write-Host "Restaurando backup previo..."
        Restore-Backup -Backup $backupDir -Target $RepoRoot
    }

    if (Test-Path -LiteralPath $RepoRoot) {
        Backup-Target -Source $RepoRoot -Backup $backupDir
    }

    if (Test-Path -LiteralPath $RepoRoot) {
        Remove-TreeWithRetry -Path $RepoRoot
    }
    New-Item -ItemType Directory -Path $RepoRoot -Force | Out-Null

    Copy-Item -Path $sourceRoot.Backend -Destination (Join-Path $RepoRoot "backend") -Recurse -Force
    Copy-Item -Path $sourceRoot.Viewer -Destination (Join-Path $RepoRoot "electron-viewer") -Recurse -Force
}
finally {
    Remove-Item -LiteralPath $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
}
