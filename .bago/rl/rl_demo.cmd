@echo off
:: rl_demo.cmd — Demo rápido del pipeline RL (doble-click para probar)
:: Simula un mini-workflow de 3 pasos y verifica que todo el pipeline RL funciona.

cd /d "%~dp0..\.."
echo [RL-Demo] Ejecutando demo manual de pipeline RL...
python .bago\rl\rl_demo_manual.py

echo.
echo [RL-Demo] Verificando transiciones acumuladas...
powershell -Command "try { $n=(Get-Content '.bago\logs\rl_transitions.jsonl').Count; Write-Host \"Total transiciones acumuladas: $n\" -ForegroundColor Green } catch { Write-Host 'Aun sin transiciones. Ejecuta de nuevo.' -ForegroundColor Yellow }"

echo.
pause
