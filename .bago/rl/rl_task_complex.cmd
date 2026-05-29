@echo off
:: rl_task_complex.cmd — Tarea RL #3: Deploy con Rollback (Complejo, ~3 min)
:: Captura secuencias largas con recovery de errores y multi-etapa.

cd /d "%~dp0..\.."
echo [RL-Task] Ejecutando pipeline complejo: "desplegar nueva feature con rollback automatico"
echo [RL-Task] Sandbox activo (simulate). Cero riesgo en disco/subprocesos.

powershell -NoProfile -ExecutionPolicy Bypass -File ".bago\rl\bago_rl_launcher.ps1" pipeline "desplegar nueva feature con rollback automatico"

echo.
echo [RL-Task] Completado. Verificando transiciones capturadas...
powershell -Command "try { $n=(Get-Content '.bago\logs\rl_transitions.jsonl' -ErrorAction SilentlyContinue).Count; Write-Host \"[RL-Task] Total transiciones acumuladas: $n\" -ForegroundColor Green } catch { Write-Host '[RL-Task] Aun sin transiciones. Esto es normal si el pipeline no disparo hooks.' -ForegroundColor Yellow }"

echo.
echo [RL-Task] Para entrenar cuando tengas ~200 transiciones:
echo   python .bago\rl\training\train_bc.py --input .bago\logs\rl_transitions.jsonl
echo   python .bago\rl\training\train_online.py --checkpoint-dir .bago\rl\checkpoints\ppo_user

echo [RL-Task] Si no hay transiciones aun, prueba el demo manual:
echo   .bago\rl\rl_demo.cmd

echo.
pause

