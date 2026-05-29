#!/usr/bin/env python3
"""

BAGO Lenovo Ethernet Connector
Conecta con el PC Lenovo por Ethernet directo (cable) usando WinRM/SMB
Uso: python lenovo_connect.py [IP_LENOVO]
     Si no se da IP, la detecta automáticamente via ARP
"""

import subprocess
import socket
import struct
import time
import os
import sys

from bago.ollama_runtime import DEFAULT_ALT_HTTP_PORT

from pathlib import Path

MONITOR_LOG = Path.home() / ".bago" / "tools" / "lenovo_monitor.log"
LENOVO_IP_FILE = Path.home() / ".bago" / "tools" / "lenovo_ip.txt"
# IP del propio adaptador Ethernet (APIPA).  Sobrescribible via env.
OUR_ETHERNET_IP = os.getenv("BAGO_OWN_ETHERNET_IP", "169.254.31.155")

def log(msg):
    print(f"[BAGO-LENOVO] {msg}")
    with open(MONITOR_LOG, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def get_lenovo_ip():
    """Detecta IP del Lenovo via ARP o archivo guardado"""
    if os.path.exists(LENOVO_IP_FILE):
        ip = open(LENOVO_IP_FILE).read().strip().split()[0]
        log(f"IP Lenovo del archivo: {ip}")
        return ip
    
    # ARP scan
    result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if '169.254.' in line and '169.254.31.155' not in line:
            parts = line.split()
            if parts and parts[0].startswith('169.254.'):
                ip = parts[0]
                log(f"IP Lenovo detectada por ARP: {ip}")
                return ip
    return None

def ping(ip, timeout=2):
    """Ping a una IP"""
    result = subprocess.run(['ping', '-n', '1', '-w', str(timeout*1000), ip],
                           capture_output=True, text=True)
    return result.returncode == 0

def check_port(ip, port, timeout=1):
    """Verifica si un puerto está abierto"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def scan_ports(ip):
    """Escanea puertos comunes en el Lenovo"""
    ports = {22: 'SSH', 23: 'Telnet', 80: 'HTTP', 135: 'WMI', 
             139: 'NetBIOS', 443: 'HTTPS', 445: 'SMB', 
             3389: 'RDP', 5985: 'WinRM', 5986: 'WinRM-HTTPS', DEFAULT_ALT_HTTP_PORT: 'HTTP-Alt'}
    open_ports = {}
    log(f"Escaneando puertos en {ip}...")
    for port, name in ports.items():
        if check_port(ip, port):
            open_ports[port] = name
            log(f"  ✓ {name} ({port})")
    return open_ports

def get_hostname_nbtstat(ip):
    """Obtiene hostname via NetBIOS"""
    result = subprocess.run(['nbtstat', '-A', ip], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if '<00>' in line and 'UNIQUE' in line:
            return line.split()[0].strip()
    return None

def winrm_connect(ip, username=None, password=None):
    """Intenta conectar via WinRM"""
    try:
        import winrm
        session = winrm.Session(ip, auth=(username or '', password or ''), 
                               transport='ntlm')
        result = session.run_cmd('hostname')
        return result.std_out.decode().strip()
    except ImportError:
        log("pywinrm no disponible - usando PowerShell")
        # Usar PowerShell para WinRM
        ps_cmd = f'Enter-PSSession -ComputerName {ip}'
        log(f"Comando para conectar: {ps_cmd}")
        return None
    except Exception as e:
        log(f"WinRM error: {e}")
        return None

def smb_list_shares(ip):
    """Lista shares SMB"""
    result = subprocess.run(['net', 'view', f'\\\\{ip}'], 
                           capture_output=True, text=True)
    return result.stdout

def interact_with_lenovo(ip):
    """Flujo principal de interacción con el Lenovo"""
    log(f"=== Iniciando interacción con Lenovo en {ip} ===")
    
    # 1. Ping
    if not ping(ip):
        log(f"ADVERTENCIA: {ip} no responde a ping (puede tener firewall)")
    else:
        log(f"Ping OK a {ip}")
    
    # 2. Hostname NetBIOS
    hostname = get_hostname_nbtstat(ip)
    if hostname:
        log(f"Hostname Lenovo: {hostname}")
    
    # 3. Puertos
    open_ports = scan_ports(ip)
    
    # 4. Según puertos disponibles, conectar
    if 5985 in open_ports:
        log("WinRM disponible - conectando...")
        hostname_winrm = winrm_connect(ip)
        if hostname_winrm:
            log(f"Conectado via WinRM - hostname: {hostname_winrm}")
    
    if 445 in open_ports:
        log("SMB disponible - listando shares...")
        shares = smb_list_shares(ip)
        log(f"Shares: {shares[:200]}")
    
    if 3389 in open_ports:
        log("RDP disponible")
        log(f"Conectar con: mstsc /v:{ip}")
    
    if 22 in open_ports:
        log("SSH disponible")
        log(f"Conectar con: ssh paola@{ip}")
    
    # Guardar resumen
    summary = {
        'ip': ip,
        'hostname': hostname,
        'ports': open_ports,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    import json
    with open(r"C:\Marc_max_20gb\.bago\tools\lenovo_status.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    log(f"Resumen guardado en lenovo_status.json")
    return summary

def wait_for_lenovo(timeout=600):
    """Espera a que el Lenovo aparezca en la red"""
    log(f"Esperando al Lenovo (timeout: {timeout}s)...")
    log(f"El Lenovo debe hacer ping a {OUR_ETHERNET_IP} o conectarse a :4444")
    
    start = time.time()
    while time.time() - start < timeout:
        ip = get_lenovo_ip()
        if ip:
            return ip
        
        # ARP scan rápido cada 10s
        result = subprocess.run(
            ['powershell', '-c', 'arp -a | Select-String "169.254" | Where-Object { $_ -notmatch "ff-ff|01-00|224|239|31.155" }'],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            log(f"ARP detectado: {result.stdout.strip()}")
            parts = result.stdout.strip().split()
            for p in parts:
                if p.startswith('169.254.'):
                    with open(LENOVO_IP_FILE, 'w') as f:
                        f.write(p)
                    return p
        
        time.sleep(10)
    
    return None

if __name__ == '__main__':
    if len(sys.argv) > 1:
        ip = sys.argv[1]
        log(f"IP proporcionada: {ip}")
    else:
        ip = get_lenovo_ip()
    
    if not ip:
        log("Lenovo no encontrado, esperando...")
        ip = wait_for_lenovo(300)
    
    if ip:
        result = interact_with_lenovo(ip)
        print(f"\n=== RESULTADO ===")
        print(f"Lenovo IP: {result['ip']}")
        print(f"Hostname: {result.get('hostname', 'desconocido')}")
        print(f"Puertos: {', '.join([f'{p}({n})' for p,n in result['ports'].items()])}")
    else:
        log("ERROR: Lenovo no encontrado después del timeout")
        log("SOLUCIÓN: Ejecutar en el Lenovo:")
        log("  1. netsh interface set interface 'Ethernet' admin=enabled")
        log("  2. netsh interface ip set address 'Ethernet' static 169.254.31.1 255.255.0.0")
        log("  3. ping 169.254.31.155")
        log("  4. Enable-PSRemoting -Force -SkipNetworkProfileCheck")
        sys.exit(1)
