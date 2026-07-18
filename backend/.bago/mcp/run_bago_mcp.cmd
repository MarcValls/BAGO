@echo off
set BAGO_ROOT=C:\Users\AMTEC_Terminal_1º\bago_fw
set BAGO_PADRE_PATH=C:\Users\AMTEC_Terminal_1º\bago_fw
set BAGO_MCP_MODE=readonly
set BAGO_ALLOW_MUTATING=0
set BAGO_ALLOW_DANGEROUS=0
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d C:\Users\AMTEC_Terminal_1º\bago_fw
py -3 C:\Users\AMTEC_Terminal_1º\bago_fw\.bago\mcp\bago_mcp_server.py
