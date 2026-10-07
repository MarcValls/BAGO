@echo off
setlocal
cd /d "%~dp0\.."
set "IA_MEMORY_ROOT=%CD%\memory_root"
set "IA_MEMORY_TRANSPORT=streamable-http"
set "IA_MEMORY_HOST=127.0.0.1"
set "IA_MEMORY_PORT=8765"
".venv\Scripts\python.exe" -m ia_memoria.server
