@echo off
setlocal
cd /d "%~dp0\.."
set "IA_MEMORY_ROOT=%CD%\memory_root"
".venv\Scripts\python.exe" scripts\smoke_test.py
if errorlevel 1 exit /b 1
echo Validacion posterior a instalacion completada.
