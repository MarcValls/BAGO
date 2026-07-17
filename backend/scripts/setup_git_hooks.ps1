#!/usr/bin/env pwsh
param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

Set-Location $RepoRoot

$hooksPath = Join-Path $RepoRoot ".githooks"
if (!(Test-Path -LiteralPath $hooksPath)) {
    throw "No existe $hooksPath"
}

git config core.hooksPath ".githooks"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo configurar core.hooksPath"
}

Write-Output "core.hooksPath=.githooks configurado en $RepoRoot"
Write-Output "Hook activo: .githooks/pre-push (bloquea push directo a main/windows/android)"
