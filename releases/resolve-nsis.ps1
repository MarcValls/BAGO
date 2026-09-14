[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ToolsDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$expectedSha = "FCDCE3229717A2A148E7CDA0AB5BDB667F39D8FB33EDE1DA8DABC336BD5AD110"
$zip = Join-Path $ToolsDirectory "nsis-3.10.zip"
$extractRoot = Join-Path $ToolsDirectory "nsis-3.10"
$makensis = Join-Path $extractRoot "nsis-3.10\makensis.exe"

New-Item -ItemType Directory -Path $ToolsDirectory -Force | Out-Null
curl.exe --fail --location --retry 3 --output $zip "https://sourceforge.net/projects/nsis/files/NSIS%203/3.10/nsis-3.10.zip/download"
if ($LASTEXITCODE -ne 0) { throw "No se pudo descargar NSIS 3.10." }

$actualSha = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actualSha -ne $expectedSha) {
    throw "Checksum NSIS inválido. Esperado: $expectedSha, actual: $actualSha"
}

Expand-Archive -LiteralPath $zip -DestinationPath $extractRoot -Force
if (-not (Test-Path -LiteralPath $makensis)) {
    throw "NSIS 3.10 no contiene makensis.exe en la ubicación esperada."
}

Write-Output $makensis
