#!/usr/bin/env pwsh
# make-portable.ps1 â€” Adapta BAGO a la letra de unidad actual y prepara para Mac/Linux
# Uso: powershell -ExecutionPolicy Bypass -File .\make-portable.ps1

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

$oldPaths = @("E:\bago_fw", "E:\bago_fw\\.bago")
$newPath = $scriptDir
$newRuntime = Join-Path $scriptDir ".bago"

Write-Host "[make-portable] Ruta detectada: $newPath" -ForegroundColor Cyan

# Helper: reemplazar rutas en un archivo de texto
function Update-TextFile($path, $old, $new) {
    if (-not (Test-Path $path)) { return }
    $content = Get-Content $path -Raw
    if ($content -match [regex]::Escape($old)) {
        $content = $content -replace [regex]::Escape($old), $new
        Set-Content $path $content -Encoding UTF8 -NoNewline
        Write-Host "  $(Split-Path $path -Leaf) actualizado" -ForegroundColor Green
    }
}

# 1. runtime_contract.json (raiz) â€” reemplazo textual para preservar escapes
Update-TextFile (Join-Path $scriptDir "runtime_contract.json") "E:\bago_fw" $newPath
Update-TextFile (Join-Path $scriptDir "runtime_contract.json") "E:\bago_fw\\.bago" $newRuntime

# 2. docs/runtime_contract.json (si existe)
Update-TextFile (Join-Path $scriptDir "docs\runtime_contract.json") "E:\bago_fw" $newPath
Update-TextFile (Join-Path $scriptDir "docs\runtime_contract.json") "C:\\Program Files\\BAGO" $newPath

# 3. .bago_portable
$portablePath = Join-Path $scriptDir ".bago\tools\.bago_portable"
if (Test-Path $portablePath) {
    $portable = Get-Content $portablePath -Raw | ConvertFrom-Json
    if ($portable.source -ne $newPath) {
        $portable.source = $newPath
        $portable | ConvertTo-Json | Set-Content $portablePath -Encoding UTF8
        Write-Host "  .bago_portable actualizado" -ForegroundColor Green
    }
}

# 4. dashboard_data.json (ruta dentro de meta)
$dashboardPath = Join-Path $scriptDir ".bago\dashboard_data.json"
if (Test-Path $dashboardPath) {
    Update-TextFile $dashboardPath "E:\bago_fw" $newPath
    Update-TextFile $dashboardPath "C:\\ProgramData\BAGO\user" (Join-Path $env:ProgramData "BAGO\user")
}

# 5. recent_projects.json
$recentPath = Join-Path $scriptDir ".bago\state\recent_projects.json"
if (Test-Path $recentPath) {
    Update-TextFile $recentPath "E:\bago_fw" $newPath
}

# 6. sync scripts (rellativizarlos)
$syncScripts = @("sync2.ps1","sync-to-programfiles.ps1")
foreach ($s in $syncScripts) {
    $p = Join-Path $scriptDir $s
    if (Test-Path $p) {
        $content = Get-Content $p -Raw
        $newContent = $content -replace '^\s*\$src\s*=\s*["\x27].*["\x27]\s*$', '$src = $PSScriptRoot' -replace '^\s*\$dst\s*=\s*["\x27]C:\\\\Program Files\\\\BAGO["\x27]\s*$', '$dst = Join-Path $env:ProgramFiles "BAGO"'
        if ($newContent -ne $content) {
            Set-Content $p $newContent -Encoding UTF8
            Write-Host "  $s relativizado" -ForegroundColor Green
        }
    }
}

# 7. Buscar cualquier otro archivo JSON o PS1 con E:\bago_fw y reemplazar
Get-ChildItem $scriptDir -Recurse -File | Where-Object {
    $_.Extension -in '.json','.ps1','.cmd','.bat','.py','.md'
} | ForEach-Object {
    Update-TextFile $_.FullName "E:\bago_fw" $newPath
}

Write-Host "[make-portable] Listo. BAGO ahora es portable en esta unidad." -ForegroundColor Green
Write-Host "  Para Mac/Linux, ejecuta: bash bago.sh <comando>" -ForegroundColor Cyan
