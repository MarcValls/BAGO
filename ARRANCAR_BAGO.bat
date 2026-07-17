@echo off
REM ============================================================
REM  ARRANCAR BAGO
REM  Doble clic para arrancar backend + frontend + electron.
REM  Para parar: usa DETENER_BAGO.bat o cierra esta ventana
REM  y ejecuta scripts\dev.ps1 stop
REM ============================================================

setlocal
cd /d "%~dp0"

title BAGO - Arrancando...

echo.
echo ============================================
echo   BAGO - Arrancando stack completo
echo ============================================
echo.

if not exist "%~dp0scripts\dev.ps1" (
    echo [ERROR] No se encontro scripts\dev.ps1.
    echo.
    pause
    exit /b 1
)

echo Usando PowerShell: scripts\dev.ps1
echo.

REM Arrancar stack (backend + build frontend + electron)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" start
set RC=%ERRORLEVEL%

echo.
if not %RC%==0 (
    echo [ERROR] dev.ps1 termino con codigo %RC%.
    echo Revisa los logs en .run\*.log
    echo.
    pause
) else (
    echo ============================================
    echo   BAGO arrancado correctamente
    echo   - Backend: http://127.0.0.1:8080
    echo   - Electron: ventana abierta
    echo.
    echo   Para detener, ejecuta DETENER_BAGO.bat
    echo   Logs: .run\*.log
    echo ============================================
    echo.
    pause
)

endlocal
