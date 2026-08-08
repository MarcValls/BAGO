# Build BAGO Installer
# Este script debe ejecutarse cada vez que se actualiza BAGO.exe o backend

param(
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Write-Host "==============================================="
Write-Host "BAGO 4.8.2 Installer Builder"
Write-Host "==============================================="

# Step 1: Actualizar estructura compilada
if (-not $SkipCompile) {
    Write-Host "`n[1/2] Actualizando estructura compilada desde electron-viewer..."
    
    $compiledDir = "$scriptDir\compiled\backend"
    $compiledViewerDir = "$scriptDir\compiled\electron-viewer"
    
    # Copiar backend fresco
    if (Test-Path "$repoRoot\backend") {
        Write-Host "  Copiando backend..."
        Remove-Item $compiledDir -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $compiledDir -Force | Out-Null
        Copy-Item -Path "$repoRoot\backend\*" -Destination $compiledDir -Recurse -Force
    }
    
    # Copiar electron-viewer compilado
    if (Test-Path "$repoRoot\electron-viewer\dist\win-unpacked") {
        Write-Host "  Copiando electron-viewer compilado..."
        Remove-Item $compiledViewerDir -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $compiledViewerDir -Force | Out-Null
        Copy-Item -Path "$repoRoot\electron-viewer\dist\win-unpacked\*" -Destination $compiledViewerDir -Recurse -Force
        
        # Copiar icono
        if (Test-Path "$repoRoot\electron-viewer\bago.ico") {
            Copy-Item -Path "$repoRoot\electron-viewer\bago.ico" -Destination $compiledViewerDir -Force
        }
    }
    
    # Verificar BAGO.exe
    if (-not (Test-Path "$compiledViewerDir\BAGO.exe")) {
        Write-Host "✗ ERROR: BAGO.exe no encontrado en electron-viewer\dist\win-unpacked"
        Write-Host "  Ejecuta: cd electron-viewer && npm run dist"
        exit 1
    }
    
    Write-Host "  ✓ BAGO.exe listo"
}

# Step 2: Compilar NSIS
Write-Host "`n[2/2] Compilando NSIS..."

$makensis = $null
$nsisPaths = @(
    "C:\Program Files (x86)\NSIS\makensis.exe",
    "C:\Program Files\NSIS\makensis.exe"
)

foreach ($path in $nsisPaths) {
    if (Test-Path $path) {
        $makensis = $path
        break
    }
}

if (-not $makensis) {
    Write-Host "✗ ERROR: NSIS makensis.exe no encontrado"
    Write-Host ""
    Write-Host "Descarga e instala NSIS desde:"
    Write-Host "  https://nsis.sourceforge.io/Download"
    Write-Host ""
    Write-Host "O en PowerShell (si tienes chocolatey):"
    Write-Host "  choco install nsis -y"
    exit 1
}

Write-Host "  Usando: $makensis"
Write-Host "  Compilando: bago-installer-local.nsi"

# Ejecutar makensis
$nsiFile = "$scriptDir\bago-installer-local.nsi"
if (-not (Test-Path $nsiFile)) {
    Write-Host "✗ ERROR: $nsiFile no encontrado"
    exit 1
}

$output = & $makensis /V4 $nsiFile 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    $setupFile = "$scriptDir\bago-4.8.2-setup.exe"
    if (Test-Path $setupFile) {
        $size = [Math]::Round((Get-Item $setupFile).Length / 1MB, 2)
        Write-Host "  ✓ bago-4.8.2-setup.exe compilado exitosamente ($size MB)"
        
        # Calcular SHA256
        $sha256 = (Get-FileHash -Path $setupFile -Algorithm SHA256).Hash
        Set-Content -Path "$setupFile.sha256" -Value $sha256
        Write-Host "  ✓ SHA256: $sha256"
        
        Write-Host ""
        Write-Host "==============================================="
        Write-Host "✓ LISTO PARA DISTRIBUCIÓN"
        Write-Host "==============================================="
        Write-Host ""
        Write-Host "Archivo: $setupFile"
        Write-Host "Tamaño: $size MB"
        Write-Host "SHA256: $sha256"
    }
} else {
    Write-Host "✗ Error compilando NSIS (exit code $exitCode):"
    Write-Host $output
    exit 1
}
