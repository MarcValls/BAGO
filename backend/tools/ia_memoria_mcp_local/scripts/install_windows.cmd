@echo off
setlocal
cd /d "%~dp0\.."
echo [1/5] Creando entorno virtual...
py -3 -m venv .venv || goto :error
echo [2/5] Activando entorno...
call .venv\Scripts\activate.bat || goto :error
echo [3/5] Instalando dependencias...
python -m pip install --upgrade pip || goto :error
pip install -e . || goto :error
echo [4/5] Inicializando memoria...
set "IA_MEMORY_ROOT=%CD%\memory_root"
set "IA_MEMORY_TRANSPORT=stdio"
ia-memoria-init || goto :error
echo [5/5] Diagnostico...
ia-memoria-doctor || goto :error
echo.
echo INSTALACION COMPLETADA
echo Comando: %CD%\.venv\Scripts\python.exe
echo Argumentos: -m ia_memoria.server
echo Variable: IA_MEMORY_ROOT=%CD%\memory_root
exit /b 0
:error
echo ERROR DURANTE LA INSTALACION
exit /b 1
