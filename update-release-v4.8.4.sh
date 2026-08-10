#!/bin/bash
# Script para actualizar GitHub Release v4.8.4 con binarios compilados correctamente
# Uso: bash update-release-v4.8.4.sh

set -e

RELEASE_TAG="v4.8.4"
REPO="MarcValls/BAGO"
RELEASE_DIR="releases"

echo "🔧 Script de Actualización de Release BAGO 4.8.4"
echo "=================================================="
echo ""
echo "Este script:"
echo "1. Elimina los binarios antiguos"
echo "2. Sube los binarios nuevos compilados desde tag v4.8.4"
echo "3. Actualiza checksums SHA256"
echo ""
echo "⚠️  Nota: Esta acción afectará a usuarios que descarguen de la release."
echo ""
read -p "¿Continuar? (s/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Abortado."
    exit 1
fi

echo ""
echo "Paso 1: Eliminando binarios antiguos..."
gh release delete-asset "$RELEASE_TAG" "bago-4.8.4-distribution.zip" --yes --repo "$REPO" 2>/dev/null && echo "  ✅ bago-4.8.4-distribution.zip eliminado" || echo "  ℹ️  bago-4.8.4-distribution.zip no encontrado"
gh release delete-asset "$RELEASE_TAG" "bago-4.8.4-setup.exe" --yes --repo "$REPO" 2>/dev/null && echo "  ✅ bago-4.8.4-setup.exe eliminado" || echo "  ℹ️  bago-4.8.4-setup.exe no encontrado"
gh release delete-asset "$RELEASE_TAG" "BAGO.exe" --yes --repo "$REPO" 2>/dev/null && echo "  ✅ BAGO.exe eliminado" || echo "  ℹ️  BAGO.exe no encontrado"

echo ""
echo "Paso 2: Eliminando checksums antiguos..."
gh release delete-asset "$RELEASE_TAG" "bago-4.8.4-distribution.zip.sha256" --yes --repo "$REPO" 2>/dev/null && echo "  ✅ checksums eliminados" || echo "  ℹ️  checksums no encontrados"
gh release delete-asset "$RELEASE_TAG" "bago-4.8.4-setup.exe.sha256" --yes --repo "$REPO" 2>/dev/null || true

echo ""
echo "Paso 3: Subiendo binarios nuevos compilados desde v4.8.4..."
cd "$RELEASE_DIR"

# Subir binarios
echo "  Subiendo bago-4.8.4-setup.exe (198 MB)..."
gh release upload "$RELEASE_TAG" "bago-4.8.4-setup.exe" --clobber --repo "$REPO" 2>&1 | grep -E "Uploading|✓" || true

echo "  Subiendo bago-4.8.4-distribution.zip (240 MB)..."
gh release upload "$RELEASE_TAG" "bago-4.8.4-distribution.zip" --clobber --repo "$REPO" 2>&1 | grep -E "Uploading|✓" || true

echo "  Subiendo BAGO.exe (216 MB)..."
gh release upload "$RELEASE_TAG" "compiled/electron-viewer/BAGO.exe" --clobber --repo "$REPO" 2>&1 | grep -E "Uploading|✓" || true

echo ""
echo "Paso 4: Subiendo checksums..."
gh release upload "$RELEASE_TAG" "bago-4.8.4-setup.exe.sha256" "bago-4.8.4-distribution.zip.sha256" --clobber --repo "$REPO" 2>&1 | grep -E "Uploading|✓" || true

cd ..

echo ""
echo "✅ Actualización completada!"
echo ""
echo "Verificación de checksums:"
echo "  Distribution: 4C79F5227EC3E111D36F5533E1AC10CA07FE1C13FFF8DD31D5A4C8E40BC57B96"
echo "  Setup.exe:    A36544A402EB954C0E53AA60DBA4C89ED85015E4B1D67D0B5848AF52B2C427B3"
echo "  BAGO.exe:     A1C1ED7D7D5F65EF73D63B9C1E2B9D86893D6C16C365DCBC88B6CD99D1DBF22B"
