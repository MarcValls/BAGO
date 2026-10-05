# Script para actualizar GitHub Release v4.8.4 con binarios compilados correctamente
# Uso: .\update-release-v4.8.4.ps1

$ErrorActionPreference = "Continue"

$RELEASE_TAG = "v4.8.4"
$REPO = "MarcValls/BAGO"
$RELEASE_DIR = "releases"

Write-Host "🔧 Script de Actualización de Release BAGO 4.8.4" -ForegroundColor Cyan
Write-Host "=================================================="
Write-Host ""
Write-Host "Este script:"
Write-Host "1. Elimina el instalador antiguo"
Write-Host "2. Sube solo el instalador compilado desde tag v4.8.4"
Write-Host "3. Actualiza el checksum SHA256 del instalador"
Write-Host ""
Write-Host "⚠️  Nota: Esta acción afectará a usuarios que descarguen de la release." -ForegroundColor Yellow
Write-Host ""

$response = Read-Host "¿Continuar? (s/n)"
if ($response -ne "s" -and $response -ne "S") {
    Write-Host "Abortado."
    exit 1
}

Write-Host ""
Write-Host "Paso 1: Eliminando binarios antiguos..." -ForegroundColor Yellow

foreach ($asset in @("bago-4.8.4-setup.exe")) {
    Write-Host "  Eliminando $asset..."
    gh release delete-asset $RELEASE_TAG $asset --yes --repo $REPO 2>&1 > $null
    if ($?) { Write-Host "  ✅ $asset eliminado" } else { Write-Host "  ℹ️  $asset no encontrado" }
}

Write-Host ""
Write-Host "Paso 2: Eliminando checksums antiguos..." -ForegroundColor Yellow
foreach ($asset in @("bago-4.8.4-setup.exe.sha256")) {
    Write-Host "  Eliminando $asset..."
    gh release delete-asset $RELEASE_TAG $asset --yes --repo $REPO 2>&1 > $null
}
Write-Host "  ✅ Checksums eliminados"

Write-Host ""
Write-Host "Paso 3: Subiendo el instalador nuevo compilado desde v4.8.4..." -ForegroundColor Yellow

Push-Location $RELEASE_DIR

$binaries = @(
    @{ file = "bago-4.8.4-setup.exe"; size = "278 MB" }
)

foreach ($binary in $binaries) {
    $displayName = $binary.name ?? $binary.file
    $displaySize = $binary.size ?? "desconocido"
    Write-Host "  Subiendo $displayName ($displaySize)..."
    gh release upload $RELEASE_TAG $binary.file --clobber --repo $REPO 2>&1 | Select-String "Uploading|✓" | Out-Null
    if ($?) { Write-Host "  ✅ $displayName subido" } else { Write-Host "  ⚠️  Error subiendo $displayName" }
}

Write-Host ""
Write-Host "Paso 4: Subiendo checksum..." -ForegroundColor Yellow
gh release upload $RELEASE_TAG "bago-4.8.4-setup.exe.sha256" --clobber --repo $REPO 2>&1 | Select-String "Uploading|✓" | Out-Null
Write-Host "  ✅ Checksums subidos"

Pop-Location

Write-Host ""
Write-Host "✅ Actualización completada!" -ForegroundColor Green
Write-Host ""
Write-Host "Verificación de checksums:" -ForegroundColor Yellow
Write-Host "  Setup.exe:    7533558D85B53BB7507C15BD1A7C6A575A069FA3CCEDBD016DCBF9DAA9C2A167"
Write-Host ""
Write-Host "El instalador ahora está disponible en GitHub Release v4.8.4"
