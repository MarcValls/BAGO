<#
.SYNOPSIS
  verify-copies.ps1 — Detector de divergencia multi-copia para BAGO.

.DESCRIPTION
  Compara hashes SHA-256 de archivos clave entre este runtime y otras copias
  detectadas o pasadas con -CopyRoot. Reporta qué copia está desfasada.

  Útil para detectar el bug recurrente del 'º' en PowerShell 5.1 que hace que
  los edits aterricen en una copia distinta a la que el launcher ejecuta.

.USAGE
  powershell -File verify-copies.ps1
  powershell -File verify-copies.ps1 -Json   # salida JSON
  powershell -File verify-copies.ps1 -CopyRoot C:\ruta\otra\copia

.EXITCODE
  0 = sin divergencia
  1 = divergencia detectada
#>
param(
  [switch]$Json,
  [string[]]$CopyRoot = @()
)

$ErrorActionPreference = 'Stop'

# ── Copias conocidas ─────────────────────────────────────────────────────────
$RuntimeRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Copies = [ordered]@{
  'Runtime' = $RuntimeRoot
}

$DefaultCandidates = @(
  (Join-Path $env:ProgramFiles 'BAGO'),
  (Join-Path $env:LOCALAPPDATA 'BAGO')
) | Where-Object { $_ -and (Test-Path $_) }

$i = 1
foreach ($copy in ($DefaultCandidates + $CopyRoot)) {
  try {
    $resolved = (Resolve-Path $copy -ErrorAction Stop).Path
  } catch {
    continue
  }
  if ($Copies.Values -contains $resolved) { continue }
  $Copies["Copy$i"] = $resolved
  $i++
}

# ── Archivos clave a comparar (relativos a cada raíz BAGO) ───────────────────
$KeyFiles = @(
  '.gabo\api\bridge.py'
  '.gabo\api\api_dispatch.py'
  '.gabo\api\api_auth.py'
  '.gabo\api\api_serializers.py'
  '.gabo\api\request_context.py'
  '.gabo\api\handlers_chat.py'
  '.gabo\api\handlers_router.py'
  '.gabo\api\handlers_routes.py'
  'ui-react\src\styles.css'
  'ui-react\src\api.js'
  'ui-react\src\App.jsx'
  'ui-react\src\components\ChatView.jsx'
  'bago_core\cli.py'
  'bago_core\launcher.py'
  'bago_core\version.py'
  'release_version.txt'
  'pyproject.toml'
  'package.json'
  'versions.json'
)

function Get-FileHashSafe {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return $null }
  try {
    return (Get-FileHash -Algorithm SHA256 -Path $Path -ErrorAction Stop).Hash
  } catch {
    return "ERROR"
  }
}

$Results = @()
$Divergence = 0

foreach ($file in $KeyFiles) {
  $hashes = @{}
  foreach ($name in $Copies.Keys) {
    $full = Join-Path $Copies[$name] $file
    $hashes[$name] = Get-FileHashSafe $full
  }

  # Solo comparar hashes de copias que tienen el archivo
  $present = $hashes.Values | Where-Object { $_ -ne $null }
  $uniqueHashes = ($present | Sort-Object -Unique)

  $isDivergent = $uniqueHashes.Count -gt 1

  if ($isDivergent) { $Divergence++ }

  $row = [ordered]@{
    File      = $file
    Divergent = $isDivergent
  }
  foreach ($name in $Copies.Keys) {
    $row[$name] = $hashes[$name]
  }
  $Results += [PSCustomObject]$row
}

if ($Json) {
  $Results | ConvertTo-Json -Depth 3
} else {
  Write-Host "`n=== BAGO verify-copies ===`n"
  Write-Host "Comparando $($KeyFiles.Count) archivos clave entre $($Copies.Count) copias.`n"

  $identical = ($Results | Where-Object { -not $_.Divergent }).Count
  $divergent = ($Results | Where-Object { $_.Divergent }).Count

  Write-Host "Identicos : $identical"
  Write-Host "Divergentes: $divergent`n"

  if ($divergent -gt 0) {
    Write-Host "--- ARCHIVOS DIVERGENTES ---"
    $Results | Where-Object { $_.Divergent } | ForEach-Object {
      Write-Host ""
      Write-Host "  $($_.File)"
      foreach ($name in $Copies.Keys) {
        $value = $_.$name
        if ($value) {
          Write-Host "    ${name}: $($value.Substring(0,12))..."
        } else {
          Write-Host "    ${name}: (no existe)"
        }
      }
    }
  }

  Write-Host ""
  if ($Divergence -eq 0) {
    Write-Host "ALL MATCH — sin divergencia detectada."
  } else {
    Write-Host "DIVERGENCIA DETECTADA — $Divergence archivo(s) difieren entre copias."
  }
}

exit $(if ($Divergence -gt 0) { 1 } else { 0 })
