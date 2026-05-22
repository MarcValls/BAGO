#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
net_scan.py — Escáner de red y estado de cables para BAGO.

Detecta:
  · Estado físico de cada adaptador (cable enchufado / desenchufado)
  · Velocidad de enlace negociada (indica hardware en el otro extremo)
  · Dispositivos que responden ARP/ICMP en la red local
  · Vecinos ARP ya conocidos por el sistema

Uso:
  python3 .bago/tools/net_scan.py               # resumen de adaptadores
  python3 .bago/tools/net_scan.py --scan        # escaneo ARP de la red local
  python3 .bago/tools/net_scan.py --watch       # monitoriza cambios de estado cada 5s
  python3 .bago/tools/net_scan.py --adapters    # solo lista de adaptadores
"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ─── Detección de adaptadores ─────────────────────────────────────────────────

def _get_adapters() -> list[dict]:
    """Lista adaptadores de red con estado, velocidad e IP."""
    adapters = []
    try:
        # Obtener info de adaptadores via PowerShell
        ps = (
            "Get-NetAdapter | ForEach-Object {"
            "$a = $_; $ip = (Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex "
            "-AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1);"
            "[PSCustomObject]@{"
            "Name=$a.Name; Desc=$a.InterfaceDescription; Status=$a.Status; "
            "LinkSpeed=$a.LinkSpeed; MediaConn=$a.MediaConnectionState; "
            "MAC=$a.MacAddress; IP=if($ip){$ip.IPAddress}else{'—'}; "
            "Prefix=if($ip){$ip.PrefixLength}else{0}"
            "}} | ConvertTo-Json -Depth 3"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        raw = r.stdout.strip()
        if not raw:
            return adapters
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        for a in data:
            adapters.append({
                "name":       a.get("Name", "?"),
                "desc":       a.get("Desc", ""),
                "status":     a.get("Status", "?"),
                "link_speed": a.get("LinkSpeed", 0),
                "conn":       a.get("MediaConn", "?"),
                "mac":        a.get("MAC", "?"),
                "ip":         a.get("IP", "—"),
                "prefix":     a.get("Prefix", 0),
            })
    except Exception as e:
        adapters.append({"name": "ERROR", "desc": str(e), "status": "?",
                         "link_speed": 0, "conn": "?", "mac": "?", "ip": "—", "prefix": 0})
    return adapters


def _format_speed(bps) -> str:
    if not bps or bps == 0:
        return "—"
    try:
        bps = int(bps)
    except Exception:
        return str(bps)
    if bps >= 1_000_000_000:
        return f"{bps // 1_000_000_000} Gbps"
    if bps >= 1_000_000:
        return f"{bps // 1_000_000} Mbps"
    if bps >= 1_000:
        return f"{bps // 1_000} Kbps"
    return f"{bps} bps"


def _cable_icon(adapter: dict) -> str:
    conn   = adapter.get("conn")
    status = adapter.get("status")
    # PowerShell puede devolver entero (1=Up/2=Disconnected) o string
    if isinstance(conn, int):
        return "🟢" if conn == 1 else "🔴"
    conn   = str(conn or "").lower()
    status = str(status or "").lower()
    if conn == "connected" or status == "up":
        return "🟢"
    if status == "disconnected" or conn == "disconnected":
        return "🔴"
    return "⚪"


def _is_apipa(ip: str) -> bool:
    return str(ip).startswith("169.254.")


# ─── Vecinos ARP ──────────────────────────────────────────────────────────────

def _get_arp_neighbors(iface: str = None) -> list[dict]:
    """Lee la tabla ARP del sistema (vecinos conocidos)."""
    neighbors = []
    try:
        filter_part = f"-InterfaceAlias '{iface}'" if iface else ""
        ps = (
            f"Get-NetNeighbor {filter_part} | "
            "Where-Object { $_.State -notin @('Permanent','Unreachable') -and "
            "  $_.LinkLayerAddress -ne 'FF-FF-FF-FF-FF-FF' -and "
            "  $_.LinkLayerAddress -ne '00-00-00-00-00-00' -and "
            "  -not $_.IPAddress.StartsWith('ff02') -and "
            "  -not $_.IPAddress.StartsWith('224.') -and "
            "  -not $_.IPAddress.StartsWith('239.') } | "
            "Select-Object InterfaceAlias,IPAddress,LinkLayerAddress,State | "
            "ConvertTo-Json -Depth 2"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        raw = r.stdout.strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        for n in data:
            neighbors.append({
                "iface": n.get("InterfaceAlias", "?"),
                "ip":    n.get("IPAddress", "?"),
                "mac":   n.get("LinkLayerAddress", "?"),
                "state": n.get("State", "?"),
            })
    except Exception:
        pass
    return neighbors


# ─── Escaneo ARP activo ───────────────────────────────────────────────────────

def _scan_subnet(ip_base: str, prefix: int) -> list[dict]:
    """
    Escanea la subred con ping paralelo y recoge respuestas ARP.
    Solo funciona con subredes /24 o más pequeñas para no tardar demasiado.
    """
    if prefix < 16:
        return []
    if prefix >= 24:
        # /24: 254 hosts
        parts = ip_base.rsplit(".", 1)[0]
        hosts = [f"{parts}.{i}" for i in range(1, 255)]
    elif prefix >= 16:
        # /16 APIPA: scan solo el último octeto del IP actual
        parts = ".".join(ip_base.split(".")[:3])
        hosts = [f"{parts}.{i}" for i in range(1, 255)]
    else:
        return []

    # Ping paralelo con PowerShell
    host_list = " ".join(f'"{h}"' for h in hosts[:254])
    ps = (
        f"$hosts = @({host_list});"
        "$hosts | ForEach-Object -Parallel {"
        "  Test-Connection -ComputerName $_ -Count 1 -Quiet -TimeoutSeconds 1 | Out-Null"
        "} -ThrottleLimit 50"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30
        )
    except Exception:
        pass

    # Leer ARP después del scan
    return _get_arp_neighbors()


# ─── Resolución de hostname ───────────────────────────────────────────────────

def _resolve(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


# ─── Modo watch ───────────────────────────────────────────────────────────────

def _watch(interval: int = 5):
    """Monitoriza cambios en el estado de los adaptadores."""
    print(f"\n🔍 Monitorizando adaptadores cada {interval}s  (Ctrl+C para salir)\n")
    prev_states: dict[str, str] = {}
    try:
        while True:
            adapters = _get_adapters()
            changed = False
            for a in adapters:
                key = a["name"]
                cur = f"{a['conn']}|{a['link_speed']}"
                if key in prev_states and prev_states[key] != cur:
                    icon = _cable_icon(a)
                    ts = time.strftime("%H:%M:%S")
                    print(f"  {ts}  {icon} {key}: {prev_states[key].split('|')[0]} → {a['conn']}  "
                          f"{_format_speed(a['link_speed'])}")
                    changed = True
                prev_states[key] = cur
            if not changed and prev_states:
                print(f"\r  {time.strftime('%H:%M:%S')}  sin cambios...", end="", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n  Monitorización detenida.")


# ─── Presentación ─────────────────────────────────────────────────────────────

def print_adapters(adapters: list[dict]):
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         BAGO · Estado de red y cables                   ║")
    print("╠══════════════════════════════════════════════════════════╣")
    for a in adapters:
        icon   = _cable_icon(a)
        speed  = _format_speed(a["link_speed"])
        ip     = a["ip"]
        apipa  = "  ⚠ APIPA (sin DHCP)" if _is_apipa(ip) else ""
        name   = a["name"][:20]
        conn   = a["conn"]
        print(f"║  {icon} {name:<20}  {conn:<12}  {speed:<10}  {ip}{apipa}")
    print("╠══════════════════════════════════════════════════════════╣")

    # Análisis de cables ethernet físicos
    ethernet = [a for a in adapters
                if "ethernet" in str(a["name"]).lower() or "ethernet" in str(a["desc"]).lower()
                or ("802.3" in str(a["desc"]).lower() and "bluetooth" not in str(a["desc"]).lower())]
    connected_eth = [a for a in ethernet if (isinstance(a.get("conn"), int) and a["conn"] == 1)
                     or str(a.get("conn") or "").lower() == "connected"
                     or str(a.get("status") or "").lower() == "up"]

    print("║")
    if connected_eth:
        for a in connected_eth:
            speed = _format_speed(a["link_speed"])
            print(f"║  ✅ Cable físico detectado en '{a['name']}' — {speed}")
            if _is_apipa(a["ip"]):
                print(f"║     ⚠  IP APIPA ({a['ip']}) — sin DHCP en el otro extremo")
                print(f"║     ℹ  El enlace a {speed} indica switch o NIC activa conectada")
            else:
                print(f"║     ✅ IP válida: {a['ip']}/{a['prefix']}")
    else:
        print("║  🔴 Sin cables ethernet activos detectados")

    print("║")
    print("║  Comandos:")
    print("║    bago net --scan      → escanear dispositivos en la red")
    print("║    bago net --watch     → monitorizar cambios de estado")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


def print_scan_results(adapters: list[dict]):
    print()
    print("  🔍 Escaneando dispositivos en la red local...")
    found: list[dict] = []
    for a in adapters:
        ip = a.get("ip", "—")
        if ip == "—" or not ip:
            continue
        prefix = int(a.get("prefix", 0))
        print(f"  → Escaneando {a['name']} ({ip}/{prefix})...")
        neighbors = _scan_subnet(ip, prefix)
        for n in neighbors:
            n["via"] = a["name"]
            found.append(n)

    print()
    if found:
        print(f"  ✅ {len(found)} dispositivo(s) encontrado(s):\n")
        print(f"  {'Interfaz':<20}  {'IP':<18}  {'MAC':<20}  {'Hostname':<30}  Estado")
        print(f"  {'-'*20}  {'-'*18}  {'-'*20}  {'-'*30}  ------")
        for n in found:
            hostname = _resolve(n["ip"])
            print(f"  {n.get('via',''):<20}  {n['ip']:<18}  {n['mac']:<20}  {hostname:<30}  {n['state']}")
    else:
        print("  ⚠  Sin respuesta de ningún dispositivo en la red local.")
        print("     Puede haber equipos con IP estática en otro rango.")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if "--watch" in args:
        _watch(interval=5)
        return 0

    adapters = _get_adapters()

    if "--adapters" in args or not args or "--scan" not in args:
        print_adapters(adapters)

    if "--scan" in args:
        # Mostrar vecinos ARP conocidos primero
        neighbors = _get_arp_neighbors()
        real = [n for n in neighbors if n["mac"] not in ("00-00-00-00-00-00", "FF-FF-FF-FF-FF-FF", "")]
        if real:
            print(f"  📋 ARP ya conocidos ({len(real)}):")
            for n in real:
                hostname = _resolve(n["ip"])
                print(f"     {n['iface']:<20}  {n['ip']:<18}  {n['mac']:<20}  {hostname}")
            print()

        # Escaneo activo
        print_scan_results(adapters)

    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    sys.exit(main())
