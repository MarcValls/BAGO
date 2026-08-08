@echo off
setlocal enabledelayedexpansion

echo ===============================================
echo BAGO 4.8.2 Installer Builder (Batch)
echo ===============================================
echo.

REM Verificar NSIS
set MAKENSIS=
if exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    set "MAKENSIS=C:\Program Files (x86)\NSIS\makensis.exe"
)
if exist "C:\Program Files\NSIS\makensis.exe" (
    set "MAKENSIS=C:\Program Files\NSIS\makensis.exe"
)

if not defined MAKENSIS (
    echo ERROR: NSIS makensis.exe no encontrado
    echo.
    echo Soluciones:
    echo 1. Instala NSIS desde: https://nsis.sourceforge.io/Download
    echo 2. O con chocolatey: choco install nsis -y
    echo.
    pause
    exit /b 1
)

echo [FOUND] NSIS: !MAKENSIS!
echo.

REM Verificar que estamos en releases/
if not exist "bago-installer-local.nsi" (
    echo ERROR: bago-installer-local.nsi no encontrado
    echo Ejecuta este script desde la carpeta releases/
    pause
    exit /b 1
)

REM Compilar NSIS
echo [1/2] Compilando NSIS...
echo Archivo: bago-installer-local.nsi
echo.

"!MAKENSIS!" /V4 "bago-installer-local.nsi"

if errorlevel 1 (
    echo.
    echo ERROR: NSIS compilation failed
    echo.
    pause
    exit /b 1
)

REM Verificar resultado
if not exist "bago-4.8.2-setup.exe" (
    echo.
    echo ERROR: bago-4.8.2-setup.exe no se creo
    pause
    exit /b 1
)

echo.
echo [2/2] Verificando...
for %%A in (bago-4.8.2-setup.exe) do (
    set "SIZE=%%~zA"
)

REM Convertir bytes a MB
set /a SIZE_MB=SIZE / 1048576
echo Archivo: bago-4.8.2-setup.exe
echo Tamaño: !SIZE_MB! MB

REM Calcular SHA256 (si certutil existe)
echo.
echo Calculando SHA256...
certutil -hashfile "bago-4.8.2-setup.exe" SHA256 > "bago-4.8.2-setup.exe.sha256"

echo.
echo ===============================================
echo ✓ LISTO PARA DISTRIBUCION
echo ===============================================
echo.
echo Archivo: bago-4.8.2-setup.exe
echo.
type "bago-4.8.2-setup.exe.sha256" | findstr /v "certutil"
echo.
echo Puedes subir bago-4.8.2-setup.exe a GitHub Releases
echo.
pause
