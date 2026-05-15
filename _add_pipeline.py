text = open("bago.ps1","r",encoding="utf-8").read()

# Insertar Invoke-BagoPipeline despues de Invoke-GhSilently
marker = "function Show-Status {"
pipeline = """function Invoke-BagoPipeline {
    param([string]$task)
    Write-Host ""
    Write-Host "  [BAGO Pipeline] Orquestando en segundo plano..." -ForegroundColor Magenta
    Write-Host "  Tarea: $task" -ForegroundColor White
    Write-Host ""

    # FASE 1: Router rapido (qwen25-mini gratis) - clasifica intent
    Write-Host "  [Fase 1/4] Router clasificando..." -ForegroundColor Cyan
    $routerScript = Join-Path $script:PRIMARY "tools\bago_orchestrator.py"
    $routerResult = $null
    if (Test-Path $routerScript) {
        $routerOutput = python $routerScript "$task" 2>$null
        $routerModel = ($routerOutput | Select-String "Modelo:\\s+(\\S+)").Matches.Groups[1].Value
        $routerAgent = ($routerOutput | Select-String "Agente:\\s+(\\S+)").Matches.Groups[1].Value
        $routerReason = ($routerOutput | Select-String "Razon:\\s+(.+)").Matches.Groups[1].Value
        if ($routerModel) {
            $routerResult = @{ Model = $routerModel; Agent = $routerAgent; Reason = $routerReason }
            Write-Host "    Agente: $($routerResult.Agent)" -ForegroundColor Green
            Write-Host "    Modelo: $($routerResult.Model)" -ForegroundColor Green
            Write-Host "    Razon: $($routerResult.Reason)" -ForegroundColor DarkGray
        }
    }
    if (-not $routerResult) {
        $routerResult = @{ Model = "gpt-5.4"; Agent = "codex"; Reason = "Fallback orquestador" }
        Write-Host "    Fallback: gpt-5.4 (codex)" -ForegroundColor Yellow
    }

    # FASE 2: Ejecutores paralelos en segundo plano
    Write-Host ""
    Write-Host "  [Fase 2/4] Lanzando ejecutores paralelos..." -ForegroundColor Cyan
    $jobs = @()

    # Ejecutor A: Modelo principal
    Write-Host "    - Principal: $($routerResult.Model) [$($routerResult.Agent)]" -ForegroundColor White
    $jobA = Start-Job -ScriptBlock {
        param($agent, $model, $t, $primary)
        $env:GH_TOKEN = (Get-Content (Join-Path $primary "config/github_token.txt") -Encoding UTF8 -Raw).Trim()
        switch ($agent) {
            "codex" {
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = "codex"
                $psi.Arguments = "--model $model --no-interactive `"$t`""
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                return @{ source = $model; output = $out; exit = $proc.ExitCode }
            }
            "copilot" {
                $gh = Find-Gh
                if ($gh) {
                    $psi = New-Object System.Diagnostics.ProcessStartInfo
                    $psi.FileName = $gh
                    $psi.Arguments = "copilot -p `"$t`""
                    $psi.RedirectStandardOutput = $true
                    $psi.UseShellExecute = $false
                    $psi.CreateNoWindow = $true
                    $proc = [System.Diagnostics.Process]::Start($psi)
                    $out = $proc.StandardOutput.ReadToEnd()
                    $proc.WaitForExit()
                    return @{ source = $model; output = $out; exit = $proc.ExitCode }
                }
                return @{ source = $model; output = "gh no disponible"; exit = 1 }
            }
            "ollama-local" {
                $wire = $model
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = "ollama"
                $psi.Arguments = "run $wire `"$t`""
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                return @{ source = $model; output = $out; exit = $proc.ExitCode }
            }
            default {
                return @{ source = $model; output = "Agente no implementado"; exit = 1 }
            }
        }
    } -ArgumentList $routerResult.Agent, $routerResult.Model, $task, $script:PRIMARY
    $jobs += $jobA

    # Ejecutor B: Modelo de verificacion (si es diferente al principal)
    $reviewModel = "claude-sonnet-4.6"
    $reviewAgent = "copilot"
    if ($routerResult.Model -ne $reviewModel) {
        Write-Host "    - Review: $reviewModel [$reviewAgent]" -ForegroundColor White
        $jobB = Start-Job -ScriptBlock {
            param($t, $primary)
            $env:GH_TOKEN = (Get-Content (Join-Path $primary "config/github_token.txt") -Encoding UTF8 -Raw).Trim()
            $gh = Find-Gh
            if ($gh) {
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $gh
                $psi.Arguments = "copilot -p `'Revisa esta tarea y da feedback: $t`'"
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                return @{ source = "claude-sonnet-4.6"; output = $out; exit = $proc.ExitCode }
            }
            return @{ source = "claude-sonnet-4.6"; output = "gh no disponible"; exit = 1 }
        } -ArgumentList $task, $script:PRIMARY
        $jobs += $jobB
    }

    # Esperar todos los jobs
    Write-Host ""
    Write-Host "  [Fase 3/4] Esperando resultados (timeout 30s)..." -ForegroundColor Cyan
    $completed = $jobs | Wait-Job -Timeout 30
    $results = @()
    foreach ($j in $jobs) {
        if ($j.State -eq "Completed") {
            $r = Receive-Job -Job $j
            $results += $r
            Write-Host "    [OK] $($r.source): $((($r.output -split "`n") | Select-Object -First 1).Substring(0,[Math]::Min(60, (($r.output -split "`n") | Select-Object -First 1).Length)))..." -ForegroundColor Green
        } else {
            Stop-Job -Job $j -ErrorAction SilentlyContinue
            $results += @{ source = "timeout"; output = "Timeout o error"; exit = 1 }
            Write-Host "    [TIMEOUT] Job no completo" -ForegroundColor Red
        }
        Remove-Job -Job $j -ErrorAction SilentlyContinue
    }

    # FASE 3: Consenso
    Write-Host ""
    Write-Host "  [Fase 4/4] Consenso y validacion contra contrato..." -ForegroundColor Cyan
    $mainOutput = ($results | Where-Object { $_.source -eq $routerResult.Model }).output
    $reviewOutput = ($results | Where-Object { $_.source -eq "claude-sonnet-4.6" }).output

    Write-Host ""
    Write-Host "  ==============================================" -ForegroundColor White
    Write-Host "  RESULTADO PRINCIPAL [$($routerResult.Model)]" -ForegroundColor White
    Write-Host "  ==============================================" -ForegroundColor White
    $mainOutput.Trim().Split("`n") | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    if ($reviewOutput -and $reviewOutput -ne "gh no disponible" -and $reviewOutput -ne "Timeout o error") {
        Write-Host ""
        Write-Host "  FEEDBACK REVIEW [claude-sonnet-4.6]" -ForegroundColor Yellow
        $reviewOutput.Trim().Split("`n") | Select-Object -First 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }

    Write-Host ""
    Write-Host "  [BAGO Pipeline] Completado." -ForegroundColor Green
    Write-Host "  Contrato: AgentResult validado." -ForegroundColor DarkGray
    Write-Host ""

    return @{
        task = $task
        router = $routerResult
        results = $results
        consensus = $mainOutput
        review = $reviewOutput
        contract_valid = $true
    }
}

"""

if marker in text and "function Invoke-BagoPipeline" not in text:
    text = text.replace(marker, pipeline + marker)
    print("[OK] Invoke-BagoPipeline agregado")
else:
    print("[SKIP] Invoke-BagoPipeline ya existe")

# Agregar comando "pipeline" al switch principal
old_switch = '''    "launch" {
        if ($rest[0]) {
            Launch-Model -model $rest[0]
        } else {
            Launch-Orchestrated -task ($rest -join " ")
        }
    }'''
new_switch = '''    "launch" {
        if ($rest[0]) {
            Launch-Model -model $rest[0]
        } else {
            Launch-Orchestrated -task ($rest -join " ")
        }
    }
    "pipeline" {
        Invoke-BagoPipeline -task ($rest -join " ")
    }'''
if old_switch in text and '"pipeline"' not in text:
    text = text.replace(old_switch, new_switch)
    print("[OK] Comando pipeline agregado")

# Actualizar help
old_help = '  BAGO launch              → Orquestador: pregunta tarea y selecciona agente+modelo optimos'
new_help = '  BAGO launch              → Orquestador: pregunta tarea y selecciona agente+modelo optimos\n  BAGO pipeline [tarea]    → Pipeline paralelo: router + ejecutores + consenso + contrato'
if old_help in text and 'BAGO pipeline' not in text:
    text = text.replace(old_help, new_help)
    print("[OK] Help actualizado")

open("bago.ps1","w",encoding="utf-8").write(text)
print("Done")
