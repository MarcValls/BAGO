@echo off
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%.bago\tools\bago_dev_twin.py" %*
