@echo off
setlocal

set "BAGO_ROOT=%~dp0.."
if not exist "%BAGO_ROOT%\bago.cmd" (
  echo No se encontro el lanzador raiz: "%BAGO_ROOT%\bago.cmd"
  exit /b 1
)

call "%BAGO_ROOT%\bago.cmd" %*
exit /b %ERRORLEVEL%
