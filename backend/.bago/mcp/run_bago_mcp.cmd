@echo off
setlocal
for %%I in ("%~dp0..\..") do set "BAGO_ROOT=%%~fI"
set "BAGO_PADRE_PATH=%BAGO_ROOT%"
set "BAGO_MCP_MODE=readonly"
set "BAGO_ALLOW_MUTATING=0"
set "BAGO_ALLOW_DANGEROUS=0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%BAGO_ROOT%" || exit /b 1
py -3 "%~dp0bago_mcp_server.py"
set "_BAGO_MCP_EXIT=%ERRORLEVEL%"
popd
exit /b %_BAGO_MCP_EXIT%
