@echo off
:: rl_task_medium.cmd — Tarea RL #2: Knowledge Sync + Refactor (Medio, ~2 min)
:: Captura decisiones del router de herramientas y ajustes de parametros.

cd /d "%~dp0..\.."
echo [RL-Task] Fase 1: knowledge sync
echo [RL-Task] Sandbox activo. Cero riesgo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".bago\rl\bago_rl_launcher.ps1" knowledge sync

echo.
echo [RL-Task] Fase 2: pipeline "refactorizar modulo CLI con manejo de errores"
powershell -NoProfile -ExecutionPolicy Bypass -File ".bago\rl\bago_rl_launcher.ps1" pipeline "refactorizar modulo CLI con manejo de errores"

echo.
echo [RL-Task] Completado. Verificando transiciones capturadas...
powershell -Command "try { $n=(Get-Content '.bago\logs\rl_transitions.jsonl' -ErrorAction SilentlyContinue).Count; Write-Host \"[RL-Task] Total transiciones acumuladas: $n\" -ForegroundColor Green } catch { Write-Host '[RL-Task] Aun sin transiciones. Esto es normal si el pipeline no disparo hooks.' -ForegroundColor Yellow }"

echo.
echo [RL-Task] Si no hay transiciones, prueba el demo manual:
echo   .bago\rl\rl_demo.cmd
echo.
pause
