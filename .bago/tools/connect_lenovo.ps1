param([string]$LenovoIP)

$out = [System.Collections.Generic.List[string]]::new()
$out.Add("TIME: $(Get-Date)")
$out.Add("Intentando conectar a Lenovo en: $LenovoIP")

# 1. Ping
$out.Add("")
$out.Add("=== PING ===")
$p = New-Object System.Net.NetworkInformation.Ping
$r = $p.Send($LenovoIP, 2000)
$out.Add("Ping status: $($r.Status) RTT=$($r.RoundtripTime)ms")

# 2. ARP para obtener MAC
$out.Add("")
$out.Add("=== ARP (MAC del Lenovo) ===")
arp -a | ForEach-Object { $out.Add($_) }

# 3. NetBIOS - hostname y nombre de PC
$out.Add("")
$out.Add("=== NetBIOS (hostname) ===")
nbtstat -A $LenovoIP 2>&1 | ForEach-Object { $out.Add("  $_") }

# 4. Scan de puertos clave
$out.Add("")
$out.Add("=== Puertos abiertos ===")
@(22,23,80,135,139,443,445,3389,5985,5986,8080,9999) | ForEach-Object {
    $port = $_
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $ar = $tcp.BeginConnect($LenovoIP, $port, $null, $null)
        $ok = $ar.AsyncWaitHandle.WaitOne(800, $false)
        if ($ok -and $tcp.Connected) {
            $out.Add("  ABIERTO: $LenovoIP`:$port")
        }
        $tcp.Close()
    } catch {}
}

# 5. SMB shares
$out.Add("")
$out.Add("=== SMB Shares ===")
try {
    $shares = net view \\$LenovoIP 2>&1
    $shares | ForEach-Object { $out.Add("  $_") }
} catch { $out.Add("  SMB: $_") }

# 6. WinRM
$out.Add("")
$out.Add("=== WinRM test ===")
try {
    $ws = Test-WSMan -ComputerName $LenovoIP -ErrorAction Stop
    $out.Add("  WinRM OK: $($ws.ProductVendor) $($ws.ProductVersion)")
} catch { $out.Add("  WinRM: $($_.Exception.Message.Split([char]10)[0])") }

$out | Set-Content "C:\Marc_max_20gb\.bago\tools\admin_output.txt" -Encoding UTF8
