@echo off
setlocal
cd /d "%~dp0\.."
set "IA_MEMORY_ROOT=%CD%\memory_root"
".venv\Scripts\ia-memoria-reindex.exe"
