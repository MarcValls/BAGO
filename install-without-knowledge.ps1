#!/usr/bin/env pwsh
# Wrapper: instala BAGO sin knowledge sincronizable.
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install-without-knowledge.ps1

& "$PSScriptRoot\install.ps1" -NoKnowledge @args
exit $LASTEXITCODE
