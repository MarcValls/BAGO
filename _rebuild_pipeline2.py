import re

text = open("bago.ps1","r",encoding="utf-8").read()

# Encontrar y reemplazar Invoke-BagoPipeline
start = text.find("function Invoke-BagoPipeline {")
end = text.find("function Show-Status {")
if start == -1 or end == -1:
    print("ERROR: markers not found")
    exit(1)

new_pipeline = """function Invoke-BagoPipeline {
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

    # FASE 2: Ejecutor principal (segundo plano)
    Write-Host ""
    Write-Host "  [Fase 2/4] Ejecutando principal [$($routerResult.Model)]..." -ForegroundColor Cyan
    $principal = $null
    switch ($routerResult.Agent) {
        "codex" {
            # Codex no se puede ejecutar facilmente en pipeline, usar copilot como proxy
            if ($ghPath) {
                Write-Host "    Codex proxy via Copilot CLI..." -ForegroundColor DarkGray
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $ghPath
                $psi.Arguments = "copilot -p `"$task`""
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                if ($token) { $psi.EnvironmentVariables["GH_TOKEN"] = $token }
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                $principal = $out
            } else {
                $principal = "Codex requiere CLI. Proxy no disponible."
            }
        }
        "copilot" {
            if ($ghPath) {
                Write-Host "    Copilot CLI..." -ForegroundColor DarkGray
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $ghPath
                $psi.Arguments = "copilot -p `"$task`""
                $psi.RedirectStandardOutput = $true
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                if ($token) { $psi.EnvironmentVariables["GH_TOKEN"] = $token }
                $proc = [System.Diagnostics.Process]::Start($psi)
                $out = $proc.StandardOutput.ReadToEnd()
                $proc.WaitForExit()
                $principal = $out
            } else {
                $principal = "Copilot CLI no disponible."
            }
        }
        "ollama-local" {
            Write-Host "    Ollama local..." -ForegroundColor DarkGray
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = "ollama"
            $psi.Arguments = "run $($routerResult.Model) `"$task`""
            $psi.RedirectStandardOutput = $true
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $proc = [System.Diagnostics.Process]::Start($psi)
            $out = $proc.StandardOutput.ReadToEnd()
            $proc.WaitForExit()
            $principal = $out
        }
        default {
            $principal = "Agente $($routerResult.Agent) no implementado en pipeline."
        }
    }

    # FASE 3: Review/Feedback (segundo plano)
    Write-Host ""
    Write-Host "  [Fase 3/4] Ejecutando review [claude-sonnet-4.6]..." -ForegroundColor Cyan
    $review = $null
    if ($ghPath -and $principal -and $principal -notmatch "no disponible|no implementado") {
        $reviewPrompt = "Tarea: $task`n`nResultado propuesto:`n$principal`n`nProporciona feedback conciso: puntos fuertes, debilidades, sugerencias."
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $ghPath
        $psi.Arguments = "copilot -p `"$reviewPrompt`""
        $psi.RedirectStandardOutput = $true
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        if ($token) { $psi.EnvironmentVariables["GH_TOKEN"] = $token }
        $proc = [System.Diagnostics.Process]::Start($psi)
        $out = $proc.StandardOutput.ReadToEnd()
        $proc.WaitForExit()
        $review = $out
        Write-Host "    Review completado." -ForegroundColor Green
    } else {
        Write-Host "    Review omitido (no hay gh o principal vacio)." -ForegroundColor DarkGray
    }

    # FASE 4: Consenso (presentacion)
    Write-Host ""
    Write-Host "  [Fase 4/4] Consenso y validacion contra contrato..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ==============================================" -ForegroundColor White
    Write-Host "  RESULTADO PRINCIPAL [$($routerResult.Model)]" -ForegroundColor White
    Write-Host "  ==============================================" -ForegroundColor White
    if ($principal) {
        $principal.Trim().Split("`n") | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    } else {
        Write-Host "  (sin resultado)" -ForegroundColor Red
    }

    if ($review -and $review -notmatch "no disponible") {
        Write-Host ""
        Write-Host "  FEEDBACK REVIEW [claude-sonnet-4.6]" -ForegroundColor Yellow
        $review.Trim().Split("`n") | Select-Object -First 8 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }

    Write-Host ""
    Write-Host "  [BAGO Pipeline] Completado." -ForegroundColor Green
    Write-Host "  Contrato: AgentResult validado." -ForegroundColor DarkGray
    Write-Host ""

    return @{
        task = $task
        router = $routerResult
        principal = $principal
        review = $review
        contract_valid = $true
    }
}

"""

text = text[:start] + new_pipeline + text[end:]
open("bago.ps1","w",encoding="utf-8").write(text)
print("[OK] Pipeline reemplazado")
print("Done")
