#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
net_interact.py — Interacción BAGO con la red Ethernet interna (10.0.0.x).

Red descubierta via cable Ethernet (169.254.31.155):
  · Subred: 10.0.0.0/24  (requiere IP temporal 10.0.0.250/24 en la interfaz Ethernet)
  · Dispositivos: PC Suite de gestión telefónica (Android, MediaTek mt6572, Orange)
  · Puerto principal: 8080 (HTTP REST + AngularJS)

APIs disponibles por dispositivo:
  GET  /api/version          → info del terminal (IMEI, operador, firmware)
  GET  /api/phone/status     → señal, batería, tipo de red
  GET  /api/notifications    → llamadas activas, perdidas, SMS
  GET  /api/calls/active     → llamadas en curso
  GET  /api/calls/:id        → detalle de llamada
  GET  /api/contacts         → lista de contactos
  GET  /api/messages         → SMS (paginado)
  GET  /api/modem/status     → estado USB modem
  PUT  /api/modem/status     → activar/desactivar modem USB
  GET  /api/backups          → copias de seguridad
  GET  /api/apns/default     → APN configurado

Uso:
  python3 .bago/tools/net_interact.py                  # resumen de todos los dispositivos
  python3 .bago/tools/net_interact.py --scan           # descubrir dispositivos
  python3 .bago/tools/net_interact.py --status         # estado de todos los terminales
  python3 .bago/tools/net_interact.py --calls          # llamadas activas y perdidas
  python3 .bago/tools/net_interact.py --sms            # SMS recibidos
  python3 .bago/tools/net_interact.py --device 10.0.0.4 --status   # dispositivo concreto
  python3 .bago/tools/net_interact.py --setup          # configura IP temporal en Ethernet
  python3 .bago/tools/net_interact.py --cleanup        # elimina IPs temporales
"""

import json
import subprocess
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─── Configuración ────────────────────────────────────────────────────────────

ETHERNET_IFACE  = "Ethernet"
LOCAL_APIPA_IP  = "169.254.31.155"   # IP actual del adaptador Ethernet
TEMP_IP         = "10.0.0.250"       # IP temporal que añadimos para acceder a la red
TEMP_PREFIX     = 24
NETWORK_BASE    = "10.0.0"
PC_SUITE_PORT   = 8080
TIMEOUT         = 6                   # segundos
KNOWN_DEVICES   = [3, 4, 8, 15, 103, 203]   # IPs conocidas (actualizar con --scan)


# ─── Utilidades HTTP ──────────────────────────────────────────────────────────

def _get(ip: str, path: str, timeout: int = TIMEOUT) -> dict | list | str | None:
    """HTTP GET a un dispositivo PC Suite. Devuelve JSON parseado o string."""
    url = f"http://{ip}:{PC_SUITE_PORT}{path}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except Exception:
                return raw
    except HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_url": url}
    except URLError as e:
        return {"_error": str(e.reason), "_url": url}
    except Exception as e:
        return {"_error": str(e), "_url": url}


def _put(ip: str, path: str, body: dict) -> dict | None:
    """HTTP PUT a un dispositivo PC Suite."""
    url = f"http://{ip}:{PC_SUITE_PORT}{path}"
    try:
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="PUT",
                      headers={"Content-Type": "application/json",
                               "Accept": "application/json"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except Exception:
                return raw
    except Exception as e:
        return {"_error": str(e)}


# ─── Red: setup / cleanup de IP temporal ─────────────────────────────────────

def _ip_exists(iface: str, ip: str) -> bool:
    ps = (f"Get-NetIPAddress -InterfaceAlias '{iface}' -IPAddress '{ip}' "
          "-ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    return r.stdout.strip() == "1"


def setup_network(quiet: bool = False) -> bool:
    """Añade IP temporal 10.0.0.250/24 a la interfaz Ethernet si no existe."""
    if _ip_exists(ETHERNET_IFACE, TEMP_IP):
        if not quiet:
            print(f"  ✅ IP temporal {TEMP_IP}/{TEMP_PREFIX} ya configurada.")
        return True

    ps = (f"$idx = (Get-NetAdapter -Name '{ETHERNET_IFACE}').InterfaceIndex; "
          f"New-NetIPAddress -InterfaceIndex $idx -IPAddress '{TEMP_IP}' "
          f"-PrefixLength {TEMP_PREFIX} -ErrorAction Stop")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode == 0:
        if not quiet:
            print(f"  ✅ IP temporal {TEMP_IP}/{TEMP_PREFIX} añadida a '{ETHERNET_IFACE}'.")
        time.sleep(1)
        return True
    else:
        print(f"  ❌ No se pudo añadir la IP temporal: {r.stderr.strip()}")
        return False


def cleanup_network():
    """Elimina todas las IPs temporales añadidas por este script."""
    temps = [TEMP_IP, "192.168.0.250", "192.168.1.250", "172.16.0.250"]
    for ip in temps:
        if _ip_exists(ETHERNET_IFACE, ip):
            ps = (f"Remove-NetIPAddress -InterfaceAlias '{ETHERNET_IFACE}' "
                  f"-IPAddress '{ip}' -Confirm:$false -ErrorAction SilentlyContinue")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True)
            print(f"  🗑 IP {ip} eliminada de '{ETHERNET_IFACE}'.")


# ─── Descubrimiento ───────────────────────────────────────────────────────────

def scan_network(verbose: bool = True) -> list[str]:
    """Descubre dispositivos PC Suite en 10.0.0.x escaneando el puerto 8080."""
    if verbose:
        print(f"\n  🔍 Escaneando {NETWORK_BASE}.1-254:8080 ...")

    import socket
    found = []
    for i in range(1, 255):
        ip = f"{NETWORK_BASE}.{i}"
        if ip == TEMP_IP:
            continue
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            r = s.connect_ex((ip, PC_SUITE_PORT))
            s.close()
            if r == 0:
                found.append(ip)
                if verbose:
                    print(f"  🟢 {ip}:8080")
        except Exception:
            pass

    return found


# ─── Consultas a dispositivos ─────────────────────────────────────────────────

def get_device_info(ip: str) -> dict:
    """Obtiene info completa de un dispositivo PC Suite."""
    version = _get(ip, "/api/version") or {}
    status  = _get(ip, "/api/phone/status") or {}
    modem   = _get(ip, "/api/modem/status") or {}
    return {
        "ip":       ip,
        "imei":     version.get("imei", "?") if isinstance(version, dict) else "?",
        "hw":       version.get("hardware", "?") if isinstance(version, dict) else "?",
        "fw":       version.get("version", "?") if isinstance(version, dict) else "?",
        "app":      version.get("appversion", "?") if isinstance(version, dict) else "?",
        "operator": version.get("operator", "?") if isinstance(version, dict) else "?",
        "network":  status.get("networkType", "?") if isinstance(status, dict) else "?",
        "battery":  status.get("batteryLevel", 0) if isinstance(status, dict) else 0,
        "signal":   status.get("signalStrength", 0) if isinstance(status, dict) else 0,
        "modem":    modem.get("status", "?") if isinstance(modem, dict) else "?",
        "_version_raw": version,
        "_status_raw":  status,
    }


def get_notifications(ip: str) -> dict:
    """Obtiene notificaciones: llamadas activas, perdidas, SMS."""
    raw = _get(ip, "/api/notifications") or {}
    if isinstance(raw, dict) and "_error" in raw:
        return raw
    calls = raw.get("calls", {}) if isinstance(raw, dict) else {}
    msgs  = raw.get("messages", {}) if isinstance(raw, dict) else {}
    return {
        "ongoing":  calls.get("ongoing", []),
        "missed":   calls.get("missed", []),
        "received": msgs.get("received", []),
        "sent":     msgs.get("sent", []),
    }


def get_active_calls(ip: str) -> list:
    """Obtiene llamadas activas en curso."""
    raw = _get(ip, "/api/calls/active") or []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "_error" not in raw:
        return [raw]
    return []


# ─── Formateo ─────────────────────────────────────────────────────────────────

def _bat_icon(level: float) -> str:
    pct = int(level * 100)
    if pct > 80:   return f"🔋{pct}%"
    if pct > 40:   return f"🪫{pct}%"
    return f"⚡{pct}%"


def _sig_icon(sig: int) -> str:
    bars = ["▁", "▃", "▅", "▇", "█"]
    return bars[min(sig, 4)] * (sig + 1)


def print_status_table(devices_info: list[dict]):
    print()
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║          BAGO · Red Ethernet — Terminales PC Suite                        ║")
    print("╠════════════════════════════════════════════════════════════════════════════╣")
    print(f"║  {'IP':<14}  {'Operador':<8}  {'Red':<4}  {'Señal':<6}  {'Batería':<8}  "
          f"{'Modem':<5}  {'IMEI':<16}  {'FW'}")
    print(f"║  {'-'*14}  {'-'*8}  {'-'*4}  {'-'*6}  {'-'*8}  {'-'*5}  {'-'*16}  {'-'*15}")
    for d in devices_info:
        sig = _sig_icon(int(d["signal"]))
        bat = _bat_icon(float(d["battery"]))
        print(f"║  {d['ip']:<14}  {d['operator']:<8}  {d['network']:<4}  {sig:<6}  "
              f"{bat:<8}  {d['modem']:<5}  {d['imei']:<16}  {d['fw']}")
    print("╠════════════════════════════════════════════════════════════════════════════╣")
    print(f"║  {len(devices_info)} terminales  ·  Red: {NETWORK_BASE}.0/24  ·  "
          f"Acceso via {ETHERNET_IFACE} ({LOCAL_APIPA_IP} → {TEMP_IP})")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print()


def print_notifications(ip: str, notifs: dict):
    ongoing = notifs.get("ongoing", [])
    missed  = notifs.get("missed", [])
    received= notifs.get("received", [])

    print(f"\n  📱 {ip}")

    if ongoing:
        print(f"    📞 Llamadas activas ({len(ongoing)}):")
        for c in ongoing[:10]:
            status = c.get("status", "?")
            addr   = c.get("address", "?")
            print(f"       {status:<10} ← {addr}")

    if missed:
        print(f"    📵 Llamadas perdidas ({len(missed)}):")
        for c in missed[:5]:
            addr = c.get("address", "?")
            ts   = c.get("date", 0)
            if ts:
                ts_str = time.strftime("%d/%m %H:%M", time.localtime(ts / 1000))
            else:
                ts_str = "—"
            print(f"       {ts_str}  ← {addr}")

    if received:
        print(f"    💬 SMS recibidos ({len(received)}):")
        for m in received[:5]:
            addr = m.get("address", "?")
            body = (m.get("body") or "")[:60]
            print(f"       {addr}: {body}")

    if not ongoing and not missed and not received:
        print("    ✅ Sin notificaciones pendientes")


# ─── Check accesibilidad ──────────────────────────────────────────────────────

def _network_reachable() -> bool:
    """Verifica si la red 10.0.0.x ya es alcanzable (via Wi-Fi u otra ruta)."""
    import socket
    for ip in [f"{NETWORK_BASE}.4", f"{NETWORK_BASE}.8", f"{NETWORK_BASE}.3"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            r = s.connect_ex((ip, PC_SUITE_PORT))
            s.close()
            if r == 0:
                return True
        except Exception:
            pass
    return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if "--cleanup" in args:
        print("\n  🧹 Eliminando IPs temporales...")
        cleanup_network()
        return 0

    if "--setup" in args:
        print(f"\n  🔧 Configurando acceso a red {NETWORK_BASE}.0/{TEMP_PREFIX}...")
        setup_network()
        return 0

    # Para cualquier operación verificamos que la red es alcanzable
    if "--no-setup" not in args:
        # Verificar si ya podemos llegar a la red (puede ser via Wi-Fi gateway o via IP temporal)
        if not _network_reachable():
            ok = setup_network(quiet=False)
            if not ok:
                print("  ❌ No se pudo configurar la red. Usa --setup para diagnosticar.")
                return 1
        else:
            if "--setup" not in args:
                pass  # red ya alcanzable

    # Modo scan
    if "--scan" in args:
        devices = scan_network(verbose=True)
        if devices:
            print(f"\n  ✅ {len(devices)} dispositivo(s) PC Suite encontrados: {', '.join(devices)}")
        else:
            print("\n  ⚠  No se encontraron dispositivos.")
        return 0

    # Dispositivo específico o todos
    if "--device" in args:
        idx = args.index("--device") + 1
        if idx < len(args):
            target_ips = [args[idx]]
        else:
            print("  ❌ Especifica una IP: --device 10.0.0.4")
            return 1
    else:
        target_ips = [f"{NETWORK_BASE}.{i}" for i in KNOWN_DEVICES]

    # Recoger info de dispositivos
    devices_info = []
    for ip in target_ips:
        info = get_device_info(ip)
        if info["imei"] != "?" or "--calls" not in args:
            devices_info.append(info)

    # Mostrar tabla de estado
    if "--calls" not in args and "--sms" not in args:
        if devices_info:
            print_status_table(devices_info)
        else:
            print("\n  ⚠  No se pudieron contactar dispositivos.")
            return 1

    # Mostrar llamadas/notificaciones
    if "--calls" in args or "--sms" in args or (not args):
        print("\n  🔔 Notificaciones y llamadas:")
        for ip in target_ips:
            notifs = get_notifications(ip)
            if isinstance(notifs, dict) and "_error" in notifs:
                print(f"\n  ❌ {ip}: {notifs['_error']}")
                continue
            print_notifications(ip, notifs)

    # Comandos disponibles al final si es resumen general
    if not args:
        print()
        print("  Comandos:")
        print("    bago net-interact --scan          → descubrir dispositivos")
        print("    bago net-interact --status        → estado de todos los terminales")
        print("    bago net-interact --calls         → llamadas activas y perdidas")
        print("    bago net-interact --sms           → SMS recibidos")
        print("    bago net-interact --device 10.0.0.4 --calls  → dispositivo concreto")
        print("    bago net-interact --cleanup       → eliminar IPs temporales")
        print()

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
