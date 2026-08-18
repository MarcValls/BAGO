@echo off
REM BAGO Windows uninstall entrypoint.
setlocal EnableDelayedExpansion

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "BAGO_ROOT=%~dp0"
set "BAGO_CORE=%BAGO_ROOT%bago_core\cli.py"

if not exist "%BAGO_CORE%" (
    echo [ERROR] No se encontro bago_core\cli.py en %BAGO_ROOT%
    exit /b 1
)

pushd "%BAGO_ROOT%"
python "%~dp0bago_core\cli.py" uninstall %*
set "EXITCODE=%ERRORLEVEL%"
popd
exit /b %EXITCODE%
