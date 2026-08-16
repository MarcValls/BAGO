# bago-launcher.ps1
# Arranca BAGO (backend + electron), y cuando el usuario cierra la ventana
# de Electron el backend se detiene automáticamente via el hook de main.cjs.
#
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bago-launcher.ps1

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$Run  = Join-Path $Root ".run"
$DevPs1 = Join-Path $PSScriptRoot "dev.ps1"

New-Item -ItemType Directory -Path $Run -Force | Out-Null

function Log($msg) { Write-Host "[bago] $msg" -ForegroundColor Cyan }
function Err($msg) { Write-Host "[bago] $msg" -ForegroundColor Red }

# ── 1. Arrancar backend ───────────────────────────────────────────────────────
Log "Arrancando backend..."
& $DevPs1 start
if ($LASTEXITCODE -ne 0) {
    Err "El backend no se pudo arrancar. Revisa .run\backend.err.log"
    Read-Host "Pulsa Enter para cerrar"
    exit 1
}

# ── 2. Arrancar Electron y esperar a que el usuario cierre la ventana ─────────
$electronCandidates = @(
    (Join-Path $Root "electron-viewer\node_modules\electron\dist\electron.exe"),
    (Join-Path $Root "node_modules\electron\dist\electron.exe")
)
$electronBin = $electronCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $electronBin) {
    Err "Electron no está instalado. Ejecuta 'npm ci' desde la raíz del repo."
    & $DevPs1 stop
    Read-Host "Pulsa Enter para cerrar"
    exit 1
}

Log "Abriendo BAGO..."
# Ejecutamos Electron de forma SINCRÓNICA: el script espera hasta que el usuario
# cierra la ventana. Cuando salga, el hook before-quit de main.cjs llama a stop.
$proc = Start-Process -FilePath $electronBin `
    -ArgumentList "." `
    -WorkingDirectory (Join-Path $Root "electron-viewer") `
    -PassThru -Wait

Log "Ventana cerrada. BAGO detenido."
exit 0
