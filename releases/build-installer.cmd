@echo off
setlocal

rem Compatibility wrapper for the one canonical installer pipeline.
rem Do not invoke makensis or the removed local NSIS script directly.
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VERSION_FILE=%REPO_ROOT%\release_version.txt"
set "BUILD_SCRIPT=%SCRIPT_DIR%build-installer.ps1"

if not exist "%VERSION_FILE%" (
    echo ERROR: release_version.txt no encontrado en "%REPO_ROOT%"
    exit /b 1
)
if not exist "%BUILD_SCRIPT%" (
    echo ERROR: build-installer.ps1 no encontrado en "%SCRIPT_DIR%"
    exit /b 1
)

for /f "usebackq delims=" %%V in ("%VERSION_FILE%") do if not defined VERSION set "VERSION=%%V"
for /f "delims=" %%S in ('git -C "%REPO_ROOT%" rev-parse HEAD 2^>nul') do set "GIT_SHA=%%S"
for /f "delims=" %%R in ('git -C "%REPO_ROOT%" branch --show-current 2^>nul') do set "GIT_REF=%%R"

if not defined VERSION (
    echo ERROR: no se pudo resolver la version canonica
    exit /b 1
)
if not defined GIT_SHA (
    echo ERROR: no se pudo resolver el SHA del candidato
    exit /b 1
)
if not defined GIT_REF set "GIT_REF=local"

echo BAGO %VERSION% - pipeline canonico
echo Candidate: %GIT_SHA%
echo Ref: %GIT_REF%

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%" ^
    -Version "%VERSION%" ^
    -GitRef "%GIT_REF%" ^
    -GitSha "%GIT_SHA%"
exit /b %errorlevel%
