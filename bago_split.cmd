@echo off
:: bago_split.cmd — Abre BAGO Chat y un terminal vacio lado a lado.
:: Si tienes Windows Terminal instalado, usa paneles divididos automaticamente.
:: Si no, abre dos ventanas de PowerShell con instrucciones para dividirlas.

echo [BAGO-Split] Lanzando entorno dividido...

powershell -ExecutionPolicy Bypass -File "%~dp0bago_split.ps1" -BagoRoot "C:\bago_true" -ChatScript ".bago\tools\bago_chat.py"

if errorlevel 1 (
    echo [ERROR] No se pudo lanzar el entorno dividido.
    pause
)

