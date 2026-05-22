$out = [System.Collections.Generic.List[string]]::new()
$out.Add("TIME: $(Get-Date)")

# Instalar OpenSSH Server si no está instalado
$out.Add("=== OpenSSH Server ===")
$sshState = Get-WindowsCapability -Online -Name OpenSSH.Server* 2>&1
$out.Add("Estado: $sshState")

$installed = Get-WindowsCapability -Online -Name OpenSSH.Server* | Where-Object { $_.State -eq "Installed" }
if (-not $installed) {
    $out.Add("Instalando OpenSSH Server...")
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 2>&1 | ForEach-Object { $out.Add("  $_") }
} else {
    $out.Add("OpenSSH ya instalado")
}

# Iniciar servicio SSH
$out.Add("=== Iniciando SSH Server ===")
Start-Service sshd 2>&1 | ForEach-Object { $out.Add("  $_") }
Set-Service -Name sshd -StartupType Automatic 2>&1 | Out-Null

# Verificar que está corriendo
$svc = Get-Service sshd -ErrorAction SilentlyContinue
$out.Add("SSH service: $($svc.Status)")

# Habilitar firewall para SSH
netsh advfirewall firewall add rule name="OpenSSH Server" dir=in action=allow protocol=TCP localport=22 2>&1 | ForEach-Object { $out.Add("FW: $_") }

# Configurar para autenticación de contraseña
$sshConfig = "C:\ProgramData\ssh\sshd_config"
if (Test-Path $sshConfig) {
    $config = Get-Content $sshConfig
    # Asegurar que PasswordAuthentication está habilitado
    $config = $config -replace '#PasswordAuthentication yes', 'PasswordAuthentication yes'
    $config = $config -replace 'PasswordAuthentication no', 'PasswordAuthentication yes'
    Set-Content $sshConfig $config
    $out.Add("SSH config actualizada: PasswordAuthentication yes")
    Restart-Service sshd -Force 2>&1 | Out-Null
    $out.Add("SSH reiniciado")
}

# Habilitar Network Discovery en todos los perfiles
$out.Add("=== Network Discovery en todos perfiles ===")
Get-NetFirewallRule -DisplayGroup "Network Discovery" | Enable-NetFirewallRule 2>&1 | Out-Null
$out.Add("Network Discovery habilitado")

# Habilitar File Sharing
Get-NetFirewallRule -DisplayGroup "File and Printer Sharing" | Enable-NetFirewallRule 2>&1 | Out-Null
$out.Add("File Sharing habilitado")

# Resumen acceso SSH
$out.Add("")
$out.Add("=== Para conectar al Lenovo vía SSH desde Lenovo hacia aquí ===")
$out.Add("ssh paola@169.254.31.155")
$out.Add("Contraseña: la del usuario paola en este PC")

$out | Set-Content "C:\Marc_max_20gb\.bago\tools\admin_output.txt" -Encoding UTF8
