@echo off
:: bago.cmd — BAGO Launcher para Windows (wrapper de bago.ps1)
:: Instalar en PATH: C:\Users\{user}\BAGO\ o C:\Program Files\BAGO\
powershell -ExecutionPolicy Bypass -File "%~dp0bago.ps1" %*
