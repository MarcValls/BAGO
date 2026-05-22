@echo off
:: bago.cmd - BAGO Launcher para Windows (wrapper del launcher Python canonico)
:: Instalar en PATH: C:\Users\{user}\BAGO\ o C:\Program Files\BAGO\
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bago.ps1" %*
exit /b %ERRORLEVEL%
