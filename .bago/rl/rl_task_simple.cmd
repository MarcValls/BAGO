@echo off
:: rl_task_simple.cmd — Tarea RL #1: Build + Test (Simple, ~30 seg)
:: Captura transiciones basicas de exito/fracaso de build y test.

cd /d "%~dp0..\.."
echo [RL-Task] Ejecutando: pipeline "build y test del proyecto"
echo [RL-Task] Sandbox activo. Cero riesgo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".bago\rl\bago_rl_launcher.ps1" pipeline "build y test del proyecto"

echo.
echo [RL-Task] Completado. Verificando transiciones capturadas...
powershell -Command "try { $n=(Get-Content '.bago\logs\rl_transitions.jsonl' -ErrorAction SilentlyContinue).Count; Write-Host \"[RL-Task] Total transiciones acumuladas: $n\" -ForegroundColor Green } catch { Write-Host '[RL-Task] Aun sin transiciones. Esto es normal si el pipeline no disparo hooks.' -ForegroundColor Yellow }"

echo.
echo [RL-Task] Si no hay transiciones, prueba el demo manual:
echo   .bago\rl\rl_demo.cmd
echo.
pause
