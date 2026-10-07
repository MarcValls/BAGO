$ErrorActionPreference = 'Stop'
$probeDll = Join-Path $PSScriptRoot 'CredUiProbe\bin\Debug\net10.0-windows\CredUiProbe.dll'
$expectedHash = 'EC85540FF8043822CA04C9B31C71C04FEC9FB46CA653AB15CE6F0734665AED28'
if ((Get-FileHash -LiteralPath $probeDll -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'El binario ha cambiado. No se abre CredUI.'
}
Write-Host 'Prueba sin cambios en BAGO. Un intento de autenticacion local.'
Write-Host 'Introduce la cuenta local actual y su clave real SOLO en Windows.'
Write-Host 'No ejecutar como administrador. Puede generar auditoria; un fallo puede contar para bloqueo.'
& dotnet $probeDll --prompt
Write-Host ('El probe ha terminado. Exit: ' + $LASTEXITCODE)
Write-Host 'La ruta impresa contiene observations.json, sin credenciales.'
