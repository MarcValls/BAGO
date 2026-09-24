#!/usr/bin/env pwsh
param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

Set-Location $RepoRoot

$hooksPath = Join-Path $RepoRoot ".githooks"
if (!(Test-Path -LiteralPath $hooksPath)) {
    throw "No existe $hooksPath"
}

$requiredHooks = @("pre-commit", "pre-push")
foreach ($hook in $requiredHooks) {
    $hookPath = Join-Path $hooksPath $hook
    if (!(Test-Path -LiteralPath $hookPath)) {
        throw "Falta hook requerido: $hookPath"
    }
}

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    throw "$RepoRoot no es un worktree Git"
}

git config core.hooksPath ".githooks"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo configurar core.hooksPath"
}

Write-Output "core.hooksPath=.githooks configurado en $RepoRoot"
Write-Output "Hook activo: .githooks/pre-commit (sincroniza README truth projection)"
Write-Output "Hook activo: .githooks/pre-push (bloquea push directo a main/windows/android)"
