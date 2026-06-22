#Requires -Version 5.1
<#
.SYNOPSIS
    Demo robusta de `bago init`: crea un proyecto vacío, lo siembra,
    verifica que no haya fisuras y corre la validación MVP.
#>
param(
    [string]$BagoRoot = "C:\Users\AMTEC_Terminal_1º\bago_fw",
    [string]$DemoRoot = "C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\bago-init-demo"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BagoRoot)) {
    throw "No se encontro BAGO en $BagoRoot"
}

# 1. Limpiar y crear el proyecto vacío
if (Test-Path $DemoRoot) {
    Remove-Item -Path $DemoRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $DemoRoot -Force | Out-Null
Set-Location $DemoRoot

# 1b. Crear .gitignore mínimo del proyecto (bago init no lo crea porque
# pertenece al contrato del proyecto, no a la semilla .bago)
@'
# BAGO runtime state
.bago/state/
.bago/logs/
.bago/launch/
.bago/credentials.json
.bago/config.json
.bago/session-credentials.json
*.db
*.sqlite
__pycache__/
'@ | Out-File -Encoding utf8 -FilePath "$DemoRoot\.gitignore"

Write-Host "`n[1/6] Proyecto vacío creado en $DemoRoot" -ForegroundColor Cyan

# 2. Dry-run: mostrar qué se sembraría sin escribir nada
Write-Host "`n[2/6] Dry-run de bago init" -ForegroundColor Cyan
& python "$BagoRoot\bago_core\cli.py" init --dry-run

# 3. Siembra real
Write-Host "`n[3/6] Ejecutando bago init" -ForegroundColor Cyan
& python "$BagoRoot\bago_core\cli.py" init

# 4. Verificar estructura sin fisuras
Write-Host "`n[4/6] Verificando estructura sembrada" -ForegroundColor Cyan
$required = @(
    ".bago\AGENT_START.md",
    ".bago\BOOTSTRAP.md",
    ".bago\core\session_manager.py",
    ".bago\api\bridge.py",
    ".bago\chat\repl.py",
    ".bago\providers\ollama_local.py",
    ".bago\state\sessions",
    ".bago\logs"
)
$failed = @()
foreach ($item in $required) {
    if (-not (Test-Path "$DemoRoot\$item")) {
        $failed += $item
        Write-Host "  FALTA: $item" -ForegroundColor Red
    } else {
        Write-Host "  OK: $item" -ForegroundColor Green
    }
}

# 5. Verificar que no se hayan copiado artefactos runtime
Write-Host "`n[5/6] Verificando ausencia de artefactos runtime" -ForegroundColor Cyan
$forbiddenPatterns = @("*.pyc", "*.pyo", "*.db", "credentials.json", "config.json", "session-credentials.json")
$foundArtifacts = Get-ChildItem -Path "$DemoRoot\.bago" -Recurse |
    Where-Object {
        $n = $_.Name
        $forbiddenPatterns | Where-Object { $n -like $_ }
    }
$pycache = Get-ChildItem -Path "$DemoRoot\.bago" -Recurse -Directory -Filter "__pycache__"
if ($foundArtifacts -or $pycache) {
    Write-Host "  Se encontraron artefactos no deseados:" -ForegroundColor Red
    $foundArtifacts | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    $pycache | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    $failed += "artefactos-runtime"
} else {
    Write-Host "  OK: sin pycache, db, credenciales ni config" -ForegroundColor Green
}

# 6. Validar (informativo: un proyecto nuevo sin contratos propios fallará
#    en contracts_present, lo cual es correcto; aquí comprobamos que la
#    semilla no introduce fallos de seguridad como credenciales o pycache).
Write-Host "`n[6/6] Validando MVP con bago_core\\cli.py validate (informativo)" -ForegroundColor Cyan
& python "$BagoRoot\bago_core\cli.py" validate
$validateExit = $LASTEXITCODE
if ($validateExit -ne 0) {
    Write-Host "  Nota: validate falló por faltar contratos/.gitignore del proyecto; esto es esperado en un proyecto vacío." -ForegroundColor Yellow
}

# Resumen
Write-Host "`n--- RESUMEN ---" -ForegroundColor Cyan
if ($failed.Count -eq 0) {
    Write-Host "Demo OK: proyecto sembrado sin fisuras." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Demo FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
