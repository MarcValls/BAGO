$logFile = "C:\Marc_max_20gb\.bago\tools\lenovo_monitor.log"
$ipFile = "C:\Marc_max_20gb\.bago\tools\lenovo_ip.txt"
Add-Content $logFile "=== Monitor v2 iniciado: $(Get-Date) ==="

# TCP Listener
try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, 4444)
    $listener.Start()
    Add-Content $logFile "Listener TCP 4444 OK"
} catch { Add-Content $logFile "Listener error: $_"; $listener = $null }

$start = Get-Date
$lenovoFound = $false

while (((Get-Date) - $start).TotalSeconds -lt 1800) {  # 30 min
    # TCP check
    if ($listener -and $listener.Pending()) {
        $client = $listener.AcceptTcpClient()
        $ip = $client.Client.RemoteEndPoint.Address.ToString()
        Add-Content $logFile "TCP CONEXION DE: $ip - $(Get-Date)"
        Set-Content $ipFile $ip
        $bytes = [Text.Encoding]::UTF8.GetBytes("BAGO:IP=$ip`r`n")
        $client.GetStream().Write($bytes, 0, $bytes.Length)
        $client.Close()
        if ($ip -ne "169.254.31.155") { $lenovoFound = $true }
    }
    
    # ARP check
    $arp = arp -a | Select-String "169\.254\." | 
           Where-Object { $_ -notmatch "ff-ff|01-00|224|239|169\.254\.31\.155" }
    if ($arp) {
        $ip = ($arp[0].Line -split '\s+' | Where-Object { $_ -match '169\.254\.' })[0]
        if ($ip -and -not (Test-Path $ipFile)) {
            Add-Content $logFile "ARP NUEVO: $ip - $(Get-Date)"
            Set-Content $ipFile $ip
            $lenovoFound = $true
        }
    }
    
    # Si encontramos el Lenovo, lanzar autoconnect
    if ($lenovoFound -and (Test-Path $ipFile)) {
        $lenovoIP = Get-Content $ipFile -First 1
        Add-Content $logFile "LANZANDO AUTOCONNECT A: $lenovoIP"
        & powershell.exe -ExecutionPolicy Bypass -File "C:\Marc_max_20gb\.bago\tools\bago_autoconnect.ps1" -LenovoIP $lenovoIP
        $lenovoFound = $false  # Reset para no reconectar continuamente
    }
    
    Start-Sleep 5
}

if ($listener) { $listener.Stop() }
Add-Content $logFile "Monitor v2 finalizado: $(Get-Date)"
