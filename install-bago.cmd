@echo off
rem version=3.5.0b1
setlocal
set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%install.ps1" %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (
  echo.
  echo BAGO instalado. Si el comando "bago" no aparece, cierra y abre la terminal.
)
exit /b %RC%
