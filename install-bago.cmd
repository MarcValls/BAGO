@echo off
setlocal EnableDelayedExpansion

:: BAGO One-Click Installer v3.4.3
:: Doble click para instalar. Requiere Python 3.9+.

title BAGO Installer v3.4.3
echo.
echo  ===========================================
echo   BAGO Framework v3.4.3 ? Instalador Rapido
echo  ===========================================
echo.

:: --- Check Python ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    python3 --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo  [XX] Python 3.9+ no encontrado.
        echo.
        echo  Descarga e instala Python desde:
        echo  https://www.python.org/downloads/
        echo.
        echo  Asegurate de marcar "Add Python to PATH" durante la instalacion.
        echo.
        pause
        exit /b 1
    )
    set "PY_CMD=python3"
) else (
    set "PY_CMD=python"
)

for /f "tokens=2" %%v in ('%PY_CMD% --version') do set "PY_VER=%%v"
echo  [OK] Python: !PY_VER!

:: --- Download ---
set "ZIP_URL=https://github.com/MarcValls/BAGO/releases/download/v3.4.3/BAGO-3.4.1.zip"
set "INSTALL_DIR=%USERPROFILE%\BAGO"
set "ZIP_FILE=%TEMP%\BAGO-3.4.1.zip"

echo  [..] Descargando BAGO desde GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%ZIP_FILE%' -UseBasicParsing" >nul 2>&1

if not exist "%ZIP_FILE%" (
    echo  [XX] No se pudo descargar el paquete.
    echo  Comprueba tu conexion a internet.
    pause
    exit /b 1
)
echo  [OK] Descarga completa

:: --- Extract ---
if exist "%INSTALL_DIR%" (
    echo  [..] El directorio %INSTALL_DIR% ya existe. Reemplazando...
    rmdir /s /q "%INSTALL_DIR%" 2>nul
    timeout /t 1 /nobreak >nul
)

echo  [..] Extrayendo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%INSTALL_DIR%' -Force" >nul 2>&1

set "BAGO_ROOT=%INSTALL_DIR%\BAGO-3.4.1"
if not exist "%BAGO_ROOT%\bago" (
    echo  [XX] Extraccion fallida. Estructura inesperada.
    pause
    exit /b 1
)
echo  [OK] Extraido en %INSTALL_DIR%

:: --- Bootstrap state ---
echo  [..] Inicializando estado limpio...
%PY_CMD% "%BAGO_ROOT%\.bago\tools\bootstrap_state.py" "%BAGO_ROOT%"
if !errorlevel! neq 0 (
    echo  [XX] Fallo la inicializacion del estado.
    pause
    exit /b 1
)

:: --- Validate ---
echo  [..] Validando instalacion...
%PY_CMD% "%BAGO_ROOT%\bago" validate >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo  [XX] VALIDACION FALLIDA ? Instalacion abortada.
    echo  El paquete no cumple el contrato de instalacion limpia.
    echo  Reporta el problema en: https://github.com/MarcValls/BAGO/issues
    echo.
    pause
    exit /b 1
)
echo  [OK] Validacion completa

:: --- Encoding check ---
echo  [..] Verificando encoding...
%PY_CMD% "%BAGO_ROOT%\.bago\tools\encoding_guard.py" "%BAGO_ROOT%" >nul 2>&1
if !errorlevel! neq 0 (
    echo  [XX] Encoding check fallo.
    pause
    exit /b 1
)
echo  [OK] Encoding limpio

:: --- Alias PowerShell ---
set "PS_PROFILE=%USERPROFILE%\Documents\PowerShell\Microsoft.PowerShell_profile.ps1"
if not exist "%PS_PROFILE%" (
    set "PS_PROFILE=%USERPROFILE%\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"
)
if exist "%PS_PROFILE%" (
    findstr /C:"function bago" "%PS_PROFILE%" >nul 2>&1
    if !errorlevel! neq 0 (
        echo. >> "%PS_PROFILE%"
        echo # BAGO Framework v3.4.3 >> "%PS_PROFILE%"
        echo function bago { ^& %PY_CMD% "%BAGO_ROOT%\bago" @args } >> "%PS_PROFILE%"
        echo  [OK] Alias anadido al perfil PowerShell
    ) else (
        echo  [OK] Alias bago ya existe en PowerShell
    )
)

:: --- Alias CMD (opcional) ---
set "BAGO_CMD=%USERPROFILE%\bago.cmd"
echo @echo off > "%BAGO_CMD%"
echo %PY_CMD% "%BAGO_ROOT%\bago" %%* >> "%BAGO_CMD%"
echo  [OK] Comando rapido creado: %BAGO_CMD%

:: --- Resumen ---
echo.
echo  ===========================================
echo   BAGO v3.4.3 instalado correctamente
echo  ===========================================
echo.
echo   Directorio: %BAGO_ROOT%
echo   Comando:    bago ^(desde terminal^)
echo.
echo   Primeros pasos:
echo     1. Abre una terminal nueva
echo     2. Escribe: bago --version
echo     3. Escribe: bago help
echo.
pause
exit /b 0
