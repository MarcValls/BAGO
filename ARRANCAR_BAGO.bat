@echo off
REM ============================================================
REM  ARRANCAR BAGO
REM  Doble clic para arrancar BAGO.
REM  Cerrar la ventana de BAGO detiene el backend automaticamente.
REM ============================================================

setlocal
cd /d "%~dp0"

if not exist "%~dp0scripts\bago-launcher.ps1" (
    echo [ERROR] No se encontro scripts\bago-launcher.ps1.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bago-launcher.ps1"

endlocal
