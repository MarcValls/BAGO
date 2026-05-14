#!/usr/bin/env pwsh
# bago.ps1 — BAGO Launcher para Windows
# Uso: BAGO [comando] [args]
#   BAGO launch [modelo]     ← lanza modelo (como ollama launch)
#   BAGO install [modelo]    ← instala modelo o herramienta
#   BAGO status              ← estado de BAGO
#   BAGO sync [--to-usb|--from-usb]  ← sincroniza con pendrive
#   BAGO repo init           ← crea repo Git para progresos
#   BAGO contribute          ← prepara informe de aprendizaje

$ErrorActionPreference = "Stop"

# === Detección de fuente de verdad ===
$exeDir = Split-Path -Parent $PSScriptRoot
$usbBago = Join-Path $exeDir ".bago"
$pcBago = Join-Path $env:USERPROFILE "BAGO\.bago"
$pcDocs = Join-Path $env:USERPROFILE "Documents\BAGO\.bago"

$script:SOURCE = $null
$script:PRIMARY = $null
$script:SECONDARY = $null

function Detect-Source {
    $usbExists = Test-Path $usbBago -PathType Container
    $pcExists = Test-Path $pcBago -PathType Container
    $docsExists = Test-Path $pcDocs -PathType Container

    $pcPath = if ($pcExists) { $pcBago } elseif ($docsExists) { $pcDocs } else { $null }

    $isRemovable = $false
    try {
        $drive = (Split-Path -Qualifier $exeDir).TrimEnd(":")
        if ($drive) {
            $driveInfo = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$drive`:" -ErrorAction SilentlyContinue
            $isRemovable = ($driveInfo.DriveType -eq 2)
        }
    } catch {}

    if ($usbExists -and $pcPath) {
        $script:SOURCE = "both"
        $script:PRIMARY = $pcPath
        $script:SECONDARY = $usbBago
        Write-Host "Fuente de verdad: $pcPath (PC). USB como backup: $usbBago" -ForegroundColor Green
    } elseif ($usbExists -and $isRemovable) {
        $script:SOURCE = "usb"
        $script:PRIMARY = $usbBago
        Write-Host "Fuente de verdad: $usbBago (PENDRIVE)" -ForegroundColor Cyan
    } elseif ($usbExists) {
        $script:SOURCE = "usb"
        $script:PRIMARY = $usbBago
        Write-Host "Fuente de verdad: $usbBago (DIRECTORIO LOCAL)" -ForegroundColor Cyan
    } elseif ($pcPath) {
        $script:SOURCE = "pc"
        $script:PRIMARY = $pcPath
        Write-Host "Fuente de verdad: $pcPath (PC INSTALADO)" -ForegroundColor Green
    } else {
        $script:SOURCE = "none"
        Write-Host "BAGO no detectado. Ejecuta: BAGO install" -ForegroundColor Red
        exit 1
    }
}

function Show-Status {
    Detect-Source
    Write-Host ""
    Write-Host "  BAGO Status" -ForegroundColor White
    Write-Host "  " + ("-" * 46) -ForegroundColor DarkGray
    Write-Host "  Modo:       $($script:SOURCE)" -ForegroundColor White
    Write-Host "  Primaria:   $($script:PRIMARY)" -ForegroundColor Green
    if ($script:SECONDARY) {
        Write-Host "  Secundaria: $($script:SECONDARY)" -ForegroundColor Cyan
    }

    # Modelos
    $providersFile = Join-Path $script:PRIMARY "..\state\model_providers.json"
    if (Test-Path $providersFile) {
        $providers = Get-Content $providersFile | ConvertFrom-Json
        $localModels = $providers.providers."ollama-local".models.PSObject.Properties.Name -join ", "
        $cloudModels = $providers.providers.copilot.models.PSObject.Properties.Name -join ", "
        Write-Host "  Locales:    $localModels" -ForegroundColor Yellow
        Write-Host "  Cloud:      $cloudModels" -ForegroundColor Yellow
    }

    Write-Host ""
}

function Launch-Model {
    param([string]$model = "qwen25-coder")
    Detect-Source
    $providersFile = Join-Path $script:PRIMARY "..\state\model_providers.json"
    $providers = Get-Content $providersFile | ConvertFrom-Json -ErrorAction SilentlyContinue

    # Buscar modelo en providers
    $found = $null
    foreach ($provName in $providers.providers.PSObject.Properties.Name) {
        $prov = $providers.providers.$provName
        if ($prov.models.PSObject.Properties.Name -contains $model) {
            $found = @{ Provider = $provName; Model = $model; WireName = $prov.models.$model.wire_name }
            break
        }
    }

    if (-not $found) {
        Write-Host "Modelo '$model' no encontrado. Modelos disponibles:" -ForegroundColor Red
        foreach ($provName in $providers.providers.PSObject.Properties.Name) {
            Write-Host "  $provName`: $($providers.providers.$provName.models.PSObject.Properties.Name -join ', ')" -ForegroundColor Yellow
        }
        exit 1
    }

    Write-Host "Lanzando: $($found.Model) via $($found.Provider)" -ForegroundColor Green

    switch ($found.Provider) {
        "ollama-local" {
            $tag = $found.WireName
            Write-Host "  ollama run $tag" -ForegroundColor DarkGray
            ollama run $tag
        }
        "codex" {
            Write-Host "  codex --model $($found.Model)" -ForegroundColor DarkGray
            codex --model $($found.Model)
        }
        "copilot" {
            Write-Host "  gh copilot suggest ..." -ForegroundColor DarkGray
            gh copilot --version
        }
        default {
            Write-Host "Provider '$($found.Provider)' no implementado aún." -ForegroundColor Yellow
        }
    }
}

function Install-Component {
    param([string]$component)
    Detect-Source
    Write-Host "Instalando: $component" -ForegroundColor Green
    switch ($component) {
        "qwen25-coder" { ollama pull qwen2.5-coder:7b }
        "llama32" { ollama pull llama3.2:latest }
        "codex" { Write-Host "Descarga desde: https://github.com/openai/codex" -ForegroundColor Cyan }
        "copilot" { gh extension install github/gh-copilot }
        "BAGO_H.1" { Write-Host "BAGO_H.1 no disponible aún. Coming soon." -ForegroundColor Yellow }
        default { Write-Host "Componente desconocido: $component" -ForegroundColor Red }
    }
}

function Sync-USB {
    param([string]$direction = "auto")
    Detect-Source
    if (-not $script:SECONDARY) {
        Write-Host "No se detectó USB. Inserta pendrive con BAGO." -ForegroundColor Red
        exit 1
    }
    $knowledgeSrc = Join-Path $script:PRIMARY "knowledge"
    $knowledgeDst = Join-Path $script:SECONDARY "knowledge"
    $stateSrc = Join-Path $script:PRIMARY "state"
    $stateDst = Join-Path $script:SECONDARY "state"

    if ($direction -eq "to-usb" -or $direction -eq "auto") {
        Write-Host "Sync PC → USB..." -ForegroundColor Cyan
        robocopy $knowledgeSrc $knowledgeDst /MIR /XD .git /NJH /NJS /NP
        robocopy $stateSrc $stateDst /MIR /XD .git /NJH /NJS /NP
    }
    if ($direction -eq "from-usb" -or $direction -eq "auto") {
        Write-Host "Sync USB → PC..." -ForegroundColor Cyan
        robocopy $knowledgeDst $knowledgeSrc /MIR /XD .git /NJH /NJS /NP
        robocopy $stateDst $stateSrc /MIR /XD .git /NJH /NJS /NP
    }
    Write-Host "Sincronización completa." -ForegroundColor Green
}

# === Main ===
$command = $args[0]
$rest = $args[1..($args.Length-1)]

switch ($command) {
    "status" { Show-Status }
    "launch" { Launch-Model -model (if ($rest[0]) { $rest[0] } else { "qwen25-coder" }) }
    "install" { Install-Component -component (if ($rest[0]) { $rest[0] } else { "qwen25-coder" }) }
    "sync" { Sync-USB -direction (if ($rest[0]) { $rest[0] } else { "auto" }) }
    "locate" { Detect-Source }
    default {
        Write-Host @"
BAGO Launcher v2026.05

Uso: BAGO <comando> [args]

Comandos:
  BAGO status              → Estado de BAGO y fuente de verdad
  BAGO launch [modelo]     → Lanza modelo (default: qwen25-coder)
  BAGO install [modelo]    → Instala modelo o herramienta
  BAGO sync [--to-usb|--from-usb] → Sincroniza con pendrive
  BAGO locate              → Detecta fuente de verdad

Ejemplos:
  BAGO launch codex
  BAGO launch gpt-5.5
  BAGO install qwen25-coder
  BAGO sync --to-usb
"@ -ForegroundColor White
    }
}
