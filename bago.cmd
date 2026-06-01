@echo off
rem BAGO global launcher — despacha por sub-comando.
rem   bago              instalacion de trabajo (~/.bago, CLI = Program Files)
rem   bago des          plataforma de desarrollo (BAGO source)
rem   bago ign          plataforma de lanzamiento (BAGO install + launch/)
rem   bago sup ...      supervisor always-on (start|stop|status|attach)
rem   bago probe        health check unificado (1 proceso Python, sin rafagas)
rem   bago help         muestra ayuda
setlocal EnableExtensions
set "BAGO_USERHOME=%USERPROFILE%\.bago"
set "BAGO_SRC=%USERPROFILE%\BAGO"
set "BAGO_INST=C:\Program Files\BAGO"
set "BAGO_SCRIPTS=%USERPROFILE%\BAGO\scripts"

set "MODE=work"
set "REST="
set "SUBCMD="
if "%~1"=="" goto :dispatch
REM Llama al parser con un maximo de 9 args
call :parse_arg %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :dispatch

:parse_arg
if "%~1"=="" goto :eof
if defined SUBCMD goto :parse_add
if /I "%~1"=="des" set "MODE=dev"& shift /1& goto :parse_arg
if /I "%~1"=="ign" set "MODE=ign"& shift /1& goto :parse_arg
if /I "%~1"=="work" set "MODE=work"& shift /1& goto :parse_arg
if /I "%~1"=="sup" set "SUBCMD=sup"& shift /1& goto :parse_arg
if /I "%~1"=="probe" set "SUBCMD=probe"& shift /1& goto :parse_arg
if /I "%~1"=="help" call :do_help& goto :eof
if /I "%~1"=="/?" call :do_help& goto :eof
if /I "%~1"=="--help" call :do_help& goto :eof
goto :parse_add

:parse_add
if "%~1"=="" goto :eof
if defined REST (set "REST=%REST% %~1") else (set "REST=%~1")
shift /1
goto :parse_add

:dispatch
if defined SUBCMD (
    if /I "%SUBCMD%"=="probe" goto :do_probe
    if /I "%SUBCMD%"=="sup" goto :do_sup_dispatch
)
if "%MODE%"=="work" goto :do_work
if "%MODE%"=="dev"  goto :do_dev
if "%MODE%"=="ign"  goto :do_ign
echo bago: modo desconocido "%MODE%" 1>&2
exit /b 1

:do_probe
if not exist "%BAGO_SCRIPTS%\probe.py" (
    echo bago probe: no se encontro %BAGO_SCRIPTS%\probe.py 1>&2
    exit /b 1
)
python "%BAGO_SCRIPTS%\probe.py" %REST%
exit /b %ERRORLEVEL%

:do_sup_dispatch
REM %REST% contiene los args despues de `sup`
if not exist "%BAGO_SCRIPTS%\bago_supervisor.py" (
    echo bago sup: no se encontro %BAGO_SCRIPTS%\bago_supervisor.py 1>&2
    exit /b 1
)
pythonw "%BAGO_SCRIPTS%\bago_supervisor.py" %REST% >nul 2>nul
exit /b %ERRORLEVEL%

:do_work
set "CLI=%BAGO_INST%\bago_core\cli.py"
if not exist "%CLI%" set "CLI=%BAGO_USERHOME%\bago_core\cli.py"
if not exist "%CLI%" (echo bago: no se encontro cli.py para modo work 1>&2& exit /b 1)
python "%CLI%" --mode work %REST%
exit /b %ERRORLEVEL%

:do_dev
set "CLI=%BAGO_SRC%\bago_core\cli.py"
if not exist "%CLI%" (echo bago: no se encontro cli.py para modo dev 1>&2& exit /b 1)
python "%CLI%" --mode dev %REST%
exit /b %ERRORLEVEL%

:do_ign
set "CLI=%BAGO_INST%\bago_core\cli.py"
if not exist "%CLI%" (echo bago: no se encontro cli.py para modo ign 1>&2& exit /b 1)
python "%CLI%" --mode ign %REST%
exit /b %ERRORLEVEL%

:do_help
echo BAGO launcher (4.1.5)
echo   bago              Instalacion de trabajo [default]
echo   bago des          Plataforma de desarrollo
echo   bago ign          Plataforma de lanzamiento
echo   bago sup ^<verb^>  Supervisor always-on (start ^|^| stop ^|^| status ^|^| attach)
echo   bago probe        Health check unificado (sin rafagas)
echo   bago help         Esta ayuda
exit /b 0

endlocal
