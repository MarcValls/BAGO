#!/usr/bin/env pwsh
# bago.ps1 â€” BAGO 4.1.5 PowerShell Entrypoint

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$BagoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BagoCore = Join-Path $BagoRoot "bago_core\cli.py"

if (-not (Test-Path $BagoCore)) {
    Write-Error "No se encontro bago_core\cli.py en $BagoRoot"
    exit 1
}

& python $BagoCore @args
