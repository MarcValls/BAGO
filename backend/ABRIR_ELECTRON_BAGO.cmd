@echo off
setlocal
set "BAGO_UI_ROOT=%~dp0release\v4\current"
for %%I in ("%BAGO_UI_ROOT%.") do set "BAGO_UI_ROOT=%%~fI"

if not exist "%BAGO_UI_ROOT%\package.json" (
  echo No se encontro %BAGO_UI_ROOT%\package.json
  exit /b 1
)

if not exist "%BAGO_UI_ROOT%\electron\main.cjs" (
  echo No se encontro %BAGO_UI_ROOT%\electron\main.cjs
  exit /b 1
)

set "ELECTRON_EXE=%BAGO_UI_ROOT%\node_modules\electron\dist\electron.exe"
if exist "%ELECTRON_EXE%" (
  start "" /min "%ELECTRON_EXE%" "%BAGO_UI_ROOT%"
  exit /b 0
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Set-Location -LiteralPath $env:BAGO_UI_ROOT; npm run manager:dev"
