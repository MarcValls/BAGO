param(
    [string]$RepoRoot = ".",
    [string]$RunId = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = Get-Date -Format "yyyyMMdd-HHmmss"
}

$Tasks = @(
    "00-preflight",
    "01-inventory",
    "02-architecture",
    "03-frontend",
    "04-backend",
    "05-contracts",
    "06-workspace",
    "07-features",
    "08-security",
    "09-tests-ci",
    "10-hygiene",
    "11-performance",
    "12-truth-authority",
    "13-synthesis",
    "14-refactor-plan"
)

Write-Host "BAGO AUDIT RUN: $RunId"
Write-Host "Repo: $RepoRoot"
Write-Host ""

foreach ($Task in $Tasks) {
    & (Join-Path $Here "Run.ps1") -Task $Task -RepoRoot $RepoRoot -RunId $RunId
}

Write-Host ""
Write-Host "AUDITORÍA FINALIZADA"
Write-Host "Informes: $(Join-Path $Here ('reports\' + $RunId))"
Write-Host "Síntesis: $(Join-Path $Here ('reports\' + $RunId + '\13-synthesis.md'))"
Write-Host "Plan:     $(Join-Path $Here ('reports\' + $RunId + '\14-refactor-plan.md'))"
