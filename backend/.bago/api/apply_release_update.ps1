[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [Parameter(Mandatory = $true)][string]$InstallRoot,
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][string]$ExpectedVersion,
    [Parameter(Mandatory = $true)][string]$ExpectedSha256,
    [Parameter(Mandatory = $true)][string]$AuthorizationLedgerPath,
    [Parameter(Mandatory = $true)][string]$AuthorizationTicketPath,
    [Parameter(Mandatory = $true)][string]$AuthorizationTicketNonce,
    [Parameter(Mandatory = $true)][string]$PermitId,
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

function Consume-AuthorizationTicket {
    $expectedTicket = Join-Path (Split-Path -Parent $bundleFull) (".apply-" + $PermitId + ".json")
    $ticketFull = [System.IO.Path]::GetFullPath($AuthorizationTicketPath)
    if ($ticketFull -ne [System.IO.Path]::GetFullPath($expectedTicket) -or
        -not (Test-Path -LiteralPath $ticketFull -PathType Leaf) -or
        (((Get-Item -LiteralPath $ticketFull).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "La actualización requiere un ticket de autorización emitido por ExecutionGateway."
    }

    try {
        $ticket = Get-Content -LiteralPath $ticketFull -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "El ticket de autorización no se puede leer."
    }
    $target = $ticket.target
    $ledgerPath = [System.IO.Path]::GetFullPath($AuthorizationLedgerPath)
    if ($env:BAGO_STATE_ROOT) {
        $canonicalStateRoot = [System.IO.Path]::GetFullPath($env:BAGO_STATE_ROOT)
    }
    elseif ($env:BAGO_USER_ROOT) {
        $canonicalStateRoot = [System.IO.Path]::GetFullPath((Join-Path $env:BAGO_USER_ROOT "state"))
    }
    else {
        $userRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "BAGO" } else { Join-Path $env:USERPROFILE "AppData\Local\BAGO" }
        $canonicalStateRoot = [System.IO.Path]::GetFullPath((Join-Path $userRoot "state"))
    }
    $canonicalLedger = [System.IO.Path]::GetFullPath((Join-Path $canonicalStateRoot "authorization\ledger.json"))
    if ($ledgerPath -ne $canonicalLedger -or -not (Test-Path -LiteralPath $ledgerPath -PathType Leaf)) {
        throw "La ruta del ledger de autorización no es canónica."
    }
    try {
        $ledger = Get-Content -LiteralPath $ledgerPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "El ledger de autorización no se puede leer."
    }
    $permitRecord = $null
    foreach ($entry in $ledger.permits.PSObject.Properties) {
        if ($entry.Value.permit_id -eq $PermitId) {
            $permitRecord = $entry.Value
            break
        }
    }
    $request = $permitRecord.executed_request
    $proof = $permitRecord.proof
    $decision = $permitRecord.decision
    $authorizedTarget = $request.target
    if ($ticket.schema -ne "bago.system-update-helper-ticket.v1" -or
        $ticket.permit_id -ne $PermitId -or
        $ticket.nonce -ne $AuthorizationTicketNonce -or
        $ticket.effect_id -ne "system.update.apply" -or
        [string]::IsNullOrWhiteSpace([string]$ticket.session_id) -or
        $ticket.operation_fingerprint -notmatch '^[a-f0-9]{64}$' -or
        $permitRecord.state -ne "consumed" -or
        $permitRecord.effect_id -ne "system.update.apply" -or
        $permitRecord.session_id -ne $ticket.session_id -or
        $permitRecord.operation_fingerprint -ne $ticket.operation_fingerprint -or
        $request.effect_id -ne "system.update.apply" -or
        $request.actor_kind -ne "user" -or
        $request.principal_id -ne "interactive-local-user" -or
        $request.source_surface -ne "api.release.apply" -or
        $request.scope -ne "system" -or
        $request.operation_fingerprint -ne $ticket.operation_fingerprint -or
        $request.arguments_digest -ne "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a" -or
        $proof.proof_id -ne $permitRecord.proof_id -or
        $proof.effect_id -ne "system.update.apply" -or
        $proof.operation_fingerprint -ne $ticket.operation_fingerprint -or
        $proof.authenticated_session_id -ne $ticket.session_id -or
        $proof.user_decision -ne "approve" -or
        $proof.provenance.kind -ne "direct_user_interaction" -or
        $proof.provenance.channel -notin @("ui-react", "desktop") -or
        $decision.result -ne "allow" -or
        $decision.proof_id -ne $proof.proof_id -or
        $decision.operation_fingerprint -ne $ticket.operation_fingerprint -or
        $decision.effect_id -ne "system.update.apply" -or
        $target.authorization_ledger_path -ne $ledgerPath -or
        $authorizedTarget.bundle_path -ne $target.bundle_path -or
        $authorizedTarget.bundle_sha256 -ne $target.bundle_sha256 -or
        $authorizedTarget.helper_path -ne $target.helper_path -or
        $authorizedTarget.helper_sha256 -ne $target.helper_sha256 -or
        $authorizedTarget.install_root -ne $target.install_root -or
        $authorizedTarget.state_path -ne $target.state_path -or
        $authorizedTarget.expected_version -ne $target.expected_version -or
        $authorizedTarget.authorization_ledger_path -ne $ledgerPath -or
        $authorizedTarget.backend_pid -ne $target.backend_pid -or
        $authorizedTarget.restart -ne $target.restart -or
        [System.IO.Path]::GetFullPath([string]$authorizedTarget.bundle_path) -ne $bundleFull -or
        [System.IO.Path]::GetFullPath([string]$authorizedTarget.install_root) -ne $installFull -or
        [System.IO.Path]::GetFullPath([string]$authorizedTarget.state_path) -ne $stateFull -or
        [string]$authorizedTarget.expected_version -ne $ExpectedVersion -or
        [int]$authorizedTarget.backend_pid -ne $BackendPid -or
        [bool]$authorizedTarget.restart -ne [bool]$Restart -or
        [System.IO.Path]::GetFullPath([string]$authorizedTarget.helper_path) -ne [System.IO.Path]::GetFullPath($PSCommandPath) -or
        [string]$authorizedTarget.helper_sha256 -ne (Get-Sha256 -Path $PSCommandPath) -or
        [System.IO.Path]::GetFullPath([string]$target.bundle_path) -ne $bundleFull -or
        [string]$target.bundle_sha256 -ne $ExpectedSha256.ToLowerInvariant() -or
        [System.IO.Path]::GetFullPath([string]$target.install_root) -ne $installFull -or
        [System.IO.Path]::GetFullPath([string]$target.state_path) -ne $stateFull -or
        [string]$target.expected_version -ne $ExpectedVersion -or
        [int]$target.backend_pid -ne $BackendPid -or
        [bool]$target.restart -ne [bool]$Restart -or
        [System.IO.Path]::GetFullPath([string]$target.helper_path) -ne [System.IO.Path]::GetFullPath($PSCommandPath) -or
        [string]$target.helper_sha256 -ne (Get-Sha256 -Path $PSCommandPath)) {
        throw "El ticket no autoriza estos argumentos ni este helper."
    }

    $claimedTicket = $ticketFull + ".consumed"
    if (Test-Path -LiteralPath $claimedTicket) {
        throw "El ticket de autorización ya fue consumido."
    }
    Move-Item -LiteralPath $ticketFull -Destination $claimedTicket
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

# This check is deliberately outside the effect try/catch. An unauthorized
# direct invocation must not write an error state, delete the bundle, or stage
# files before it is rejected.
Consume-AuthorizationTicket

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
