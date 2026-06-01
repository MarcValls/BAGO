@echo off
:: bago-cpp-local.cmd — Wrapper cmd que delega en el stub python.
:: Usado por `bago-cpp-local` cuando se invoca desde PATH.
:: Ubicación esperada: scripts/bago-cpp-local.cmd (renombrable a bago-cpp-local.exe)
@echo off
setlocal
set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0bago_cpp_local.py" %*
endlocal
