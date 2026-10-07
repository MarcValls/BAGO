$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -e .
$env:IA_MEMORY_ROOT = (Join-Path (Get-Location) "memory_root")
$env:IA_MEMORY_TRANSPORT = "stdio"
& .\.venv\Scripts\ia-memoria-init.exe
& .\.venv\Scripts\ia-memoria-doctor.exe
Write-Host "Instalación completada."
