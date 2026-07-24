@echo off
setlocal
set "BAGO_LAUNCHER_ROOT=%~dp0"
set "BAGO_UI_ROOT=%BAGO_LAUNCHER_ROOT%release\v4\current"

if not exist "%BAGO_UI_ROOT%\package.json" set "BAGO_UI_ROOT=%BAGO_LAUNCHER_ROOT%"
if not exist "%BAGO_UI_ROOT%\electron\main.cjs" set "BAGO_UI_ROOT=%BAGO_LAUNCHER_ROOT%"
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

set "ELECTRON_EXE=%BAGO_LAUNCHER_ROOT%node_modules\electron\dist\electron.exe"
if exist "%ELECTRON_EXE%" (
  start "" /min "%ELECTRON_EXE%" "%BAGO_UI_ROOT%"
  exit /b 0
)

set "BAGO_MANAGER_EXE=%LOCALAPPDATA%\Programs\BAGO Installation Manager\BAGO Installation Manager.exe"
if exist "%BAGO_MANAGER_EXE%" (
  start "" "%BAGO_MANAGER_EXE%"
  exit /b 0
)

echo No se encontro Electron local ni BAGO Installation Manager instalado.
echo Instala el Manager o ejecuta npm install desde "%BAGO_UI_ROOT%".
exit /b 1
