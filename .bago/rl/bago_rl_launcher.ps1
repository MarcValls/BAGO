#!/usr/bin/env pwsh
# bago_rl_launcher.ps1 — Lanza BAGO con RL instrumentation activa
#
# Uso:
#   .bago\rl\bago_rl_launcher.ps1 pipeline "refactorizar auth"
#   .bago\rl\bago_rl_launcher.ps1 build
#   .bago\rl\bago_rl_launcher.ps1 status
#
# Esto activa hooks + sandbox simulate + logging RL automático.

$ErrorActionPreference = "Stop"

# --- 1. Activar instrumentación RL ---
$env:BAGO_RL_INSTRUMENTATION = "1"

# --- 2. Preparar PYTHONPATH para imports RL ---
$scriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$rlDir        = Split-Path -Parent $scriptDir          # -> .bago
$rootDir      = Split-Path -Parent $rlDir               # -> C:\bago_true
$toolsDir     = Join-Path $rlDir "tools"
$adaptersDir  = Join-Path $rlDir "rl\adapters"
$trainingDir  = Join-Path $rlDir "rl\training"
$envsDir      = Join-Path $rlDir "rl\envs"

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$rootDir;$toolsDir;$adaptersDir;$trainingDir;$envsDir;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = "$rootDir;$toolsDir;$adaptersDir;$trainingDir;$envsDir"
}

# --- 3. Asegurar directorio de logs ---
$logDir = Join-Path $rlDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

Write-Host "[RL-Launcher] Instrumentación RL activa. Logs: $logDir\rl_transitions.jsonl" -ForegroundColor Cyan

# --- 4. Ejecutar BAGO con sandbox simulate ---
# Sandbox intercepta llamadas peligrosas durante el pipeline
if ($args.Count -eq 0) {
    Write-Host "[RL-Launcher] Sin argumentos. Ejecutando 'bago status' por defecto." -ForegroundColor Yellow
    Write-Host "[RL-Launcher] Uso: .bago\rl\bago_rl_launcher.ps1 <comando> [args]" -ForegroundColor DarkGray
    Write-Host "[RL-Launcher] Ejemplos: pipeline 'build y test' | status | build | knowledge sync" -ForegroundColor DarkGray
    $bagoArgs = @("status")
} else {
    $bagoArgs = $args
}

$pyCode = @"
import sys, os
root = r'$rootDir'
tools = r'$toolsDir'
adapters = r'$adaptersDir'
for p in [root, tools, adapters]:
    if p not in sys.path:
        sys.path.insert(0, p)

from bago_sandbox import BagoSandbox
sb = BagoSandbox(mode='simulate')
sb.activate()
print('[RL-Launcher] Sandbox activado (modo simulate).')
os.chdir(root)

# Luego lanzar el comando real de BAGO
import subprocess
cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
       root + r'\bago.ps1'] + sys.argv[1:]
result = subprocess.run(cmd)
sb.deactivate()
sys.exit(result.returncode)
"@
python -c $pyCode $bagoArgs
