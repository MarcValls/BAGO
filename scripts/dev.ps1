# dev.ps1 - Arranca backend + build frontend + electron (PowerShell nativo).
#
# Uso:
#   .\scripts\dev.ps1 start
#   .\scripts\dev.ps1 stop
#   .\scripts\dev.ps1 status
#   .\scripts\dev.ps1 restart
#   .\scripts\dev.ps1 logs
#
# Mismo comportamiento que scripts/dev.sh pero para PowerShell.

$ErrorActionPreference = "Stop"

$Root    = (Resolve-Path "$PSScriptRoot\..").Path
$Run     = Join-Path $Root ".run"
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$ElectronDir = Join-Path $Root "electron-viewer"
$ApiUrl  = "http://127.0.0.1:8080"

New-Item -ItemType Directory -Path $Run -Force | Out-Null

function Log($msg)  { Write-Host "[dev] $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "[dev] $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "[dev] $msg" -ForegroundColor Red }

function Is-Running($pidfile) {
    if (-not (Test-Path $pidfile)) { return $false }
    $procId = Get-Content $pidfile -ErrorAction SilentlyContinue
    if (-not $procId) { return $false }
    try {
        $proc = Get-Process -Id $procId -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Wait-ForUrl($url, $timeout = 30) {
    for ($i = 0; $i -lt $timeout; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { return $true }
        } catch { }
        Start-Sleep 1
    }
    return $false
}

# --- Backend ------------------------------------------------
function Start-Backend {
    $pidfile = Join-Path $Run "backend.pid"
    $logfile = Join-Path $Run "backend.log"
    $errfile = Join-Path $Run "backend.err.log"
    if (Is-Running $pidfile) {
        Log "backend ya corre (pid $(Get-Content $pidfile))"
        return $true
    }
    Log "arrancando backend en $ApiUrl ..."
    try {
        $proc = Start-Process -FilePath "python" `
            -ArgumentList @("-u", "-m", "bago_core.launcher", "serve", "--host", "127.0.0.1", "--port", "8080") `
            -WorkingDirectory $Backend -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $logfile -RedirectStandardError $errfile
    } catch {
        Err "no se pudo arrancar backend: $($_.Exception.Message)"
        return $false
    }
    $proc.Id | Set-Content $pidfile
    if (Wait-ForUrl "$ApiUrl/health" 90) {
        Log "backend listo (pid $(Get-Content $pidfile))"
        return $true
    } else {
        Err "backend no respondio en 90s. Logs: $logfile, $errfile"
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
        Remove-Item $pidfile -ErrorAction SilentlyContinue
        return $false
    }
}

function Stop-Backend {
    $pidfile = Join-Path $Run "backend.pid"
    if (Is-Running $pidfile) {
        $procId = Get-Content $pidfile
        Log "matando backend (pid $procId)"
        try {
            taskkill /F /PID $procId /T 2>$null | Out-Null
        } catch { }
        Remove-Item $pidfile -ErrorAction SilentlyContinue
    } else {
        Log "backend no esta corriendo"
    }
}

# --- Frontend build ----------------------------------------
function Build-Frontend {
    $frontendPackage = Join-Path $Frontend "package.json"
    $packagedDist = Join-Path $Backend "ui-react\dist\index.html"
    if (-not (Test-Path $frontendPackage) -and (Test-Path $packagedDist)) {
        Log "frontend precompilado disponible en backend\ui-react\dist"
        return $true
    }
    if (-not (Test-Path $frontendPackage)) {
        Err "frontend fuente no existe y no hay dist precompilado: $Frontend"
        return $false
    }
    Log "compilando frontend..."
    $buildLog = Join-Path $Run "frontend-build.log"
    Push-Location $Root
    try {
        cmd /d /c "python backend\scripts\build_ui_dist.py > `"$buildLog`" 2>&1"
        $buildExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($buildExit -ne 0 -or -not (Test-Path (Join-Path $Backend "ui-react\dist\index.html"))) {
        Err "build del frontend fallo. Log: $buildLog"
        return $false
    }
    Log "frontend interactivo compilado y sincronizado a backend\ui-react\dist"
    return $true
}

function Ensure-PackagedViewer {
    $viewerRoot = $ElectronDir
    $electronBin = Join-Path $viewerRoot "node_modules\electron\dist\electron.exe"
    if (-not (Test-Path $electronBin)) {
        $electronBin = Join-Path $Root "node_modules\electron\dist\electron.exe"
        if (-not (Test-Path $electronBin)) {
            Err "electron no esta instalado ni en $viewerRoot ni en $Root"
            return $false
        }
    }
    Log "empaquetando electron viewer..."
    Push-Location $viewerRoot
    try {
        npm run dist
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($exitCode -ne 0) {
        Err "no se pudo empaquetar electron viewer"
        return $false
    }
    return $true
}

# --- Electron ----------------------------------------------
function Start-Electron {
    $pidfile = Join-Path $Run "electron.pid"
    $logfile = Join-Path $Run "electron.log"
    $errfile = Join-Path $Run "electron.err.log"
    $electronCandidates = @(
        (Join-Path $ElectronDir "node_modules\electron\dist\electron.exe"),
        (Join-Path $Root "node_modules\electron\dist\electron.exe")
    )
    $electronBin = $electronCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $electronBin) {
        Err "electron no esta instalado. Ejecuta npm ci desde la raiz"
        return $false
    }
    if (Is-Running $pidfile) {
        Log "electron ya corre (pid $(Get-Content $pidfile))"
        return $true
    }
    Log "arrancando electron..."
    try {
        $proc = Start-Process -FilePath $electronBin -ArgumentList "." `
            -WorkingDirectory $ElectronDir -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $logfile -RedirectStandardError $errfile
    } catch {
        Err "no se pudo arrancar electron: $($_.Exception.Message)"
        return $false
    }
    $proc.Id | Set-Content $pidfile
    Start-Sleep -Milliseconds 750
    if ($proc.HasExited) {
        Err "electron termino durante el arranque. Logs: $logfile, $errfile"
        Remove-Item $pidfile -ErrorAction SilentlyContinue
        return $false
    }
    Log "electron lanzado (pid $(Get-Content $pidfile))"
    return $true
}

function Stop-Electron {
    $pidfile = Join-Path $Run "electron.pid"
    if (Is-Running $pidfile) {
        $procId = Get-Content $pidfile
        Log "matando electron (pid $procId)"
        try {
            taskkill /F /PID $procId /T 2>$null | Out-Null
        } catch { }
        Remove-Item $pidfile -ErrorAction SilentlyContinue
    } else {
        Log "electron no esta corriendo"
    }
}

# --- Status -------------------------------------------------
function Show-Status {
    Log "estado:"
    $bp = Join-Path $Run "backend.pid"
    $ep = Join-Path $Run "electron.pid"
    if (Is-Running $bp) {
        Write-Host "  backend  : RUNNING (pid $(Get-Content $bp)) - $ApiUrl"
    } else {
        Write-Host "  backend  : stopped"
    }
    if (Is-Running $ep) {
        Write-Host "  electron : RUNNING (pid $(Get-Content $ep))"
    } else {
        Write-Host "  electron : stopped"
    }
    Write-Host "  logs     : $Run\*.log"
}

# --- Logs ---------------------------------------------------
function Show-Logs {
    $logs = Get-ChildItem "$Run\*.log" -ErrorAction SilentlyContinue
    if (-not $logs) {
        Warn "no hay logs aun"
        return
    }
    Get-Content $logs -Wait
}

# --- Main ---------------------------------------------------
$action = if ($args.Count -gt 0) { $args[0] } else { "start" }
switch ($action) {
    "start"   {
        if (-not (Build-Frontend)) { exit 1 }
        if (-not (Ensure-PackagedViewer)) { exit 1 }
        if (-not (Start-Backend)) { exit 1 }
        if (-not (Start-Electron)) { Stop-Backend; exit 1 }
        ""; Show-Status; ""; Log "logs: .\scripts\dev.ps1 logs  |  parar: .\scripts\dev.ps1 stop"
    }
    "stop"    { Stop-Electron; Stop-Backend; Log "todo detenido" }
    "restart" { & $PSCommandPath stop; Start-Sleep 2; & $PSCommandPath start }
    "status"  { Show-Status }
    "logs"    { Show-Logs }
    "build"   { if (-not (Build-Frontend)) { exit 1 } }
    "backend" { if (-not (Start-Backend)) { exit 1 } }
    "electron" { if (-not (Start-Electron)) { exit 1 } }
    default {
        Write-Host "uso: .\scripts\dev.ps1 {start|stop|restart|status|logs|build|backend|electron}" -ForegroundColor Yellow
        exit 1
    }
}
