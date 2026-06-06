#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _run(command: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _get_adapters_windows() -> list[dict]:
    ps = (
        "Get-NetAdapter | ForEach-Object {"
        "$a = $_; $ip = (Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex "
        "-AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1);"
        "[PSCustomObject]@{"
        "Name=$a.Name; Desc=$a.InterfaceDescription; Status=$a.Status; "
        "LinkSpeed=$a.LinkSpeed; MediaConn=$a.MediaConnectionState; "
        "MAC=$a.MacAddress; IP=if($ip){$ip.IPAddress}else{''}; "
        "Prefix=if($ip){$ip.PrefixLength}else{0}"
        "}} | ConvertTo-Json -Depth 3"
    )
    result = _run(["powershell", "-NoProfile", "-Command", ps])
    raw = result.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    return [{
        "name": item.get("Name", "?"),
        "desc": item.get("Desc", ""),
        "status": item.get("Status", "?"),
        "link_speed": item.get("LinkSpeed", 0),
        "conn": item.get("MediaConn", "?"),
        "mac": item.get("MAC", "?"),
        "ip": item.get("IP", ""),
        "prefix": item.get("Prefix", 0),
    } for item in data]


def _get_adapters_linux() -> list[dict]:
    adapters: list[dict] = []
    try:
        result = _run(["ip", "-j", "address", "show"])
        data = json.loads(result.stdout or "[]")
    except Exception:
        data = []
    for item in data:
        ipv4 = next((entry for entry in item.get("addr_info", []) if entry.get("family") == "inet"), {})
        speed_file = Path("/sys/class/net") / item.get("ifname", "") / "speed"
        speed = 0
        try:
            speed = int(speed_file.read_text().strip()) * 1_000_000
        except Exception:
            pass
        adapters.append({
            "name": item.get("ifname", "?"),
            "desc": item.get("ifname", ""),
            "status": item.get("operstate", "unknown"),
            "link_speed": speed,
            "conn": item.get("operstate", "unknown"),
            "mac": item.get("address", "?"),
            "ip": ipv4.get("local", ""),
            "prefix": ipv4.get("prefixlen", 0),
        })
    if adapters:
        return adapters
    try:
        result = _run(["ifconfig"])
    except Exception:
        return []
    current: dict | None = None
    for line in result.stdout.splitlines():
        if line and not line.startswith(" ") and not line.startswith("\t"):
            if current:
                adapters.append(current)
            name = line.split(":", 1)[0].strip()
            current = {"name": name, "desc": name, "status": "unknown", "link_speed": 0, "conn": "unknown", "mac": "?", "ip": "", "prefix": 0}
        elif current and "inet " in line:
            parts = line.strip().split()
            if "inet" in parts:
                idx = parts.index("inet")
                if idx + 1 < len(parts):
                    current["ip"] = parts[idx + 1]
    if current:
        adapters.append(current)
    return adapters


def _get_adapters() -> list[dict]:
    try:
        if os.name == "nt":
            return _get_adapters_windows()
        return _get_adapters_linux()
    except Exception:
        return []


def _format_speed(value) -> str:
    if value in (None, "", 0, "0"):
        return "-"
    if isinstance(value, str):
        stripped = value.strip()
        if any(unit in stripped.lower() for unit in ("gbps", "mbps", "kbps", "bps")):
            return stripped
        value = stripped
    try:
        bps = int(value)
    except Exception:
        return str(value)
    if bps >= 1_000_000_000:
        return f"{bps // 1_000_000_000} Gbps"
    if bps >= 1_000_000:
        return f"{bps // 1_000_000} Mbps"
    if bps >= 1_000:
        return f"{bps // 1_000} Kbps"
    return f"{bps} bps"


def _cable_icon(adapter: dict) -> str:
    conn = str(adapter.get("conn", "")).lower()
    status = str(adapter.get("status", "")).lower()
    if conn in {"connected", "up"} or status == "up":
        return "UP"
    if conn in {"disconnected", "down"} or status == "disconnected":
        return "DOWN"
    return "UNK"


def _is_apipa(ip: str) -> bool:
    return str(ip).startswith("169.254.")


def _get_arp_neighbors_windows(iface: str | None = None) -> list[dict]:
    filter_part = f"-InterfaceAlias '{iface}'" if iface else ""
    ps = (
        f"Get-NetNeighbor {filter_part} | "
        "Where-Object { $_.State -notin @('Permanent','Unreachable') -and "
        "  $_.LinkLayerAddress -ne 'FF-FF-FF-FF-FF-FF' -and "
        "  $_.LinkLayerAddress -ne '00-00-00-00-00-00' } | "
        "Select-Object InterfaceAlias,IPAddress,LinkLayerAddress,State | ConvertTo-Json -Depth 2"
    )
    result = _run(["powershell", "-NoProfile", "-Command", ps])
    raw = result.stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    return [{"iface": item.get("InterfaceAlias", "?"), "ip": item.get("IPAddress", "?"), "mac": item.get("LinkLayerAddress", "?"), "state": item.get("State", "?")} for item in data]


def _get_arp_neighbors_linux() -> list[dict]:
    try:
        result = _run(["ip", "neigh", "show"])
    except Exception:
        return []
    neighbors: list[dict] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or "lladdr" not in parts:
            continue
        neighbors.append({
            "iface": parts[-1],
            "ip": parts[0],
            "mac": parts[parts.index("lladdr") + 1],
            "state": parts[-2],
        })
    return neighbors


def _get_arp_neighbors(iface: str | None = None) -> list[dict]:
    if os.name == "nt":
        return _get_arp_neighbors_windows(iface)
    return _get_arp_neighbors_linux()


def _ping_host(ip: str) -> None:
    if os.name == "nt":
        command = ["ping", "-n", "1", "-w", "250", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass


def _scan_subnet(ip: str, prefix: int) -> list[dict]:
    if not ip or prefix <= 0:
        return []
    network = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
    if network.num_addresses > 256:
        return []
    hosts = [str(host) for host in network.hosts()]
    with ThreadPoolExecutor(max_workers=32) as executor:
        list(executor.map(_ping_host, hosts))
    return _get_arp_neighbors()


def _resolve(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def _build_report(adapters: list[dict], do_scan: bool) -> dict:
    report = {"adapters": adapters, "neighbors": []}
    if do_scan:
        found: list[dict] = []
        for adapter in adapters:
            ip = adapter.get("ip", "")
            prefix = int(adapter.get("prefix", 0) or 0)
            if not ip:
                continue
            for neighbor in _scan_subnet(ip, prefix):
                neighbor = dict(neighbor)
                neighbor["hostname"] = _resolve(neighbor.get("ip", ""))
                neighbor["via"] = adapter.get("name", "")
                found.append(neighbor)
        report["neighbors"] = found
    return report


def _print_adapters(adapters: list[dict]) -> None:
    print("NET SCAN")
    if not adapters:
        print("No adapters found")
        return
    print(f"{'State':<6} {'Name':<20} {'Conn':<12} {'Speed':<10} {'IP':<18} MAC")
    for adapter in adapters:
        print(f"{_cable_icon(adapter):<6} {adapter.get('name','')[:20]:<20} {str(adapter.get('conn',''))[:12]:<12} {_format_speed(adapter.get('link_speed')):<10} {str(adapter.get('ip',''))[:18]:<18} {adapter.get('mac','')}")


def _print_neighbors(neighbors: list[dict]) -> None:
    print("LOCAL DEVICES")
    if not neighbors:
        print("No devices found")
        return
    print(f"{'Iface':<20} {'IP':<18} {'MAC':<20} {'State':<12} Hostname")
    for item in neighbors:
        print(f"{item.get('via') or item.get('iface',''):<20} {item.get('ip',''):<18} {item.get('mac',''):<20} {item.get('state',''):<12} {item.get('hostname','')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scans network adapters and local devices.")
    parser.add_argument("--root", default="", help="Unused portable root argument")
    parser.add_argument("--scan", action="store_true", help="Scan local subnet")
    parser.add_argument("--adapters", action="store_true", help="List adapters only")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--test", action="store_true", help="Run self tests")
    return parser


def run_self_tests() -> int:
    results = []
    results.append(_format_speed(1_000_000_000) == "1 Gbps")
    results.append(_format_speed(100_000_000) == "100 Mbps")
    results.append(_cable_icon({"conn": "Connected"}) == "UP")
    results.append(_is_apipa("169.254.10.20") is True)
    results.append(isinstance(_get_adapters(), list))
    passed = sum(1 for ok in results if ok)
    print(f"{passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test:
        return run_self_tests()
    adapters = _get_adapters()
    report = _build_report(adapters, do_scan=args.scan)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0
    _print_adapters(adapters)
    if args.scan:
        _print_neighbors(report["neighbors"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
