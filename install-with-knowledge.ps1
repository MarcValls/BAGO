#!/usr/bin/env pwsh
# Wrapper: instala BAGO con knowledge sincronizable incluido.
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install-with-knowledge.ps1

& "$PSScriptRoot\install.ps1" @args
exit $LASTEXITCODE
