@echo off
setlocal
set "BAGO_UI_ROOT=%~dp0"
for %%I in ("%BAGO_UI_ROOT%.") do set "BAGO_UI_ROOT=%%~fI"

if not exist "%BAGO_UI_ROOT%\bago_core\launcher.py" (
  echo No se encontro %BAGO_UI_ROOT%\bago_core\launcher.py
  exit /b 1
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Set-Location -LiteralPath $env:BAGO_UI_ROOT; python -m bago_core.launcher manager --port 0"
