# Ejecutado como SYSTEM por BAGO
$output = @()
$output += "=== PERMISOS ACTUALES ==="
$output += (whoami)
$output += (whoami /priv)
$output += ""
$output += "=== ADAPTADORES DE RED ==="
$output += (Get-NetAdapter | Format-Table -AutoSize | Out-String)
$output += ""
$output += "=== INICIO DE CAPTURA DE PAQUETES (30s en Ethernet) ==="
$adapter = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceDescription -match 'Ethernet|Realtek|Intel.*Network' -and $_.Name -notmatch 'Wi-Fi|Wireless|vEthernet' } | Select-Object -First 1
$output += "Adaptador: $($adapter.Name) - $($adapter.InterfaceDescription)"

# Iniciar captura
$capFile = "C:\Marc_max_20gb\.bago\tools\capture.etl"
netsh trace start capture=yes traceFile="$capFile" maxSize=50 | Out-Null
Start-Sleep 10
netsh trace stop | Out-Null
$output += "Captura completada: $capFile"

$output | Set-Content "C:\Marc_max_20gb\.bago\tools\admin_output.txt" -Encoding UTF8
