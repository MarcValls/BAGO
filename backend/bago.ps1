#!/usr/bin/env pwsh
# BAGO global launcher — despacha por sub-comando:
#   bago              → instalación de trabajo (%BAGO_USER_ROOT% o perfil local)
#   bago des          → plataforma de desarrollo (BAGO source)
#   bago ign          → plataforma de lanzamiento (BAGO install + root de usuario)
#   bago sup <verb>   → supervisor always-on (start|stop|status|attach)
# Sin sub-comando = "bago" (instalación de trabajo) para retro-compatibilidad.
$ErrorActionPreference = 'Stop'
$userBago  = $null
[string]$userProfileRoot = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::UserProfile)
if ([string]::IsNullOrWhiteSpace($userProfileRoot)) { $userProfileRoot = [System.IO.Path]::GetTempPath() }
$legacyBago = Join-Path $userProfileRoot '.bago'
$srcBago   = Join-Path $userProfileRoot 'BAGO'

function Get-DefaultUserRoot {
    [string]$override = $env:BAGO_USER_ROOT
    if (-not [string]::IsNullOrWhiteSpace($override)) { return [System.IO.Path]::GetFullPath($override) }
    [string]$legacyOverride = $env:BAGO_LEGACY_USER_ROOT
    if (-not [string]::IsNullOrWhiteSpace($legacyOverride)) { return [System.IO.Path]::GetFullPath($legacyOverride) }
    if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA 'BAGO') }
    [string]$localAppData = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::LocalApplicationData)
    if (-not [string]::IsNullOrWhiteSpace($localAppData)) { return (Join-Path $localAppData 'BAGO') }
    [string]$userProfile = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::UserProfile)
    if (-not [string]::IsNullOrWhiteSpace($userProfile)) { return (Join-Path $userProfile 'AppData\Local\BAGO') }
    return (Join-Path ([System.IO.Path]::GetTempPath()) 'BAGO')
}

function Get-DefaultInstallDir {
    [string]$override = $env:BAGO_INSTALL_DIR
    if (-not [string]::IsNullOrWhiteSpace($override)) { return [System.IO.Path]::GetFullPath($override) }
    [string]$programFilesRoot = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::ProgramFiles)
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = $env:ProgramFiles }
    if ([string]::IsNullOrWhiteSpace($programFilesRoot)) { $programFilesRoot = [System.IO.Path]::GetTempPath() }
    return (Join-Path $programFilesRoot 'BAGO')
}

$userBago = Get-DefaultUserRoot
$instBago  = Get-DefaultInstallDir
$activeBago = $instBago
$supScript = Join-Path $srcBago 'scripts\bago_supervisor.py'

function Get-LauncherVersion {
    $selfRoot = Split-Path -Parent $PSCommandPath
    $versionFile = Join-Path $selfRoot 'release_version.txt'
    if (Test-Path $versionFile) {
        return ((Get-Content -LiteralPath $versionFile -Raw).Trim())
    }
    return 'dev'
}

function Get-SelectedRolePath([string]$role, [string]$fallback) {
    $selectionFile = @(
        (Join-Path $userBago 'install_selection.json'),
        (Join-Path $legacyBago 'install_selection.json')
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $selectionFile) { return $fallback }
    try {
        $selection = Get-Content -LiteralPath $selectionFile -Raw | ConvertFrom-Json
        $entry = $selection.roles.$role
        if ($entry -and $entry.path -and (Test-Path $entry.path)) {
            return [string]$entry.path
        }
    } catch {
        return $fallback
    }
    return $fallback
}

function Resolve-PreferredDevRoot {
    $selectedDev = Get-SelectedRolePath 'dev' ''
    if ($selectedDev) { return $selectedDev }
    $repoDev = Join-Path $env:USERPROFILE 'bago_fw'
    if (Test-Path $repoDev) { return $repoDev }
    $legacyDev = Join-Path $env:USERPROFILE 'BAGO'
    if (Test-Path $legacyDev) { return $legacyDev }
    return $repoDev
}

$activeBago = Get-SelectedRolePath 'active' $activeBago
$srcBago    = Resolve-PreferredDevRoot
$instBago   = Get-SelectedRolePath 'launch' $instBago
$supScript  = Join-Path $srcBago 'scripts\bago_supervisor.py'

function Resolve-Target([string]$mode) {
    switch ($mode) {
        'work' { return @{ cli = (Join-Path $activeBago 'bago_core\cli.py'); mode = 'work'; home = $userBago } }
        'dev'  { return @{ cli = (Join-Path $srcBago  'bago_core\cli.py'); mode = 'dev';  home = $srcBago  } }
        'ign'  { return @{ cli = (Join-Path $instBago 'bago_core\cli.py'); mode = 'ign';  home = $instBago } }
        default { Write-Error "bago: modo desconocido '$mode'"; exit 1 }
    }
}

function Get-ArgsTail([object[]]$values, [int]$start) {
    if (-not $values -or $values.Count -le $start) { return @() }
    return $values[$start..($values.Count - 1)]
}

function Invoke-ControlCommand([object[]]$argv) {
    $selfRoot = Split-Path -Parent $PSCommandPath
    $candidates = @(
        (Join-Path $selfRoot 'bago_core\cli.py'),
        (Join-Path $srcBago 'bago_core\cli.py'),
        (Join-Path $instBago 'bago_core\cli.py'),
        (Join-Path $activeBago 'bago_core\cli.py')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            & python $candidate @($argv)
            exit $LASTEXITCODE
        }
    }
    Write-Error "bago: no se encontró cli.py para comando de control"
    exit 1
}

$mode = 'work'
$rest = @()
if ($args.Count -gt 0) {
    $first = ([string]$args[0]).ToLower()
    # `bago sup <verb>` se intercepta SIEMPRE antes del modo, sin importar
    # si vino solo o detrás de un `des`/`ign`. La razón: el supervisor vive
    # en un único lugar (el dev tree) y no debería respetar el modo.
    # Si 'sup' está en cualquier posición, dejamos que el caller decida.
    $supIdx = -1
    for ($i = 0; $i -lt $args.Count; $i++) {
        if ([string]$args[$i] -ieq 'sup') { $supIdx = $i; break }
    }
    if ($supIdx -ge 0) {
        if (-not (Test-Path $supScript)) {
            Write-Error "bago sup: no se encontró $supScript"
            exit 1
        }
        $supArgs = @()
        if ($supIdx + 1 -lt $args.Count) {
            $supArgs = $args[($supIdx + 1)..($args.Count - 1)]
        }
        # Usar pythonw.exe (sin consola) para evitar parpadeo de ventana.
        & pythonw $supScript @($supArgs) 2>$null
        exit $LASTEXITCODE
    }

    # `bago probe` se intercepta en cualquier posición (sólo, detrás de `des`/`ign`/`work`).
    # Igual que `sup`: el probe vive en el dev tree y no respeta el modo.
    $probeIdx = -1
    for ($i = 0; $i -lt $args.Count; $i++) {
        if ([string]$args[$i] -ieq 'probe') { $probeIdx = $i; break }
    }
    if ($probeIdx -ge 0) {
        $probeScript = Join-Path $srcBago 'scripts\probe.py'
        if (-not (Test-Path $probeScript)) {
            Write-Error "bago probe: no se encontró $probeScript"
            exit 1
        }
        $probeArgs = @()
        if ($probeIdx + 1 -lt $args.Count) {
            $probeArgs = $args[($probeIdx + 1)..($args.Count - 1)]
        }
        & python $probeScript @($probeArgs)
        exit $LASTEXITCODE
    }
    if ($first -eq 'des') {
        $mode = 'dev'; $rest = Get-ArgsTail $args 1
    } elseif ($first -eq 'dev') {
        $mode = 'dev'; $rest = Get-ArgsTail $args 1
    } elseif ($first -eq 'ign') {
        $mode = 'ign'; $rest = Get-ArgsTail $args 1
    } elseif ($first -eq 'work') {
        $mode = 'work'; $rest = Get-ArgsTail $args 1
    } elseif ($first -eq 'help' -or $first -eq '--help' -or $first -eq '-h') {
        $launcherVersion = Get-LauncherVersion
        @"
BAGO launcher ($launcherVersion)
  bago              Copia activa seleccionada [default]
  bago work         Igual que bago sin sub-comando
  bago dev/des      Copia de desarrollo seleccionada
  bago ign          Plataforma de lanzamiento seleccionada
  bago sup <verb>   Supervisor always-on (start|stop|status|attach)
  roles             $userBago\install_selection.json
  bago help         Muestra esta ayuda
"@
        exit 0
    } else {
        $rest = $args
    }
}

$controlArgs = @($rest)
if ($controlArgs.Count -gt 0) {
    $controlCmd = [string]$controlArgs[0]
    if ($controlCmd -ieq 'install-role' -or $controlCmd -ieq 'list-installs') {
        Invoke-ControlCommand $controlArgs
    }
}

$target = Resolve-Target $mode
if (-not (Test-Path $target.cli)) {
    Write-Error "bago ($mode): no se encontró $($target.cli)"
    exit 1
}
& python $target.cli @($rest)
exit $LASTEXITCODE
