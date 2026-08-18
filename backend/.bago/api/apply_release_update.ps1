[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [Parameter(Mandatory = $true)][string]$InstallRoot,
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][string]$ExpectedVersion,
    [Parameter(Mandatory = $true)][string]$ExpectedSha256,
    [int]$BackendPid = 0,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$installFull = [System.IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$bundleFull = [System.IO.Path]::GetFullPath($BundlePath)
$stateFull = [System.IO.Path]::GetFullPath($StatePath)
$backendTarget = Join-Path $installFull "backend"
$viewerTarget = Join-Path $installFull "electron-viewer"
$previousVersion = ""

function Write-UpdateState {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$ErrorMessage = "",
        [string]$BackupPath = ""
    )
    $parent = Split-Path -Parent $stateFull
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $payload = [ordered]@{
        status = $Status
        phase = $Status
        message = $Message
        current = if ($Status -eq "completed") { $ExpectedVersion.TrimStart('v', 'V') } else { $previousVersion }
        latest = $ExpectedVersion
        available = ($Status -eq "error")
        percent = if ($Status -eq "completed") { 100 } else { 0 }
        transferred = 0
        total = 0
        release = @{}
        installation = @{ ready = $true; root = $installFull; viewer = (Join-Path $viewerTarget "BAGO.exe"); reason = "" }
        error = $ErrorMessage
        detail = @{ backup_path = $BackupPath }
        updated_at = [DateTime]::UtcNow.ToString("o")
    }
    $temp = $stateFull + ".tmp"
    $payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $stateFull -Force
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

$workRoot = Join-Path (Split-Path -Parent $stateFull) ("stage-" + [Guid]::NewGuid().ToString("N"))
$extractRoot = Join-Path $workRoot "extract"
$backupRoot = Join-Path $installFull ("backups\updates\" + $ExpectedVersion.TrimStart('v', 'V') + "-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ"))
$sourceBackend = Join-Path $extractRoot "compiled\backend"
$sourceViewer = Join-Path $extractRoot "compiled\electron-viewer"
$backendBackup = Join-Path $backupRoot "backend"
$viewerBackup = Join-Path $backupRoot "electron-viewer"
$backendMoved = $false
$viewerMoved = $false
$newBackendInstalled = $false
$newViewerInstalled = $false
$processesStopped = $false

try {
    $rootPath = [System.IO.Path]::GetPathRoot($installFull).TrimEnd('\')
    if ($installFull -eq $rootPath -or [System.IO.Path]::GetFileName($installFull) -ne "BAGO") {
        throw "Destino de actualización inseguro: $installFull"
    }
    if (-not $stateFull.StartsWith($installFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "El estado del actualizador debe permanecer dentro de la instalación."
    }
    if (-not (Test-Path -LiteralPath $backendTarget) -or -not (Test-Path -LiteralPath (Join-Path $viewerTarget "BAGO.exe"))) {
        throw "La instalación no contiene backend y electron-viewer esperados."
    }
    $previousVersionPath = Join-Path $backendTarget "release_version.txt"
    $previousVersion = if (Test-Path -LiteralPath $previousVersionPath) { (Get-Content -LiteralPath $previousVersionPath -Raw).Trim().TrimStart('v', 'V') } else { "" }
    $actualSha = Get-Sha256 -Path $bundleFull
    if ($actualSha -ne $ExpectedSha256.ToLowerInvariant()) {
        throw "SHA-256 del payload cambió antes de instalar."
    }
    Write-UpdateState -Status "applying" -Message "Extrayendo y validando actualización…"
    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    Expand-Archive -LiteralPath $bundleFull -DestinationPath $extractRoot -Force
    $versionFile = Join-Path $sourceBackend "release_version.txt"
    $newViewerExe = Join-Path $sourceViewer "BAGO.exe"
    if (-not (Test-Path -LiteralPath $versionFile) -or -not (Test-Path -LiteralPath $newViewerExe)) {
        throw "El payload no contiene los dos componentes instalables."
    }
    $packagedVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim().TrimStart('v', 'V')
    if ($packagedVersion -ne $ExpectedVersion.TrimStart('v', 'V')) {
        throw "Versión inesperada en payload: $packagedVersion"
    }

    Start-Sleep -Seconds 2
    Get-CimInstance Win32_Process -Filter "Name = 'BAGO.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        $exePath = [string]$_.ExecutablePath
        if ($exePath -and $exePath.StartsWith($installFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    if ($BackendPid -gt 0 -and $BackendPid -ne $PID) {
        Stop-Process -Id $BackendPid -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    $processesStopped = $true

    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Move-Item -LiteralPath $backendTarget -Destination $backendBackup
    $backendMoved = $true
    Move-Item -LiteralPath $viewerTarget -Destination $viewerBackup
    $viewerMoved = $true
    Move-Item -LiteralPath $sourceBackend -Destination $backendTarget
    $newBackendInstalled = $true
    Move-Item -LiteralPath $sourceViewer -Destination $viewerTarget
    $newViewerInstalled = $true

    if (-not (Test-Path -LiteralPath (Join-Path $backendTarget "bago_core\launcher.py")) -or
        -not (Test-Path -LiteralPath (Join-Path $viewerTarget "BAGO.exe"))) {
        throw "La validación posterior a la instalación ha fallado."
    }
    Write-UpdateState -Status "completed" -Message "BAGO se actualizó correctamente." -BackupPath $backupRoot
    if ($Restart) {
        Start-Process -FilePath (Join-Path $viewerTarget "BAGO.exe") -WorkingDirectory $viewerTarget
    }
}
catch {
    $failure = $_.Exception.Message
    if ($newBackendInstalled -and (Test-Path -LiteralPath $backendTarget)) { Remove-Item -LiteralPath $backendTarget -Recurse -Force }
    if ($newViewerInstalled -and (Test-Path -LiteralPath $viewerTarget)) { Remove-Item -LiteralPath $viewerTarget -Recurse -Force }
    if ($backendMoved -and (Test-Path -LiteralPath $backendBackup)) { Move-Item -LiteralPath $backendBackup -Destination $backendTarget }
    if ($viewerMoved -and (Test-Path -LiteralPath $viewerBackup)) { Move-Item -LiteralPath $viewerBackup -Destination $viewerTarget }
    Write-UpdateState -Status "error" -Message "La actualización falló y se restauró la versión anterior." -ErrorMessage $failure -BackupPath $backupRoot
    if ($Restart -and $processesStopped -and (Test-Path -LiteralPath (Join-Path $viewerTarget "BAGO.exe"))) {
        Start-Process -FilePath (Join-Path $viewerTarget "BAGO.exe") -WorkingDirectory $viewerTarget
    }
    exit 1
}
finally {
    if (Test-Path -LiteralPath $workRoot) { Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $bundleFull) { Remove-Item -LiteralPath $bundleFull -Force -ErrorAction SilentlyContinue }
}
