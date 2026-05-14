#!/usr/bin/env pwsh
# bago.ps1 — BAGO Launcher para Windows
# Uso: BAGO <comando> [args]
#   BAGO launch [modelo]     ← lanza modelo o orquesta
#   BAGO install [modelo]    ← instala modelo o herramienta
#   BAGO status              ← estado de BAGO
#   BAGO sync [--to-usb|--from-usb]  ← sincroniza con pendrive
#   BAGO contribute          ← genera informe de aprendizaje
#   BAGO repo init           ← crea repo Git para progresos
#   BAGO repo sync           ← sube progresos

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

    $providersFile = Join-Path $script:PRIMARY "..\state\model_providers.json"
    if (Test-Path $providersFile) {
        $providers = Get-Content $providersFile | ConvertFrom-Json
        $localModels = $providers.providers."ollama-local".models.PSObject.Properties.Name -join ", "
        $cloudModels = $providers.providers.copilot.models.PSObject.Properties.Name -join ", "
        Write-Host "  Locales:    $localModels" -ForegroundColor Yellow
        Write-Host "  Cloud:      $cloudModels" -ForegroundColor Yellow
    }

    # Health check
    $healthScript = Join-Path $script:PRIMARY "..\tools\bago_health_check.py"
    if (Test-Path $healthScript) {
        Write-Host ""
        Write-Host "  Health Check:" -ForegroundColor White
        $health = python $healthScript 2>$null | Select-String "OK|NO" | Select-Object -First 4
        $health | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    }

    Write-Host ""
}

function Show-Models {
    Detect-Source
    $providersFile = Join-Path $script:PRIMARY "..\state\model_providers.json"
    if (-not (Test-Path $providersFile)) {
        Write-Host "No se encontró model_providers.json" -ForegroundColor Red
        return
    }
    $providers = Get-Content $providersFile | ConvertFrom-Json

    Write-Host ""
    Write-Host "  Modelos disponibles en BAGO" -ForegroundColor White
    Write-Host "  " + ("-" * 50) -ForegroundColor DarkGray

    foreach ($provName in $providers.providers.PSObject.Properties.Name) {
        $prov = $providers.providers.$provName
        $color = switch ($provName) {
            "ollama-local" { "Green" }
            "ollama-cloud" { "Cyan" }
            "copilot"      { "Yellow" }
            "codex"        { "Magenta" }
            default        { "White" }
        }
        Write-Host "  [$provName]" -ForegroundColor $color
        foreach ($mName in $prov.models.PSObject.Properties.Name) {
            $m = $prov.models.$mName
            $size = if ($m.size_mb) { " ($($m.size_mb)MB)" } else { "" }
            $cost = $m.cost
            $costColor = switch ($cost) {
                "free"         { "Green" }
                "included"     { "Yellow" }
                "subscription" { "Cyan" }
                "openai_credits" { "Magenta" }
                default        { "White" }
            }
            Write-Host "    $mName$size — $($m.best_for) " -NoNewline -ForegroundColor White
            Write-Host "[$cost]" -ForegroundColor $costColor
        }
    }
    Write-Host ""
    Write-Host "  Uso: BAGO launch <modelo>" -ForegroundColor DarkGray
    Write-Host "  Ej:  BAGO launch qwen25-mini   ← rápido, gratis, local" -ForegroundColor DarkGray
    Write-Host "       BAGO launch gpt-5.4-mini   ← rápido, créditos OpenAI" -ForegroundColor DarkGray
    Write-Host "       BAGO launch claude-sonnet-4.6 ← review, incluido en Copilot" -ForegroundColor DarkGray
    Write-Host ""
}

function Launch-Model {
    param([string]$model)
    if (-not $model) {
        Show-Models
        return
    }
    Detect-Source
    $providersFile = Join-Path $script:PRIMARY "..\state\model_providers.json"
    $providers = Get-Content $providersFile | ConvertFrom-Json -ErrorAction SilentlyContinue

    $found = $null
    foreach ($provName in $providers.providers.PSObject.Properties.Name) {
        $prov = $providers.providers.$provName
        if ($prov.models.PSObject.Properties.Name -contains $model) {
            $found = @{ Provider = $provName; Model = $model; WireName = $prov.models.$model.wire_name; BestFor = $prov.models.$model.best_for; Cost = $prov.models.$model.cost }
            break
        }
    }

    if (-not $found) {
        Write-Host "Modelo '$model' no encontrado." -ForegroundColor Red
        Show-Models
        exit 1
    }

    $costWarn = ""
    if ($found.Cost -eq "openai_credits") { $costWarn = " (consume créditos OpenAI)" }
    if ($found.Cost -eq "subscription") { $costWarn = " (requiere suscripción Ollama Cloud)" }
    Write-Host "Lanzando: $($found.Model) [$($found.BestFor)] via $($found.Provider)$costWarn" -ForegroundColor Green

    switch ($found.Provider) {
        "ollama-local" {
            $tag = $found.WireName
            Write-Host "  ollama run $tag" -ForegroundColor DarkGray
            ollama run $tag
        }
        "ollama-cloud" {
            $tag = $found.WireName
            Write-Host "  ollama run $tag (cloud)" -ForegroundColor DarkGray
            ollama run $tag
        }
        "codex" {
            Write-Host "  codex --model $($found.Model)" -ForegroundColor DarkGray
            codex --model $($found.Model)
        }
        "copilot" {
            Write-Host "  gh copilot suggest --model $($found.Model)" -ForegroundColor DarkGray
            gh copilot --version
        }
        default {
            Write-Host "Provider '$($found.Provider)' no implementado aún." -ForegroundColor Yellow
        }
    }
}

function Launch-Orchestrated {
    param([string]$task)
    if (-not $task) {
        $task = Read-Host "Describe tu tarea (ej: transponer partitura, revisar código, brainstorm ideas)"
    }
    Detect-Source
    $orchScript = Join-Path $script:PRIMARY "tools\bago_orchestrator.py"
    if (Test-Path $orchScript) {
        $result = python $orchScript "$task"
        Write-Host $result -ForegroundColor White
        # Extract model from output
        $model = ($result | Select-String "Modelo:\s+(\S+)").Matches.Groups[1].Value
        if ($model) {
            Write-Host ""
            $confirm = Read-Host "Lanzar $model? [S/n]"
            if ($confirm -ne "n" -and $confirm -ne "N") {
                Launch-Model -model $model
            }
        }
    } else {
        Write-Host "Orquestador no encontrado. Listando modelos disponibles..." -ForegroundColor Yellow
        Show-Models
    }
}

function Install-Component {
    param([string]$component)
    if (-not $component) {
        Write-Host ""
        Write-Host "  Componentes disponibles para instalar:" -ForegroundColor White
        Write-Host "  Modelos locales (Ollama):" -ForegroundColor Green
        Write-Host "    qwen25-coder  — 4.5GB, código Python" -ForegroundColor White
        Write-Host "    llama32       — 1.9GB, uso general" -ForegroundColor White
        Write-Host "    llama32-1b    — 1.2GB, clasificación" -ForegroundColor White
        Write-Host "    qwen25-mini   — 379MB, ultra-rápido" -ForegroundColor White
        Write-Host "  Herramientas:" -ForegroundColor Green
        Write-Host "    codex         — OpenAI Codex CLI" -ForegroundColor White
        Write-Host "    copilot       — GitHub Copilot CLI" -ForegroundColor White
        Write-Host "    all           — Todos los modelos locales" -ForegroundColor White
        Write-Host ""
        Write-Host "  Uso: BAGO install <componente>" -ForegroundColor DarkGray
        return
    }
    Detect-Source
    Write-Host "Instalando: $component" -ForegroundColor Green
    switch ($component) {
        "qwen25-coder" {
            Write-Host "Descargando qwen2.5-coder:7b (4.5GB)..." -ForegroundColor Cyan
            ollama pull qwen2.5-coder:7b
            Write-Host "✓ qwen25-coder instalado" -ForegroundColor Green
        }
        "llama32" {
            Write-Host "Descargando llama3.2:latest (1.9GB)..." -ForegroundColor Cyan
            ollama pull llama3.2:latest
            Write-Host "✓ llama32 instalado" -ForegroundColor Green
        }
        "llama32-1b" {
            Write-Host "Descargando llama3.2:1b (1.2GB)..." -ForegroundColor Cyan
            ollama pull llama3.2:1b
            Write-Host "✓ llama32-1b instalado" -ForegroundColor Green
        }
        "qwen25-mini" {
            Write-Host "Descargando qwen2.5:0.5b (379MB)..." -ForegroundColor Cyan
            ollama pull qwen2.5:0.5b
            Write-Host "✓ qwen25-mini instalado" -ForegroundColor Green
        }
        "all" {
            Write-Host "Descargando todos los modelos locales..." -ForegroundColor Cyan
            ollama pull qwen2.5-coder:7b
            ollama pull llama3.2:latest
            ollama pull llama3.2:1b
            ollama pull qwen2.5:0.5b
            Write-Host "✓ Todos los modelos locales instalados" -ForegroundColor Green
        }
        "codex" {
            Write-Host "Codex CLI se instala vía npm:" -ForegroundColor Cyan
            Write-Host "  npm install -g @openai/codex" -ForegroundColor White
            Write-Host "O descarga desde: https://github.com/openai/codex" -ForegroundColor White
        }
        "copilot" {
            Write-Host "Copilot CLI se instala vía gh:" -ForegroundColor Cyan
            Write-Host "  gh extension install github/gh-copilot" -ForegroundColor White
        }
        default {
            Write-Host "Componente desconocido: $component" -ForegroundColor Red
            Write-Host "Ejecuta 'BAGO install' para ver opciones" -ForegroundColor Yellow
        }
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

    # Asegurar que directorios existen en destino
    if (-not (Test-Path $knowledgeDst)) { New-Item -ItemType Directory -Force $knowledgeDst | Out-Null }
    if (-not (Test-Path $stateDst)) { New-Item -ItemType Directory -Force $stateDst | Out-Null }

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

function Contribute {
    Detect-Source
    $date = Get-Date -Format "yyyy-MM-dd"
    $contributionFile = Join-Path $script:PRIMARY "state\contribution_$date.md"

    Write-Host ""
    Write-Host "  BAGO Contribute — Informe de Aprendizaje" -ForegroundColor White
    Write-Host "  " + ("-" * 50) -ForegroundColor DarkGray

    $topic = Read-Host "¿Qué aprendiste hoy? (tema principal)"
    $model = Read-Host "¿Qué modelo usaste principalmente?"
    $improvement = Read-Host "¿Qué función de BAGO mejorarías?"

    $content = @"
# Informe de Aprendizaje BAGO — $date

## Tema
$topic

## Modelo utilizado
$model

## Mejora sugerida
$improvement

## Entorno
- Fuente de verdad: $($script:PRIMARY)
- Modo: $($script:SOURCE)

## Fecha
$date
"@

    $content | Set-Content $contributionFile -Encoding UTF8
    Write-Host ""
    Write-Host "  Informe generado: $contributionFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Para subir a GitHub:" -ForegroundColor Cyan
    Write-Host "  1. Ve a https://github.com/MarcValls/BAGO/issues/new" -ForegroundColor White
    Write-Host "  2. Pega el contenido del informe" -ForegroundColor White
    Write-Host "  3. Etiqueta: enhancement o documentation" -ForegroundColor White
    Write-Host ""
    Write-Host "  O usa: BAGO repo sync (si tienes repo configurado)" -ForegroundColor DarkGray
}

function Repo-Init {
    Detect-Source
    $repoName = Read-Host "Nombre del repo para tus progresos (default: bago-progress)"
    if (-not $repoName) { $repoName = "bago-progress" }

    Write-Host ""
    Write-Host "  Creando repo $repoName..." -ForegroundColor Cyan
    Write-Host "  Esto creará un repositorio Git local vinculado a GitHub." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Comandos a ejecutar manualmente:" -ForegroundColor Yellow
    Write-Host "  1. gh repo create $repoName --private --clone" -ForegroundColor White
    Write-Host "  2. cd $repoName" -ForegroundColor White
    Write-Host "  3. BAGO repo sync" -ForegroundColor White
}

function Repo-Sync {
    Detect-Source
    $progressDir = Join-Path $script:PRIMARY "..\..\bago-progress"
    if (-not (Test-Path $progressDir)) {
        Write-Host "Repo no encontrado. Ejecuta: BAGO repo init" -ForegroundColor Red
        exit 1
    }

    Write-Host "Sincronizando progresos..." -ForegroundColor Cyan
    # Copiar knowledge y state
    $destKnowledge = Join-Path $progressDir "knowledge"
    $destState = Join-Path $progressDir "state"
    robocopy (Join-Path $script:PRIMARY "knowledge") $destKnowledge /MIR /XD .git /NJH /NJS /NP
    robocopy (Join-Path $script:PRIMARY "state") $destState /MIR /XD .git /NJH /NJS /NP

    cd $progressDir
    git add .
    git commit -m "sync: progresos $(Get-Date -Format 'yyyy-MM-dd')" 2>$null
    git push origin main 2>$null
    Write-Host "✓ Progresos sincronizados con GitHub" -ForegroundColor Green
}

# === Main ===
$command = $args[0]
$rest = $args[1..($args.Length-1)]

switch ($command) {
    "status" { Show-Status }
    "launch" {
        if ($rest[0]) {
            Launch-Model -model $rest[0]
        } else {
            Launch-Orchestrated -task ($rest -join " ")
        }
    }
    "install" { Install-Component -component $rest[0] }
    "sync" { $dir = if ($rest[0]) { $rest[0] } else { "auto" }; Sync-USB -direction $dir }
    "contribute" { Contribute }
    "repo" {
        switch ($rest[0]) {
            "init" { Repo-Init }
            "sync" { Repo-Sync }
            default {
                Write-Host "Uso: BAGO repo init | BAGO repo sync" -ForegroundColor Yellow
            }
        }
    }
    default {
        Write-Host @"
BAGO Launcher v2026.05

Uso: BAGO <comando> [args]

Comandos:
  BAGO status              → Estado de BAGO y fuente de verdad
  BAGO launch              → Orquestador: pregunta tarea y selecciona modelo óptimo
  BAGO launch [modelo]     → Lanza modelo específico
  BAGO install             → Lista componentes disponibles
  BAGO install [modelo]    → Instala modelo o herramienta
  BAGO sync [--to-usb|--from-usb] → Sincroniza con pendrive
  BAGO contribute          → Genera informe de aprendizaje
  BAGO repo init           → Crea repo Git para progresos
  BAGO repo sync           → Sube progresos a GitHub

Ejemplos:
  BAGO launch
  BAGO launch qwen25-coder
  BAGO install qwen25-mini
  BAGO sync --to-usb
  BAGO contribute
"@ -ForegroundColor White
    }
}

