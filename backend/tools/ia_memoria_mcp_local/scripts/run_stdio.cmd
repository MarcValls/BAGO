@echo off
setlocal
cd /d "%~dp0\.."
set "IA_MEMORY_ROOT=%CD%\memory_root"
set "IA_MEMORY_TRANSPORT=stdio"
".venv\Scripts\python.exe" -m ia_memoria.server
