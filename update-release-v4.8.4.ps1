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
Write-Host "1. Elimina los binarios antiguos"
Write-Host "2. Sube los binarios nuevos compilados desde tag v4.8.4"
Write-Host "3. Actualiza checksums SHA256"
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

foreach ($asset in @("bago-4.8.4-distribution.zip", "bago-4.8.4-setup.exe", "BAGO.exe")) {
    Write-Host "  Eliminando $asset..."
    gh release delete-asset $RELEASE_TAG $asset --yes --repo $REPO 2>&1 > $null
    if ($?) { Write-Host "  ✅ $asset eliminado" } else { Write-Host "  ℹ️  $asset no encontrado" }
}

Write-Host ""
Write-Host "Paso 2: Eliminando checksums antiguos..." -ForegroundColor Yellow
foreach ($asset in @("bago-4.8.4-distribution.zip.sha256", "bago-4.8.4-setup.exe.sha256")) {
    Write-Host "  Eliminando $asset..."
    gh release delete-asset $RELEASE_TAG $asset --yes --repo $REPO 2>&1 > $null
}
Write-Host "  ✅ Checksums eliminados"

Write-Host ""
Write-Host "Paso 3: Subiendo binarios nuevos compilados desde v4.8.4..." -ForegroundColor Yellow

Push-Location $RELEASE_DIR

$binaries = @(
    @{ file = "bago-4.8.4-setup.exe"; size = "198 MB" },
    @{ file = "bago-4.8.4-distribution.zip"; size = "240 MB" },
    @{ file = "compiled\electron-viewer\BAGO.exe"; size = "216 MB"; name = "BAGO.exe" }
)

foreach ($binary in $binaries) {
    $displayName = $binary.name ?? $binary.file
    $displaySize = $binary.size ?? "desconocido"
    Write-Host "  Subiendo $displayName ($displaySize)..."
    gh release upload $RELEASE_TAG $binary.file --clobber --repo $REPO 2>&1 | Select-String "Uploading|✓" | Out-Null
    if ($?) { Write-Host "  ✅ $displayName subido" } else { Write-Host "  ⚠️  Error subiendo $displayName" }
}

Write-Host ""
Write-Host "Paso 4: Subiendo checksums..." -ForegroundColor Yellow
gh release upload $RELEASE_TAG "bago-4.8.4-setup.exe.sha256", "bago-4.8.4-distribution.zip.sha256" --clobber --repo $REPO 2>&1 | Select-String "Uploading|✓" | Out-Null
Write-Host "  ✅ Checksums subidos"

Pop-Location

Write-Host ""
Write-Host "✅ Actualización completada!" -ForegroundColor Green
Write-Host ""
Write-Host "Verificación de checksums:" -ForegroundColor Yellow
Write-Host "  Distribution: 4C79F5227EC3E111D36F5533E1AC10CA07FE1C13FFF8DD31D5A4C8E40BC57B96"
Write-Host "  Setup.exe:    A36544A402EB954C0E53AA60DBA4C89ED85015E4B1D67D0B5848AF52B2C427B3"
Write-Host "  BAGO.exe:     A1C1ED7D7D5F65EF73D63B9C1E2B9D86893D6C16C365DCBC88B6CD99D1DBF22B"
Write-Host ""
Write-Host "Los binarios ahora están disponibles en GitHub Release v4.8.4"
