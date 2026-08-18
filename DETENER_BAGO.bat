@echo off
REM ============================================================
REM  DETENER BAGO
REM  Doble clic para parar backend + electron.
REM ============================================================

setlocal
cd /d "%~dp0"

title BAGO - Deteniendo...

echo.
echo ============================================
echo   BAGO - Deteniendo stack
echo ============================================
echo.

if not exist "%~dp0scripts\dev.ps1" (
    echo [ERROR] No se encontro scripts\dev.ps1.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" stop

echo.
echo ============================================
echo   BAGO detenido.
echo ============================================
echo.
pause

endlocal
