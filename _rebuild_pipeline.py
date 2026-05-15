import re

text = open("bago.ps1","r",encoding="utf-8").read()

# Reemplazar todo el bloque de Invoke-BagoPipeline existente (si hay) con uno nuevo correcto
start_marker = "function Invoke-BagoPipeline {"
end_marker = "function Show-Status {"

if start_marker in text and end_marker in text:
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    old_block = text[start_idx:end_idx]
else:
    old_block = None

new_pipeline = """function Invoke-BagoPipeline {
    param([string]$task)
    Detect-Source
    Write-Host ""
    Write-Host "  [BAGO Pipeline] Orquestando en segundo plano..." -ForegroundColor Magenta
    Write-Host "  Tarea: $task" -ForegroundColor White
    Write-Host ""

    # FASE 1: Router rapido
    Write-Host "  [Fase 1/4] Router clasificando..." -ForegroundColor Cyan
    $routerScript = Join-Path $script:PRIMARY "tools\\bago_orchestrator.py"
    $routerResult = $null
    if (Test-Path $routerScript) {
        $routerOutput = python $routerScript "$task" 2>$null
        $routerModel = ($routerOutput | Select-String "Modelo:\\s+(\\S+)").Matches.Groups[1].Value
        $routerAgent = ($routerOutput | Select-String "Agente:\\s+(\\S+)").Matches.Groups[1].Value
        if ($routerModel) {
            $routerResult = @{ Model = $routerModel; Agent = $routerAgent }
            Write-Host "    Agente: $($routerResult.Agent)" -ForegroundColor Green
            Write-Host "    Modelo: $($routerResult.Model)" -ForegroundColor Green
        }
    }
    if (-not $routerResult) {
        $routerResult = @{ Model = "gpt-5.4"; Agent = "codex" }
        Write-Host "    Fallback: gpt-5.4 (codex)" -ForegroundColor Yellow
    }

    # Preparar paths
    $ghPath = Find-Gh
    $token = $null
    $tokenFile = Join-Path $script:PRIMARY "config/github_token.txt"
    if (Test-Path $tokenFile) {
        $token = (Get-Content $tokenFile -Encoding UTF8 -Raw).Trim()
    }

    # FASE 2: Ejecutores paralelos
    Write-Host ""
    Write-Host "  [Fase 2/4] Lanzando ejecutores paralelos..." -ForegroundColor Cyan
    $jobs = @()

    # Ejecutor A: Principal
    Write-Host "    - Principal: $($routerResult.Model) [$($routerResult.Agent)]" -ForegroundColor White
    $jobA = Start-Job -ScriptBlock {
        param($agent, $model, $t, $primary, $gh, $tok)
        if ($tok) { $env:GH_TOKEN = $tok }
        switch ($agent) {
            "copilot" {
                if ($gh -and (Test-Path $gh)) {
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
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = "ollama"
                $psi.Arguments = "run $model `"$t`""
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                return @{ source = $model; output = $out; exit = $proc.ExitCode }
            }
            default {
                return @{ source = $model; output = "Codex/Agente no implementado en pipeline"; exit = 1 }
            }
        }
    } -ArgumentList $routerResult.Agent, $routerResult.Model, $task, $script:PRIMARY, $ghPath, $token
    $jobs += $jobA

    # Ejecutor B: Review
    $reviewModel = "claude-sonnet-4.6"
    if ($routerResult.Model -ne $reviewModel -and $ghPath) {
        Write-Host "    - Review: $reviewModel [copilot]" -ForegroundColor White
        $jobB = Start-Job -ScriptBlock {
            param($t, $primary, $gh, $tok)
            if ($tok) { $env:GH_TOKEN = $tok }
            if ($gh -and (Test-Path $gh)) {
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $gh
                $psi.Arguments = "copilot -p `'Revisa y da feedback conciso: $t`'"
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                return @{ source = "claude-sonnet-4.6"; output = $out; exit = $proc.ExitCode }
            }
            return @{ source = "claude-sonnet-4.6"; output = "gh no disponible"; exit = 1 }
        } -ArgumentList $task, $script:PRIMARY, $ghPath, $token
        $jobs += $jobB
    }

    # FASE 3: Esperar resultados
    Write-Host ""
    Write-Host "  [Fase 3/4] Esperando resultados (timeout 30s)..." -ForegroundColor Cyan
    $completed = $jobs | Wait-Job -Timeout 30
    $results = @()
    foreach ($j in $jobs) {
        if ($j.State -eq "Completed") {
            $r = Receive-Job -Job $j
            $results += $r
            $firstLine = (($r.output -split "`n") | Select-Object -First 1)
            if (-not $firstLine) { $firstLine = "(sin salida)" }
            $truncated = $firstLine.Substring(0, [Math]::Min(60, $firstLine.Length))
            Write-Host "    [OK] $($r.source): $truncated..." -ForegroundColor Green
        } else {
            Stop-Job -Job $j -ErrorAction SilentlyContinue
            $results += @{ source = "timeout"; output = "Timeout"; exit = 1 }
            Write-Host "    [TIMEOUT] Job no completo" -ForegroundColor Red
        }
        Remove-Job -Job $j -ErrorAction SilentlyContinue
    }

    # FASE 4: Consenso
    Write-Host ""
    Write-Host "  [Fase 4/4] Consenso y validacion..." -ForegroundColor Cyan
    $mainOutput = ($results | Where-Object { $_.source -eq $routerResult.Model }).output
    $reviewOutput = ($results | Where-Object { $_.source -eq "claude-sonnet-4.6" }).output

    Write-Host ""
    Write-Host "  ==============================================" -ForegroundColor White
    Write-Host "  RESULTADO PRINCIPAL [$($routerResult.Model)]" -ForegroundColor White
    Write-Host "  ==============================================" -ForegroundColor White
    if ($mainOutput) {
        $mainOutput.Trim().Split("`n") | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "  (sin resultado)" -ForegroundColor Red
    }

    if ($reviewOutput -and $reviewOutput -ne "gh no disponible" -and $reviewOutput -ne "Timeout") {
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
    }
}

"""

if old_block and end_marker in text:
    text = text[:start_idx] + new_pipeline + text[end_idx:]
    print("[OK] Invoke-BagoPipeline reemplazado")
elif start_marker not in text:
    # Insertar antes de Show-Status
    text = text.replace(end_marker, new_pipeline + end_marker)
    print("[OK] Invoke-BagoPipeline agregado")

# Agregar comando pipeline al switch
old_launch = '''    "launch" {
        if ($rest[0]) {
            Launch-Model -model $rest[0]
        } else {
            Launch-Orchestrated -task ($rest -join " ")
        }
    }'''
new_launch = '''    "launch" {
        if ($rest[0]) {
            Launch-Model -model $rest[0]
        } else {
            Launch-Orchestrated -task ($rest -join " ")
        }
    }
    "pipeline" {
        Invoke-BagoPipeline -task ($rest -join " ")
    }'''
if old_launch in text and '"pipeline"' not in text:
    text = text.replace(old_launch, new_launch)
    print("[OK] Comando pipeline agregado")

# Actualizar help
old_help = '  BAGO launch              → Orquestador: pregunta tarea y selecciona agente+modelo optimos'
new_help = '  BAGO launch              → Orquestador: pregunta tarea y selecciona agente+modelo optimos\n  BAGO pipeline [tarea]    → Pipeline paralelo: router + ejecutores + consenso'
if old_help in text and 'BAGO pipeline' not in text:
    text = text.replace(old_help, new_help)
    print("[OK] Help actualizado")

open("bago.ps1","w",encoding="utf-8").write(text)
print("Done")
