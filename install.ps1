# ─────────────────────────────────────────────────────────────
#  BAGO Installer — Windows (PowerShell)
#  Uso (PowerShell como Admin o usuario normal):
#    irm https://raw.githubusercontent.com/MarcValls/BAGO/main/install.ps1 | iex
#  O con directorio personalizado:
#    $env:BAGO_DIR="C:\BAGO"; irm https://raw.githubusercontent.com/MarcValls/BAGO/main/install.ps1 | iex
# ─────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$REPO       = "https://github.com/MarcValls/BAGO.git"
$InstallDir = if ($env:BAGO_DIR) { $env:BAGO_DIR } else { "$HOME\BAGO" }

function Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function Err($msg)  { Write-Host "  [XX] $msg" -ForegroundColor Red; exit 1 }
function Info($msg) { Write-Host "       $msg" -ForegroundColor Cyan }

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor White
Write-Host "  BAGO Framework — Instalador v3.4.2" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor White
Write-Host ""

# ── Requisitos ────────────────────────────────────────────────
Info "Comprobando requisitos..."
if (-not (Get-Command python3 -ErrorAction SilentlyContinue) -and
    -not (Get-Command python  -ErrorAction SilentlyContinue)) {
  Err "Python 3.9+ requerido. Descárgalo en https://python.org"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Err "Git requerido. Descárgalo en https://git-scm.com"
}
$pyCmd = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
Ok "Python: $(& $pyCmd --version)"
Ok "Git: $(git --version)"

# ── Clonar / actualizar ───────────────────────────────────────
if (Test-Path "$InstallDir\.git") {
  Info "Actualizando repo existente en $InstallDir..."
  git -C "$InstallDir" pull --quiet
  Ok "Repo actualizado"
} else {
  Info "Clonando en $InstallDir..."
  git clone --quiet $REPO "$InstallDir"
  Ok "Repo clonado"
}

# ── Dependencias Python ───────────────────────────────────────
Info "Instalando dependencias Python..."
& $pyCmd -m pip install --quiet litellm rich prompt_toolkit 2>$null
Ok "Dependencias instaladas"

# ── global_state.json ─────────────────────────────────────────
$tmpl  = "$InstallDir\.bago\templates\global_state.clean.json"
$state = "$InstallDir\.bago\state\global_state.json"
if (-not (Test-Path $state) -and (Test-Path $tmpl)) {
  & $pyCmd "$InstallDir\.bago\tools\bootstrap_state.py" "$InstallDir"
  Ok "global_state.json creado"
}

# ── Función bago en perfil PowerShell ────────────────────────
$profilePath = $PROFILE
if (-not (Test-Path $profilePath)) {
  New-Item -ItemType File -Path $profilePath -Force | Out-Null
}
$funcLine = "function bago { & $pyCmd `"$InstallDir\bago`" @args }"
$content  = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
if ($content -match "function bago") {
  $content = $content -replace "function bago \{[^\}]*\}", $funcLine
  Set-Content $profilePath $content
  Ok "Función bago actualizada en $profilePath"
} else {
  Add-Content $profilePath "`n# BAGO Framework`n$funcLine"
  Ok "Función bago añadida en $profilePath"
}

# ── Validar instalación ───────────────────────────────────────
Info "Validando instalación..."
& $pyCmd "$InstallDir\bago" validate
if ($LASTEXITCODE -eq 0) {
  Ok "bago validate → OK"
} else {
  Err "bago validate → KO. Instalación abortada."
}

# ── Resumen ───────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor White
Write-Host "  ✅ BAGO instalado correctamente" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor White
Write-Host ""
Write-Host "  Directorio : $InstallDir" -ForegroundColor Cyan
Write-Host "  Perfil     : $profilePath" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Próximos pasos:" -ForegroundColor White
Write-Host "    1) Recarga el perfil:  . `$PROFILE" -ForegroundColor Yellow
Write-Host "    2) Lanza BAGO:         bago launch" -ForegroundColor Yellow
Write-Host "    3) Verifica estado:    bago health" -ForegroundColor Yellow
Write-Host ""

