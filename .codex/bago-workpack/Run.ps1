param(
    [Parameter(Mandatory=$true)]
    [string]$Task,

    [string]$RepoRoot = ".",

    [string]$RunId = "manual",

    [string]$Extra = ""
)

$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ManifestPath = Join-Path $Here "manifest.json"
$RulesPath = Join-Path $Here "COMMON_RULES.md"

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI no está disponible en PATH."
}

$versionText = (& codex --version 2>$null | Out-String).Trim()
if ($versionText -match '(\d+\.\d+\.\d+)') {
    $installed = [version]$Matches[1]
    $required = [version]"0.144.0"
    if ($installed -lt $required) {
        throw "Codex CLI $installed detectado. GPT-5.6 requiere Codex CLI 0.144.0 o posterior."
    }
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$Entry = $Manifest.tasks | Where-Object { $_.id -eq $Task } | Select-Object -First 1
if (-not $Entry) {
    $valid = ($Manifest.tasks.id -join ", ")
    throw "Tarea desconocida '$Task'. Válidas: $valid"
}

if ($Entry.requires_extra -and [string]::IsNullOrWhiteSpace($Extra)) {
    throw "La tarea '$Task' modifica o verifica un alcance concreto y requiere -Extra con el trabajo aprobado."
}

$Repo = (Resolve-Path $RepoRoot).Path
if (-not (Test-Path (Join-Path $Repo ".git"))) {
    throw "RepoRoot no parece la raíz de un repositorio Git: $Repo"
}

$PromptPath = Join-Path $Here $Entry.prompt
$Rules = Get-Content $RulesPath -Raw
$Prompt = Get-Content $PromptPath -Raw

$ReportDir = Join-Path $Here ("reports\" + $RunId)
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$ReportPath = Join-Path $ReportDir ($Task + ".md")

$Context = @"

WORKPACK_CONTEXT
- RepoRoot: $Repo
- RunId: $RunId
- ReportsDir: $ReportDir
- TaskId: $Task
- RequiredAgent: $($Entry.agent)
- ConfiguredModel: $($Entry.model)
- ConfiguredReasoning: $($Entry.reasoning)
- Sandbox: $($Entry.sandbox)

EXTRA_INSTRUCTIONS
$Extra
"@

$FullPrompt = $Rules + "`n`n" + $Prompt + "`n`n" + $Context

Write-Host ""
Write-Host "BAGO CODEX WORKPACK"
Write-Host "Task:      $Task"
Write-Host "Agent:     $($Entry.agent)"
Write-Host "Model:     $($Entry.model)"
Write-Host "Reasoning: $($Entry.reasoning)"
Write-Host "Sandbox:   $($Entry.sandbox)"
Write-Host "Report:    $ReportPath"
Write-Host ""

$args = @(
    "exec",
    "-C", $Repo,
    "-m", $Entry.model,
    "-s", $Entry.sandbox,
    "-c", ("model_reasoning_effort='" + $Entry.reasoning + "'"),
    "-o", $ReportPath,
    "-"
)

$FullPrompt | & codex @args
if ($LASTEXITCODE -ne 0) {
    throw "Codex finalizó con exit code $LASTEXITCODE en la tarea $Task."
}

Write-Host ""
Write-Host "OK: $ReportPath"
