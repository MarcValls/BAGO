<#
.SYNOPSIS
  verify-copies.ps1 — Detector de divergencia multi-copia para BAGO.

.DESCRIPTION
  Compara hashes SHA-256 de archivos clave entre las copias conocidas de BAGO
  (BAG4.8, Program Files, AppData\Local\BAGO) y reporta qué copia está desfasada.

  Útil para detectar el bug recurrente del 'º' en PowerShell 5.1 que hace que
  los edits aterricen en una copia distinta a la que el launcher ejecuta.

.USAGE
  powershell -File verify-copies.ps1
  powershell -File verify-copies.ps1 -Json   # salida JSON

.EXITCODE
  0 = sin divergencia
  1 = divergencia detectada
#>
param(
  [switch]$Json
)

$ErrorActionPreference = 'Stop'

# ── Copias conocidas ─────────────────────────────────────────────────────────
$Copies = @{
  'BAG4.8'      = 'C:\Users\AMTEC_Terminal_1º\BAG4.8'
  'ProgramFiles' = 'C:\Program Files\BAGO'
  'AppData'     = 'C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO'
}

# ── Archivos clave a comparar (relativos a cada raíz BAGO) ───────────────────
$KeyFiles = @(
  '.bago\api\bridge.py'
  '.bago\api\api_dispatch.py'
  '.bago\api\api_auth.py'
  '.bago\api\api_serializers.py'
  '.bago\api\request_context.py'
  '.bago\api\handlers_chat.py'
  '.bago\api\handlers_router.py'
  '.bago\api\handlers_routes.py'
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

  $Results += [PSCustomObject]@{
    File       = $file
    Divergent  = $isDivergent
    BAG48      = $hashes['BAG4.8']
    ProgFiles  = $hashes['ProgramFiles']
    AppData    = $hashes['AppData']
  }
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
      if ($_.BAG48)     { Write-Host "    BAG4.8      : $($_.BAG48.Substring(0,12))..." } else { Write-Host "    BAG4.8      : (no existe)" }
      if ($_.ProgFiles) { Write-Host "    ProgramFiles: $($_.ProgFiles.Substring(0,12))..." } else { Write-Host "    ProgramFiles: (no existe)" }
      if ($_.AppData)   { Write-Host "    AppData    : $($_.AppData.Substring(0,12))..." } else { Write-Host "    AppData    : (no existe)" }
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