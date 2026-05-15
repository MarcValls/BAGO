import re

text = open("bago.ps1","r",encoding="utf-8").read()

# Agregar Find-Gh antes de cualquier otra funcion que lo use
find_gh = """function Find-Gh {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) { return $gh.Source }
    $known = @(
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe"),
        "C:\\Program Files\\GitHub CLI\\gh.exe"
    )
    foreach ($p in $known) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

"""

if "function Find-Gh" not in text:
    text = text.replace("function Show-Status {", find_gh + "function Show-Status {")
    print("[OK] Find-Gh agregado")

# Agregar Invoke-BagoPipeline
pipeline = """function Invoke-BagoPipeline {
    param([string]$task)
    Detect-Source
    Write-Host ""
    Write-Host "  [BAGO Pipeline] Orquestando en segundo plano..." -ForegroundColor Magenta
    Write-Host "  Tarea: $task" -ForegroundColor White
    Write-Host ""

    # FASE 1: Router
    Write-Host "  [Fase 1/4] Router clasificando..." -ForegroundColor Cyan
    $routerScript = Join-Path $script:PRIMARY "tools\\bago_orchestrator.py"
    $routerResult = @{ Model = "gpt-5.4"; Agent = "codex" }
    if (Test-Path $routerScript) {
        $routerOutput = python $routerScript "$task" 2>$null
        $m = ($routerOutput | Select-String "Modelo:\\s+(\\S+)").Matches.Groups[1].Value
        $a = ($routerOutput | Select-String "Agente:\\s+(\\S+)").Matches.Groups[1].Value
        if ($m) { $routerResult = @{ Model = $m; Agent = $a } }
    }
    Write-Host "    Agente: $($routerResult.Agent) | Modelo: $($routerResult.Model)" -ForegroundColor Green

    $ghPath = Find-Gh
    $token = $null
    $tokenFile = Join-Path $script:PRIMARY "config/github_token.txt"
    if (Test-Path $tokenFile) { $token = (Get-Content $tokenFile -Encoding UTF8 -Raw).Trim() }

    # FASE 2: Principal (job en segundo plano)
    Write-Host ""
    Write-Host "  [Fase 2/4] Ejecutando principal [$($routerResult.Model)]..." -ForegroundColor Cyan
    $principal = $null
    if ($routerResult.Agent -eq "ollama-local") {
        $job = Start-Job -ScriptBlock {
            param($model, $t)
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = "ollama"
            $psi.Arguments = "run $model `"$t`""
            $psi.RedirectStandardOutput = $true
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $proc = [System.Diagnostics.Process]::Start($psi)
            $out = $proc.StandardOutput.ReadToEnd()
            $proc.WaitForExit(15000)
            if (-not $proc.HasExited) { $proc.Kill() }
            return $out
        } -ArgumentList $routerResult.Model, $task
    } else {
        # Usar gh copilot como proxy para codex/copilot
        if ($ghPath) {
            $job = Start-Job -ScriptBlock {
                param($gh, $tok, $t)
                $env:GH_TOKEN = $tok
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $gh
                $psi.Arguments = "copilot -p `"$t`""
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit(20000)
                if (-not $proc.HasExited) { $proc.Kill() }
                return $out
            } -ArgumentList $ghPath, $token, $task
        } else {
            $principal = "gh CLI no disponible."
        }
    }
    if ($job) {
        $job | Wait-Job -Timeout 25 | Out-Null
        if ($job.State -eq "Completed") {
            $principal = Receive-Job -Job $job
            $firstLine = (($principal -split "`n") | Select-Object -First 1)
            Write-Host "    OK: $firstLine" -ForegroundColor Green
        } else {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            $principal = "[Timeout: el modelo no respondio a tiempo]"
            Write-Host "    TIMEOUT" -ForegroundColor Red
        }
        Remove-Job -Job $job -ErrorAction SilentlyContinue
    }

    # FASE 3: Review
    Write-Host ""
    Write-Host "  [Fase 3/4] Ejecutando review [claude-sonnet-4.6]..." -ForegroundColor Cyan
    $review = $null
    if ($ghPath -and $principal -and $principal -notmatch "no disponible|Timeout") {
        $reviewPrompt = "Tarea: $task`n`nResultado:`n$principal`n`nFeedback conciso."
        $jobR = Start-Job -ScriptBlock {
            param($gh, $tok, $rp)
            $env:GH_TOKEN = $tok
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $gh
            $psi.Arguments = "copilot -p `"$rp`""
            $psi.RedirectStandardOutput = $true
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $proc = [System.Diagnostics.Process]::Start($psi)
            $out = $proc.StandardOutput.ReadToEnd()
            $proc.WaitForExit(20000)
            if (-not $proc.HasExited) { $proc.Kill() }
            return $out
        } -ArgumentList $ghPath, $token, $reviewPrompt
        $jobR | Wait-Job -Timeout 25 | Out-Null
        if ($jobR.State -eq "Completed") {
            $review = Receive-Job -Job $jobR
            Write-Host "    Review OK" -ForegroundColor Green
        } else {
            Stop-Job -Job $jobR -ErrorAction SilentlyContinue
            $review = "[Timeout]"
            Write-Host "    Review TIMEOUT" -ForegroundColor Red
        }
        Remove-Job -Job $jobR -ErrorAction SilentlyContinue
    } else {
        Write-Host "    Review omitido." -ForegroundColor DarkGray
    }

    # FASE 4: Consenso
    Write-Host ""
    Write-Host "  [Fase 4/4] Consenso y validacion..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ==============================================" -ForegroundColor White
    Write-Host "  RESULTADO PRINCIPAL [$($routerResult.Model)]" -ForegroundColor White
    Write-Host "  ==============================================" -ForegroundColor White
    if ($principal) {
        $principal.Trim().Split("`n") | Select-Object -First 12 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "  (sin resultado)" -ForegroundColor Red
    }
    if ($review -and $review -notmatch "Timeout") {
        Write-Host ""
        Write-Host "  FEEDBACK REVIEW [claude-sonnet-4.6]" -ForegroundColor Yellow
        $review.Trim().Split("`n") | Select-Object -First 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }
    Write-Host ""
    Write-Host "  [BAGO Pipeline] Completado." -ForegroundColor Green
    Write-Host ""
}

"""

# Reemplazar o insertar
if "function Invoke-BagoPipeline {" in text:
    start_idx = text.find("function Invoke-BagoPipeline {")
    end_idx = text.find("function Show-Status {")
    text = text[:start_idx] + pipeline + text[end_idx:]
    print("[OK] Pipeline reemplazado")
else:
    text = text.replace("function Show-Status {", pipeline + "function Show-Status {")
    print("[OK] Pipeline agregado")

# Agregar comando pipeline
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

open("bago.ps1","w",encoding="utf-8").write(text)
print("Done")
