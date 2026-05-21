#!/usr/bin/env pwsh
# bago.ps1 — BAGO Launcher para Windows
# Uso: BAGO <comando> [args]
#
#   ── Chat / IA ────────────────────────────────
#   bago launch              → BAGO Chat REPL (auto-detecta provider)
#   bago chat                → alias de launch
#   bago copilot             → fuerza provider GitHub Copilot
#   bago codex / bago gpt    → fuerza provider Codex/OpenAI
#   bago claude              → fuerza provider Anthropic
#   bago ollama              → fuerza modelo local Ollama
#   bago menu                → menú curses de navegación
#
#   ── Framework ────────────────────────────────
#   bago status              → estado de BAGO
#   bago install [component] → instala componente o modelo
#   bago sync [--to-usb|--from-usb|knowledge] → sincroniza con pendrive o knowledge repo
#   bago knowledge [sync|pull|push|status] → sincroniza con bago-knowledge
#   bago dev refresh-engine [--with-knowledge|--without-knowledge] → reconstruye el motor limpio
#   bago inventory           → inventario de herramientas
#   bago pipeline <tarea>    → ejecuta pipeline multi-modelo
#
#   ── Proyectos ─────────────────────────────────
#   bago build / test / lint / run / deploy / clean
#   bago ideas               → genera ideas de evolución
#   bago repo init | sync    → gestión de repositorio Git

$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"

# === Detección de fuente de verdad ===
$exeDir = $PSScriptRoot
$usbBago = Join-Path $exeDir ".bago"
$pcBago = Join-Path $env:USERPROFILE "BAGO\.bago"
$pcDocs = Join-Path $env:USERPROFILE "Documents\BAGO\.bago"

$script:SOURCE = $null
$script:PRIMARY = $null
$script:SECONDARY = $null

function Detect-Source {
    # Buscar .bago en unidades removibles (USB real)
    $usbReal = $null
    try {
        $drives = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DriveType=2" | Select-Object -ExpandProperty DeviceID
        foreach ($d in $drives) {
            $cand = Join-Path ($d.TrimEnd(':') + ':\') '.bago'
            if (Test-Path $cand -PathType Container) { $usbReal = $cand; break }
        }
    } catch {}

    # Directorio del script (donde está bago.ps1, junto a .bago/)
    $exeDir = $PSScriptRoot
    $usbBago = Join-Path $exeDir '.bago'
    $pcBago = Join-Path $env:USERPROFILE 'BAGO\.bago'
    $pcDocs = Join-Path $env:USERPROFILE 'Documents\BAGO\.bago'

    $usbExists = if ($usbReal) { $true } else { Test-Path $usbBago -PathType Container }
    $usbPath = if ($usbReal) { $usbReal } else { $usbBago }

    $pcExists = Test-Path $pcBago -PathType Container
    $docsExists = Test-Path $pcDocs -PathType Container
    $pcPath = if ($pcExists) { $pcBago } elseif ($docsExists) { $pcDocs } else { $null }
    $installedRoot = Join-Path $env:ProgramFiles 'BAGO'
    $installedManifest = Join-Path $exeDir 'runtime_contract.json'
    $isInstalledRuntime = $false
    try {
        $exeResolved = [System.IO.Path]::GetFullPath($exeDir).TrimEnd('\')
        $installedResolved = [System.IO.Path]::GetFullPath($installedRoot).TrimEnd('\')
        $isInstalledRuntime = (Test-Path $installedManifest -PathType Leaf) -or $exeResolved.Equals($installedResolved, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {}

    $isRemovable = $false
    $runningFromUsb = $false
    try {
        $drive = (Split-Path -Qualifier $exeDir).TrimEnd(':')
        if ($drive) {
            $driveInfo = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='${drive}:'" -ErrorAction SilentlyContinue
            $isRemovable = ($driveInfo.DriveType -eq 2)
        }
        $scriptDrive = (Split-Path -Qualifier $exeDir).TrimEnd('\')
        $usbDrive = (Split-Path -Qualifier $usbPath).TrimEnd('\')
        if ($usbExists -and $scriptDrive -and $usbDrive) {
            $runningFromUsb = ($scriptDrive.ToUpperInvariant() -eq $usbDrive.ToUpperInvariant())
        }
    } catch {}

    if ($usbExists -and $isInstalledRuntime) {
        $script:SOURCE = 'installed'
        $script:PRIMARY = $usbBago
        if ($env:BAGO_ALLOW_DEV_SECONDARY -eq "1") {
            if ($pcPath -and ($pcPath.ToUpperInvariant() -ne $usbBago.ToUpperInvariant())) {
                $script:SECONDARY = $pcPath
            } elseif ($usbReal -and ($usbReal.ToUpperInvariant() -ne $usbBago.ToUpperInvariant())) {
                $script:SECONDARY = $usbReal
            }
        }
        Write-Host "Fuente de verdad: $usbBago (INSTALADO)" -ForegroundColor Green
    } elseif ($usbReal -and $pcPath) {
        if ($runningFromUsb) {
            $script:SOURCE = 'both'
            $script:PRIMARY = $usbPath
            $script:SECONDARY = $pcPath
            Write-Host "Fuente de verdad: $usbPath (USB primaria). PC: $pcPath" -ForegroundColor Cyan
        } else {
            $script:SOURCE = 'both'
            $script:PRIMARY = $pcPath
            $script:SECONDARY = $usbReal
            Write-Host "Fuente de verdad: $pcPath (PC). USB: $usbReal" -ForegroundColor Green
        }
    } elseif ($usbReal) {
        $script:SOURCE = 'usb'
        $script:PRIMARY = $usbReal
        Write-Host "Fuente de verdad: $usbReal (PENDRIVE)" -ForegroundColor Cyan
    } elseif ($usbExists -and $isRemovable) {
        $script:SOURCE = 'usb'
        $script:PRIMARY = $usbPath
        Write-Host "Fuente de verdad: $usbPath (PENDRIVE)" -ForegroundColor Cyan
    } elseif ($usbExists) {
        $script:SOURCE = 'usb'
        $script:PRIMARY = $usbPath
        if ($pcPath) {
            $script:SECONDARY = $pcPath
            Write-Host "Fuente de verdad: $usbPath (DIRECTORIO LOCAL). PC: $pcPath" -ForegroundColor Cyan
        } else {
            Write-Host "Fuente de verdad: $usbPath (DIRECTORIO LOCAL)" -ForegroundColor Cyan
        }
    } elseif ($pcPath) {
        $script:SOURCE = 'pc'
        $script:PRIMARY = $pcPath
        Write-Host "Fuente de verdad: $pcPath (PC INSTALADO)" -ForegroundColor Green
    } else {
        $script:SOURCE = 'none'
        Write-Host 'BAGO no detectado. Ejecuta: BAGO install' -ForegroundColor Red
        exit 1
    }

    if ($script:PRIMARY) {
        $portableUserHome = if ($env:ProgramData) {
            Join-Path $env:ProgramData 'BAGO\user'
        } else {
            Join-Path $script:PRIMARY 'user'
        }
        New-Item -ItemType Directory -Path $portableUserHome -Force | Out-Null
        $env:BAGO_USER_HOME = $portableUserHome
    }
}

function Find-Gh {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) { return $gh.Source }
    $known = @(
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe"),
        "C:\Program Files\GitHub CLI\gh.exe"
    )
    foreach ($p in $known) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Invoke-GhSilently {
    param([string]$prompt, [int]$timeoutSec = 25)
    $gh = Find-Gh
    if (-not $gh) { return @{ success = $false; output = ""; error = "gh no encontrado" } }
    $out = [System.IO.Path]::GetTempFileName()
    $err = [System.IO.Path]::GetTempFileName()
    $proc = Start-Process -FilePath $gh -ArgumentList 'copilot','--','-p',$prompt,'--silent','--allow-all-tools','--stream','off' -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -PassThru
    $exited = $proc.WaitForExit($timeoutSec * 1000)
    if (-not $exited) { $proc.Kill(); $proc.WaitForExit() }
    $stdout = Get-Content $out -Raw -ErrorAction SilentlyContinue
    $stderr = Get-Content $err -Raw -ErrorAction SilentlyContinue
    Remove-Item $out -ErrorAction SilentlyContinue
    Remove-Item $err -ErrorAction SilentlyContinue
    $success = ($proc.ExitCode -eq 0) -and ($stdout.Trim().Length -gt 0)
    return @{ success = $success; output = $stdout.Trim(); error = $stderr.Trim(); exitCode = $proc.ExitCode }
}

function Invoke-BagoPipeline {
    param([string]$task)
    Detect-Source
    Write-Host ""
    Write-Host "  [BAGO Pipeline] Orquestando en segundo plano..." -ForegroundColor Magenta
    Write-Host "  Tarea: $task" -ForegroundColor White
    Write-Host ""

    $pipelineScript = Join-Path $script:PRIMARY "tools\bago_pipeline.py"
    if (-not (Test-Path $pipelineScript)) {
        Write-Host "  ERROR: No se encuentra bago_pipeline.py" -ForegroundColor Red
        return
    }

    # Pre-router rapido para ajustar timeout segun tipo de tarea
    $taskType = "default"
    $execTimeout = 40
    $reviewTimeout = 30
    try {
        $routerOut = python -c "import sys; sys.path.insert(0, r'$($script:PRIMARY)\tools'); from bago_dynamic_router import dynamic_route; print(dynamic_route(r'$task')['task_type'])" 2>$null
        if ($routerOut) { $taskType = $routerOut.Trim() }
        switch ($taskType) {
            "content"      { $execTimeout = 20;  $reviewTimeout = 15 }
            "brainstorm"   { $execTimeout = 20;  $reviewTimeout = 15 }
            "music"        { $execTimeout = 90;  $reviewTimeout = 60 }
            "code"         { $execTimeout = 50;  $reviewTimeout = 35 }
            "debug"        { $execTimeout = 45;  $reviewTimeout = 30 }
            "quality"      { $execTimeout = 40;  $reviewTimeout = 30 }
            "architecture" { $execTimeout = 60;  $reviewTimeout = 45 }
            "coordination" { $execTimeout = 35;  $reviewTimeout = 25 }
            default        { $execTimeout = 40;  $reviewTimeout = 30 }
        }
    } catch {}
    $fallbackTimeout = 60
    $jobTimeout = $execTimeout + $reviewTimeout + $fallbackTimeout + 20
    Write-Host "  Tipo detectado: $taskType | Timeouts: exec=${execTimeout}s review=${reviewTimeout}s job=${jobTimeout}s" -ForegroundColor DarkGray
    Write-Host ""

    $outputFile = [System.IO.Path]::GetTempFileName()
    $job = Start-Job -ScriptBlock {
        param($script, $task, $output)
        & python "$script" "$task" --output "$output"
    } -ArgumentList $pipelineScript, $task, $outputFile
    $job | Wait-Job -Timeout $jobTimeout | Out-Null
    if ($job.State -eq 'Running') {
        Write-Host "  WARN Pipeline timeout (${jobTimeout}s). Matando job..." -ForegroundColor Yellow
        $job | Stop-Job
    }
    $job | Receive-Job | Out-Null
    Remove-Job $job -ErrorAction SilentlyContinue

    if (Test-Path $outputFile) {
        $result = Get-Content $outputFile -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json -ErrorAction SilentlyContinue
        Remove-Item $outputFile -ErrorAction SilentlyContinue
    } else {
        $result = $null
    }

    if ($result) {
        Write-Host "  [Fase 1/4] Router -> $($result.provider) | $($result.model) | confianza $($result.confidence)%" -ForegroundColor Cyan
        Write-Host "  [Fase 2/4] Ejecutor principal -> $($result.phases.executor.success)" -ForegroundColor Cyan
        Write-Host "  [Fase 3/4] Reviewer -> $($result.phases.reviewer.success)" -ForegroundColor Cyan
        Write-Host "  [Fase 4/4] Consenso -> $(if ($result.contract_valid) {'VALIDO'} else {'CON ISSUES'})" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  OUTPUT PRINCIPAL:" -ForegroundColor White
        $result.output -split "`n" | Select-Object -First 8 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        Write-Host ""
        Write-Host "  REVIEW:" -ForegroundColor Yellow
        $result.review -split "`n" | Select-Object -First 4 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        Write-Host ""
        Write-Host "  Duracion: $($result.duration_ms)ms | Contract: $($result.contract_valid)" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: No se pudo obtener resultado del pipeline" -ForegroundColor Red
    }
    Write-Host ""
}
function Show-Banner {
    Detect-Source
    $bannerScript = Join-Path $script:PRIMARY "tools\\bago_banner.py"
    if (Test-Path $bannerScript) {
        python $bannerScript
    } else {
        Write-Host ""
        Write-Host '  BAGO Framework v2026.05' -ForegroundColor Cyan
        Write-Host '  Balanceado · Adaptativo · Generativo · Organizativo' -ForegroundColor DarkGray
        Write-Host ""
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

    $providersFile = Join-Path $script:PRIMARY "state\model_providers.json"
    if (Test-Path $providersFile) {
        $providers = Get-Content $providersFile | ConvertFrom-Json
        $localModels = $providers.providers."ollama-local".models.PSObject.Properties.Name -join ", "
        $cloudModels = $providers.providers.copilot.models.PSObject.Properties.Name -join ", "
        Write-Host "  Locales:    $localModels" -ForegroundColor Yellow
        Write-Host "  Cloud:      $cloudModels" -ForegroundColor Yellow
    }

    # Health check
    $healthScript = Join-Path $script:PRIMARY "tools\health_check.py"
    if (Test-Path $healthScript) {
        Write-Host ""
        Write-Host "  Health Check:" -ForegroundColor White
        $health = python $healthScript 2>$null | Select-String "OK|NO" | Select-Object -First 4
        $health | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    }

    Write-Host ""
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
        "assets" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isCasino) {
            Write-Host "ERROR: No estas en un proyecto Casino BAGO" -ForegroundColor Red
            Write-Host "  Detectado: $($ctx.path)" -ForegroundColor DarkGray
            exit 1
        }
        $script = Join-Path $script:PRIMARY "tools\pipeline_casino_assets.py"
        python $script --project-dir $($ctx.path)
    }
    "deploy" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isCasino) {
            Write-Host "ERROR: No estas en un proyecto Casino BAGO" -ForegroundColor Red
            exit 1
        }
        $port = if ($rest[0]) { $rest[0] } else { 8080 }
        $script = Join-Path $script:PRIMARY "tools\pipeline_casino_deploy.py"
        python $script --project-dir $($ctx.path) --port $port
    }
    "balance" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isCasino) {
            Write-Host "ERROR: No estas en un proyecto Casino BAGO" -ForegroundColor Red
            exit 1
        }
        $script = Join-Path $script:PRIMARY "tools\pipeline_casino_balance.py"
        python $script --project-dir $($ctx.path)
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

function Sync-Knowledge {
    param([string[]]$RawArgs = @())
    Detect-Source
    $knowledgeScript = Join-Path $script:PRIMARY "tools\knowledge_sync.py"
    if (-not (Test-Path $knowledgeScript)) {
        Write-Host "No se encontro knowledge_sync.py en $knowledgeScript" -ForegroundColor Red
        return
    }
    if (-not $RawArgs -or $RawArgs.Count -eq 0) {
        $RawArgs = @("sync")
    }
    python $knowledgeScript @RawArgs
}

function Get-EngineProfile {
    $installedManifest = Join-Path $env:ProgramFiles "BAGO\runtime_contract.json"
    if (Test-Path $installedManifest) {
        try {
            $manifest = Get-Content -Raw -LiteralPath $installedManifest | ConvertFrom-Json
            if ($manifest.PSObject.Properties.Name -contains "install_profile" -and $manifest.install_profile) {
                return [string]$manifest.install_profile
            }
            if ($manifest.PSObject.Properties.Name -contains "knowledge_included") {
                return if ($manifest.knowledge_included) { "with-knowledge" } else { "without-knowledge" }
            }
        } catch {}
    }

    $sourceContract = Join-Path $PSScriptRoot "docs\runtime_contract.json"
    if (Test-Path $sourceContract) {
        try {
            $contract = Get-Content -Raw -LiteralPath $sourceContract | ConvertFrom-Json
            if ($contract.PSObject.Properties.Name -contains "publication") {
                $publication = $contract.publication
                if ($publication.PSObject.Properties.Name -contains "default_profile" -and $publication.default_profile) {
                    return [string]$publication.default_profile
                }
            }
        } catch {}
    }

    return "with-knowledge"
}

function Refresh-Engine {
    param([string[]]$RawArgs = @())

    $profile = Get-EngineProfile
    foreach ($arg in $RawArgs) {
        switch ($arg.ToLowerInvariant()) {
            "--with-knowledge" { $profile = "with-knowledge" }
            "--without-knowledge" { $profile = "without-knowledge" }
            "--help" {
                Write-Host ""
                Write-Host "  Uso: BAGO dev refresh-engine [--with-knowledge|--without-knowledge]" -ForegroundColor Yellow
                Write-Host "  Reinstala el motor limpio y lo valida al final." -ForegroundColor DarkGray
                Write-Host ""
                return
            }
            default {
                if ($arg) {
                    Write-Host "  Argumento no reconocido: $arg" -ForegroundColor Red
                    Write-Host "  Uso: BAGO dev refresh-engine [--with-knowledge|--without-knowledge]" -ForegroundColor Yellow
                    return
                }
            }
        }
    }

    $installer = Join-Path $PSScriptRoot "install.ps1"
    if (-not (Test-Path $installer)) {
        Write-Host "No se encontro install.ps1 en $installer" -ForegroundColor Red
        return
    }

    $installArgs = @()
    if ($profile -eq "without-knowledge") {
        $installArgs += "-NoKnowledge"
    }

    Write-Host ""
    Write-Host "  BAGO Dev · Refresh Engine" -ForegroundColor White
    Write-Host ("  " + ("-" * 42)) -ForegroundColor DarkGray
    Write-Host "  Perfil: $profile" -ForegroundColor Cyan
    Write-Host "  Motor destino: $env:ProgramFiles\BAGO" -ForegroundColor Cyan
    Write-Host ""

    & $installer @installArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $installedBago = Join-Path $env:ProgramFiles "BAGO\bago.cmd"
    if (Test-Path $installedBago) {
        Write-Host ""
        Write-Host "  Validando motor instalado..." -ForegroundColor Cyan
        & $installedBago validate
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    Write-Host ""
    Write-Host "  ✓ Motor refrescado y validado" -ForegroundColor Green
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
function Detect-ProjectContext {
    $cwd = Get-Location
    $files = Get-ChildItem $cwd -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
    $hasCasino = ($files -contains 'slot_engine.py') -or ($files -contains 'bot.py') -or ($files -contains 'casino.db')
    $hasPython = ($files -contains 'requirements.txt') -or ($files -contains 'server.py') -or ($files -contains 'app.py') -or (Test-Path (Join-Path $cwd '__init__.py'))
    $hasNode = ($files -contains 'package.json')
    $hasWeb = ($files -contains 'index.html') -and (-not $hasPython) -and (-not $hasNode)
    $isProject = $hasCasino -or $hasPython -or $hasNode -or $hasWeb -or (Test-Path (Join-Path $cwd '.git')) -or (Test-Path (Join-Path $cwd 'README.md'))
    
    $type = if ($hasCasino) { 'casino' } elseif ($hasPython) { 'python' } elseif ($hasNode) { 'node' } elseif ($hasWeb) { 'web' } else { 'generic' }
    
    return @{ 
        isProject = $isProject; 
        type = $type; 
        path = $cwd;
        files = $files;
    }
}

function Build-Project {
    param([string]$projectType, [string]$projectPath)
    Write-Host "  [Build] Tipo: $projectType" -ForegroundColor Cyan
    switch ($projectType) {
        'casino' {
            $script = Join-Path $script:PRIMARY "tools\pipeline_casino_assets.py"
            python $script --project-dir $projectPath
        }
        'python' {
            Write-Host "  Python project: instalando dependencias..." -ForegroundColor DarkGray
            $req = Join-Path $projectPath 'requirements.txt'
            if (Test-Path $req) { pip install -r $req 2>$null }
            Write-Host "  OK" -ForegroundColor Green
        }
        'node' {
            Write-Host "  Node project: npm install..." -ForegroundColor DarkGray
            Push-Location $projectPath; npm install 2>$null; Pop-Location
            Write-Host "  OK" -ForegroundColor Green
        }
        'web' {
            Write-Host "  Web project: no build necesario" -ForegroundColor DarkGray
        }
        default {
            Write-Host "  Proyecto generico: no hay build definido" -ForegroundColor Yellow
        }
    }
}

function Test-Project {
    param([string]$projectType, [string]$projectPath)
    Write-Host "  [Test] Ejecutando tests..." -ForegroundColor Cyan
    $hasTests = (Test-Path (Join-Path $projectPath 'tests')) -or (Test-Path (Join-Path $projectPath 'test'))
    if (-not $hasTests) {
        Write-Host "  No se encontraron tests/" -ForegroundColor Yellow
        return
    }
    switch ($projectType) {
        'casino' {
            Push-Location $projectPath; python -m pytest tests/ -v --tb=short 2>$null; Pop-Location
        }
        'python' {
            if (Test-Path (Join-Path $projectPath 'pytest.ini')) {
                Push-Location $projectPath; python -m pytest -v --tb=short 2>$null; Pop-Location
            } else {
                Push-Location $projectPath; python -m unittest discover -s tests -v 2>$null; Pop-Location
            }
        }
        'node' {
            Push-Location $projectPath; npm test 2>$null; Pop-Location
        }
        default {
            Write-Host "  Tests no configurados para este tipo" -ForegroundColor Yellow
        }
    }
}

function Lint-Project {
    param([string]$projectType, [string]$projectPath)
    Write-Host "  [Lint] Analisis de calidad..." -ForegroundColor Cyan
    switch ($projectType) {
        'casino' {
            Push-Location $projectPath; Get-ChildItem -Filter *.py | ForEach-Object { python -m py_compile $_.FullName 2>$null }; Pop-Location
            Write-Host "  Sintaxis OK" -ForegroundColor Green
        }
        'python' {
            Push-Location $projectPath; Get-ChildItem -Filter *.py | ForEach-Object { python -m py_compile $_.FullName 2>$null }; Pop-Location
            Write-Host "  Sintaxis OK" -ForegroundColor Green
        }
        'node' {
            Push-Location $projectPath; npm run lint 2>$null; Pop-Location
        }
        default {
            Write-Host "  Lint no configurado" -ForegroundColor Yellow
        }
    }
}

function Deploy-Project {
    param([string]$projectType, [string]$projectPath, [int]$port)
    Write-Host "  [Deploy] Desplegando..." -ForegroundColor Cyan
    switch ($projectType) {
        'casino' {
            $script = Join-Path $script:PRIMARY "tools\pipeline_casino_deploy.py"
            python $script --project-dir $projectPath --port $port
        }
        'python' {
            $server = Join-Path $projectPath 'server.py'
            if (Test-Path $server) {
                Start-Process python -ArgumentList $server -WindowStyle Hidden
                Write-Host "  Server arrancado" -ForegroundColor Green
            } else {
                Write-Host "  No se encontro server.py" -ForegroundColor Red
            }
        }
        'node' {
            Set-Location $projectPath; Start-Process npm -ArgumentList 'start' -WindowStyle Hidden; Set-Location -
            Write-Host "  npm start ejecutado" -ForegroundColor Green
        }
        'web' {
            Write-Host "  Abre index.html en navegador" -ForegroundColor Green
        }
        default {
            Write-Host "  Deploy no configurado para este tipo" -ForegroundColor Yellow
        }
    }
}

function Run-Project {
    param([string]$projectType, [string]$projectPath)
    Write-Host "  [Run] Ejecutando en modo dev..." -ForegroundColor Cyan
    switch ($projectType) {
        'casino' {
            $bot = Join-Path $projectPath 'bot.py'
            if (Test-Path $bot) { python $bot }
            else { Write-Host "  No se encontro bot.py" -ForegroundColor Red }
        }
        'python' {
            $main = Join-Path $projectPath 'main.py'
            if (Test-Path $main) { python $main }
            else { Write-Host "  No se encontro main.py" -ForegroundColor Red }
        }
        'node' {
            Set-Location $projectPath; npm start; Set-Location -
        }
        'web' {
            $index = Join-Path $projectPath 'index.html'
            if (Test-Path $index) { Start-Process $index }
        }
        default {
            Write-Host "  Run no configurado para este tipo" -ForegroundColor Yellow
        }
    }
}

function Clean-Project {
    param([string]$projectType, [string]$projectPath)
    Write-Host "  [Clean] Limpiando artefactos..." -ForegroundColor Cyan
    $patterns = @('__pycache__', '*.pyc', '.pytest_cache', 'node_modules', 'dist', 'build')
    foreach ($pat in $patterns) {
        Get-ChildItem $projectPath -Recurse -Filter $pat -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  OK" -ForegroundColor Green
}

function Reset-Db {
    param([string]$projectType, [string]$projectPath)
    Write-Host "  [DB-Reset] Resetear estado..." -ForegroundColor Cyan
    switch ($projectType) {
        'casino' {
            $db = Join-Path $projectPath 'casino.db'
            if (Test-Path $db) {
                Remove-Item $db -Force
                Write-Host "  DB eliminada: $db" -ForegroundColor Yellow
            }
            $dbScript = Join-Path $projectPath 'db.py'
            if (Test-Path $dbScript) {
                python -c "import sys; sys.path.insert(0, '$projectPath'); import db" 2>$null
                Write-Host "  DB reinicializada" -ForegroundColor Green
            }
        }
        default {
            $dbs = Get-ChildItem $projectPath -Filter '*.db' -ErrorAction SilentlyContinue
            if ($dbs) {
                $dbs | Remove-Item -Force
                Write-Host "  DBs eliminadas: $($dbs.Name -join ', ')" -ForegroundColor Yellow
            } else {
                Write-Host "  No hay DBs que resetear" -ForegroundColor DarkGray
            }
        }
    }
}

function Invoke-BagoChat {
    param(
        [string]$Provider = "",
        [string[]]$RawArgs = @()
    )
    Detect-Source
    $chatScript = Join-Path $script:PRIMARY "tools\bago_chat.py"

    if ($Provider) {
        python $chatScript --provider $Provider
        return
    }

    if ($RawArgs -and $RawArgs.Count -gt 0) {
        if ($RawArgs[0].StartsWith("-")) {
            python $chatScript @RawArgs
        } else {
            python $chatScript --provider $RawArgs[0]
        }
        return
    }

    python $chatScript
}

function Invoke-BagoMenu {
    param([string[]]$RawArgs = @())
    Detect-Source
    $menuScript = Join-Path $script:PRIMARY "tools\bago_menu.py"
    if ($RawArgs -and $RawArgs.Count -gt 0) {
        python $menuScript @RawArgs
    } else {
        python $menuScript
    }
}

function Invoke-CanonicalEntry {
    param(
        [string]$From = "launch",
        [string]$Provider = "",
        [string[]]$RawArgs = @()
    )
    if ($From -and $From -ne "launch") {
        Write-Host "Alias '$From' redirigido a entrada canónica: BAGO launch" -ForegroundColor DarkYellow
    }
    if ($Provider) {
        Invoke-BagoChat -Provider $Provider
    } else {
        Invoke-BagoChat -RawArgs @($RawArgs)
    }
}

# === Main ===

# Sin argumentos: entrar directamente por la puerta canónica.
if ($args.Count -eq 0) {
    Show-Banner
    Invoke-CanonicalEntry -From "default"
    exit $LASTEXITCODE
}
$command = $args[0]
$rest = $args[1..($args.Length-1)]

switch ($command) {
    "status" { Show-Banner; Show-Status }
    "inventory" {
        Detect-Source
        $invScript = Join-Path $script:PRIMARY "tools\bago_inventory.py"
        if ($rest[0]) {
            python $invScript --suggest $rest[0]
        } else {
            python $invScript
        }
    }
    "launch" {
        # Entrada canónica de la app.
        Invoke-CanonicalEntry -From "launch" -RawArgs @($rest)
    }
    # Alias corto: "bago chat" == "bago launch"
    "chat" {
        Invoke-CanonicalEntry -From "chat" -RawArgs @($rest)
    }

    # Alias copilot/codex/gpt: "bago copilot" == "bago launch copilot"
    "copilot" {
        Invoke-CanonicalEntry -From "copilot" -Provider "copilot"
    }
    "codex" {
        Invoke-CanonicalEntry -From "codex" -Provider "codex"
    }
    "gpt" {
        Invoke-CanonicalEntry -From "gpt" -Provider "codex"
    }
    "claude" {
        Invoke-CanonicalEntry -From "claude" -Provider "anthropic"
    }
    "ollama" {
        Invoke-CanonicalEntry -From "ollama" -Provider "ollama-local"
    }

    # Compatibilidad: `bago menu --list` sigue disponible.
    # El modo interactivo principal se centraliza en `bago launch`.
    "menu" {
        if ($rest -and $rest[0] -eq "--list") {
            Invoke-BagoMenu -RawArgs @($rest)
        } else {
            Invoke-CanonicalEntry -From "menu"
        }
    }

    "pipeline" {
        Invoke-BagoPipeline -task ($rest -join " ")
    }
    "install" { Install-Component -component $rest[0] }
    "sync" {
        if ($rest -and $rest[0] -eq "knowledge") {
            $knowledgeArgs = @()
            if ($rest.Count -gt 1) {
                $knowledgeArgs = $rest[1..($rest.Count-1)]
            }
            Sync-Knowledge -RawArgs $knowledgeArgs
        } else {
            $dir = if ($rest[0]) { $rest[0] } else { "auto" }
            Sync-USB -direction $dir
        }
    }
    "knowledge" { Sync-Knowledge -RawArgs $rest }
    "dev" {
        if ($rest -and $rest[0] -eq "refresh-engine") {
            $refreshArgs = @()
            if ($rest.Count -gt 1) {
                $refreshArgs = $rest[1..($rest.Count-1)]
            }
            Refresh-Engine -RawArgs $refreshArgs
        } else {
            Write-Host "Uso: BAGO dev refresh-engine [--with-knowledge|--without-knowledge]" -ForegroundColor Yellow
        }
    }
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
    "build" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        Build-Project -projectType $ctx.type -projectPath $ctx.path
    }
    "test" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        Test-Project -projectType $ctx.type -projectPath $ctx.path
    }
    "lint" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        Lint-Project -projectType $ctx.type -projectPath $ctx.path
    }
    "deploy" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        $port = if ($rest[0]) { [int]$rest[0] } else { 8080 }
        Deploy-Project -projectType $ctx.type -projectPath $ctx.path -port $port
    }
    "run" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        Run-Project -projectType $ctx.type -projectPath $ctx.path
    }
    "clean" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        Clean-Project -projectType $ctx.type -projectPath $ctx.path
    }
    "db-reset" {
        Detect-Source
        $ctx = Detect-ProjectContext
        if (-not $ctx.isProject) { Write-Host "ERROR: No estas en un proyecto" -ForegroundColor Red; exit 1 }
        Reset-Db -projectType $ctx.type -projectPath $ctx.path
    }
    "ideas" {
        Detect-Source
        $ideasScript = Join-Path $script:PRIMARY "tools\emit_ideas.py"
        $ideasArgs = if ($args.Length -gt 1) { $args[1..($args.Length-1)] } else { @() }
        if ($ideasArgs.Count -gt 0) { python $ideasScript @ideasArgs } else { python $ideasScript }
    }
    "telegram" {
        Detect-Source
        $bridgeScript = Join-Path $script:PRIMARY "tools\bago_telegram_bridge.py"
        $action = if ($rest.Count -gt 0) { $rest[0] } else { "start" }
        switch ($action) {
            "start" {
                Write-Host "Iniciando bridge Telegram..." -ForegroundColor Cyan
                Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File $bridgeScript" -WindowStyle Hidden
                Write-Host "✓ Bridge iniciado en segundo plano" -ForegroundColor Green
            }
            "stop" {
                Get-Process python | Where-Object { $_.CommandLine -like "*bago_telegram_bridge*" } | Stop-Process -Force
                Write-Host "✓ Bridge detenido" -ForegroundColor Green
            }
            "status" {
                $procs = Get-Process python | Where-Object { $_.CommandLine -like "*bago_telegram_bridge*" }
                if ($procs) { Write-Host "✓ Bridge activo" -ForegroundColor Green } else { Write-Host "✗ Bridge inactivo" -ForegroundColor Red }
            }
            default { Write-Host "Uso: BAGO telegram [start|stop|status]" -ForegroundColor Yellow }
        }
    }
    "apk" {
        Detect-Source
        $monitorScript = Join-Path $script:PRIMARY "tools\bago_music_apk_monitor.py"
        python $monitorScript
    }
    default {
        # Fallback: delegar comandos no implementados en este launcher
        # al launcher Python canónico (repo-root/bago), que cubre todo
        # el registro de tools BAGO.
        if ($command) {
            Detect-Source
            $root = Split-Path $script:PRIMARY -Parent
            $candidate = Join-Path $root "bago"
            $coreLauncher = Join-Path $root "bago_core\launcher.py"
            if (Test-Path $candidate -PathType Leaf) {
                $forwardArgs = @($command)
                if ($rest) { $forwardArgs += $rest }
                & python $candidate @forwardArgs
                exit $LASTEXITCODE
            }
            if (Test-Path $coreLauncher -PathType Leaf) {
                $forwardArgs = @($command)
                if ($rest) { $forwardArgs += $rest }
                & python $coreLauncher @forwardArgs
                exit $LASTEXITCODE
            }
        }

        Write-Host @"
BAGO Launcher v2026.05

Uso: BAGO <comando> [args]

Entrada canónica de la app:
  BAGO launch

Comandos globales:
  BAGO status              → Estado de BAGO y fuente de verdad
  BAGO inventory [tipo]    → Descubre herramientas, roles y workflows existentes
  BAGO launch              → Orquestador: pregunta tarea y selecciona modelo optimo
  BAGO chat/menu/...       → aliases de compatibilidad (redirigen a launch)
  BAGO launch [modelo]     → Lanza modelo especifico
  BAGO launch copilot      → Codex CLI con mejor modelo Copilot (incluido)
  BAGO launch codex        → Codex CLI con mejor modelo Codex (créditos OpenAI)
  BAGO launch ollama       → Codex CLI con Ollama local (gratis, offline)
  BAGO pipeline [tarea]    → Ejecuta pipeline de 4 fases en segundo plano
  BAGO install             → Lista componentes disponibles
  BAGO install [modelo]    → Instala modelo o herramienta
  BAGO sync [--to-usb|--from-usb] → Sincroniza con pendrive
  BAGO contribute          → Genera informe de aprendizaje
  BAGO repo init           → Crea repo Git para progresos
  BAGO repo sync           → Sube progresos a GitHub

Comandos de proyecto (desde directorio del proyecto):
  BAGO build               → Construye/genera artefactos del proyecto
  BAGO test                → Ejecuta tests
  BAGO lint                → Analisis de calidad
  BAGO deploy [puerto]     → Despliega/arranca servidor
  BAGO run                 → Ejecuta en modo desarrollo
  BAGO clean               → Limpia artefactos generados
  BAGO db-reset            → Resetea base de datos
  BAGO ideas [args]        → Emite ideas contextuales del catalogo
  BAGO build --target apk|electron|docker  → Build multiplataforma
  BAGO ideas [args]        → Emite ideas contextuales del catalogo
  BAGO apk                 → Monitorizar build APK y enviar por Telegram
  BAGO ideas [args]        → Emite ideas contextuales del catalogo
  BAGO telegram [start|stop|status] → Bridge de Telegram bidireccional

Ejemplos:
  BAGO launch
  BAGO launch qwen25-coder
  BAGO install qwen25-mini
  BAGO build
  BAGO deploy 8080
  BAGO test
  BAGO db-reset
"@ -ForegroundColor White
        exit 1
    }
}


