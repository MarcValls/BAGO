param($LenovoIP, $User = "lenovo", $Pass = "")

$out = [System.Collections.Generic.List[string]]::new()
$out.Add("=== BAGO AutoConnect a Lenovo: $LenovoIP ===")
$out.Add("TIME: $(Get-Date)")

# Intentar WinRM sin credenciales (si está en misma red confiable)
$out.Add("=== Intentando WinRM a $LenovoIP ===")
try {
    # Añadir a trusted hosts
    Set-Item WSMan:\localhost\Client\TrustedHosts -Value "$LenovoIP" -Force 2>&1 | Out-Null
    
    # Intentar sin credenciales primero (si usa autenticación de Windows)
    $session = New-PSSession -ComputerName $LenovoIP -ErrorAction Stop
    $out.Add("WinRM conectado! Session ID: $($session.Id)")
    
    # Obtener info del Lenovo
    $info = Invoke-Command -Session $session -ScriptBlock {
        @{
            Hostname = $env:COMPUTERNAME
            User = $env:USERNAME
            OS = (Get-WmiObject Win32_OperatingSystem).Caption
            IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'}).IPAddress -join ', '
            CPU = (Get-WmiObject Win32_Processor).Name
            RAM = [math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory/1GB, 1)
        }
    }
    $out.Add("=== INFO LENOVO ===")
    $info.GetEnumerator() | ForEach-Object { $out.Add("$($_.Key): $($_.Value)") }
    
    Remove-PSSession $session
} catch {
    $out.Add("WinRM sin creds falló: $($_.Exception.Message.Split([char]10)[0])")
    
    # Intentar con credenciales
    if ($Pass) {
        try {
            $secPass = ConvertTo-SecureString $Pass -AsPlainText -Force
            $cred = New-Object System.Management.Automation.PSCredential($User, $secPass)
            $session = New-PSSession -ComputerName $LenovoIP -Credential $cred -ErrorAction Stop
            $out.Add("WinRM con credenciales: CONECTADO!")
            Remove-PSSession $session
        } catch {
            $out.Add("WinRM con creds falló: $($_.Exception.Message.Split([char]10)[0])")
        }
    }
}

# Intentar SMB
$out.Add("")
$out.Add("=== SMB shares en $LenovoIP ===")
net view \\$LenovoIP 2>&1 | ForEach-Object { $out.Add("  $_") }

# Hostname via NetBIOS
$out.Add("")
$out.Add("=== Hostname NetBIOS ===")
nbtstat -A $LenovoIP 2>&1 | Select-Object -First 20 | ForEach-Object { $out.Add("  $_") }

$out | Set-Content "C:\Marc_max_20gb\.bago\tools\lenovo_connected.txt" -Encoding UTF8
$out | Write-Host
