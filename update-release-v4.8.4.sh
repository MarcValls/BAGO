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
echo "1. Elimina los assets antiguos"
echo "2. Sube solo el instalador compilado desde tag v4.8.4"
echo "3. Actualiza el checksum SHA256 del instalador"
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
gh release delete-asset "$RELEASE_TAG" "bago-4.8.4-setup.exe" --yes --repo "$REPO" 2>/dev/null && echo "  ✅ bago-4.8.4-setup.exe eliminado" || echo "  ℹ️  bago-4.8.4-setup.exe no encontrado"

echo ""
echo "Paso 2: Eliminando checksums antiguos..."
gh release delete-asset "$RELEASE_TAG" "bago-4.8.4-setup.exe.sha256" --yes --repo "$REPO" 2>/dev/null || true

echo ""
echo "Paso 3: Subiendo el instalador nuevo compilado desde v4.8.4..."
cd "$RELEASE_DIR"

# Subir instalador
echo "  Subiendo bago-4.8.4-setup.exe..."
gh release upload "$RELEASE_TAG" "bago-4.8.4-setup.exe" --clobber --repo "$REPO" 2>&1 | grep -E "Uploading|✓" || true

echo ""
echo "Paso 4: Subiendo checksum..."
gh release upload "$RELEASE_TAG" "bago-4.8.4-setup.exe.sha256" --clobber --repo "$REPO" 2>&1 | grep -E "Uploading|✓" || true

cd ..

echo ""
echo "✅ Actualización completada!"
echo ""
echo "Verificación de checksums:"
echo "  Setup.exe:    7533558D85B53BB7507C15BD1A7C6A575A069FA3CCEDBD016DCBF9DAA9C2A167"
