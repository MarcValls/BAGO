#!/usr/bin/env python3
"""
airdrop_scanner.py — BAGO Airdrop Scanner v1
Detecta airdrops cobrables en una TON wallet (Telegram Wallet).
READ-ONLY: consulta blockchain, no firma ni envía transacciones.

APIs usadas (todas gratuitas, sin auth):
  - tonapi.io  v2  — jetton balances, NFT, eventos
  - toncenter.com  — balance, transacciones recientes
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import ssl
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

CONFIG_PATH = Path(__file__).parent / "notify_config.json"

# ── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}

def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

def get_ton_address() -> Optional[str]:
    cfg = load_config()
    return cfg.get("wallet", {}).get("ton_address")

def set_ton_address(address: str):
    cfg = load_config()
    cfg.setdefault("wallet", {})["ton_address"] = address.strip()
    save_config(cfg)

# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 10) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "BAGO/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode())

# ── TON API calls ─────────────────────────────────────────────────────────────

def get_ton_balance(address: str) -> float:
    """Retorna balance TON en nanotons → TON."""
    try:
        data = _get(f"https://tonapi.io/v2/accounts/{urllib.parse.quote(address)}")
        nano = int(data.get("balance", 0))
        return nano / 1e9
    except Exception:
        return 0.0

def get_jetton_balances(address: str) -> list[dict]:
    """
    Retorna lista de jetton (tokens TON) en la wallet.
    Incluye tokens con balance > 0 (potenciales airdrops recibidos).
    """
    try:
        data = _get(f"https://tonapi.io/v2/accounts/{urllib.parse.quote(address)}/jettons?currencies=usd,eur&supported_extensions=custom_payload")
        balances = data.get("balances", [])
        result = []
        for b in balances:
            jetton = b.get("jetton", {})
            raw_balance = int(b.get("balance", "0"))
            decimals = jetton.get("decimals", 9)
            amount = raw_balance / (10 ** decimals)
            if amount <= 0:
                continue
            # Price
            price_usd = 0.0
            price_data = b.get("price", {})
            if price_data:
                price_usd = float(price_data.get("prices", {}).get("USD", 0) or 0)
            value_usd = amount * price_usd

            result.append({
                "symbol":    jetton.get("symbol", "?"),
                "name":      jetton.get("name", ""),
                "address":   jetton.get("address", ""),
                "amount":    amount,
                "decimals":  decimals,
                "price_usd": price_usd,
                "value_usd": value_usd,
                "image":     jetton.get("image", ""),
                "verified":  jetton.get("verification", "") == "whitelist",
            })
        result.sort(key=lambda x: x["value_usd"], reverse=True)
        return result
    except Exception as e:
        return [{"error": str(e)}]

def get_nft_balances(address: str) -> list[dict]:
    """Retorna NFTs en la wallet (posibles airdrops NFT)."""
    try:
        data = _get(f"https://tonapi.io/v2/accounts/{urllib.parse.quote(address)}/nfts?limit=50&indirect_ownership=false")
        items = data.get("nft_items", [])
        result = []
        for nft in items:
            collection = nft.get("collection", {})
            meta = nft.get("metadata", {})
            result.append({
                "name":        meta.get("name") or nft.get("address", "?"),
                "collection":  collection.get("name", "Unknown"),
                "address":     nft.get("address", ""),
                "verified":    collection.get("is_trust", False),
            })
        return result[:20]
    except Exception:
        return []

def get_recent_incoming(address: str, limit: int = 30) -> list[dict]:
    """
    Transacciones entrantes recientes — detecta airdrops por transferencias
    de tokens desconocidos o mensajes 'claim' / 'airdrop'.
    """
    try:
        data = _get(f"https://tonapi.io/v2/accounts/{urllib.parse.quote(address)}/events?limit={limit}&subject_only=true")
        events = data.get("events", [])
        airdrops = []
        keywords = {"airdrop", "claim", "reward", "giveaway", "gift", "free", "drop"}
        for ev in events:
            # Look for incoming jetton transfers with airdrop hints
            for action in ev.get("actions", []):
                atype = action.get("type", "")
                if atype == "JettonTransfer":
                    jt = action.get("JettonTransfer", {})
                    comment = (ev.get("event_description") or "").lower()
                    if any(kw in comment for kw in keywords):
                        jetton = jt.get("jetton", {})
                        airdrops.append({
                            "symbol":  jetton.get("symbol", "?"),
                            "amount":  int(jt.get("amount", "0")) / (10 ** jetton.get("decimals", 9)),
                            "comment": comment[:80],
                            "ts":      ev.get("timestamp", 0),
                        })
        return airdrops
    except Exception:
        return []

# ── Known airdrop claim URLs ──────────────────────────────────────────────────
# Mapa símbolo → URL de claim (actualizable)
KNOWN_CLAIM_URLS = {
    "NOT":   "https://notcoin.app",
    "DOGS":  "https://t.me/dogshouse_bot",
    "CATS":  "https://t.me/catizenbot",
    "HAMSTER": "https://hamster.t.me",
    "BLUM":  "https://t.me/BlumCryptoBot",
    "MAJOR": "https://t.me/major",
    "TOMARKET": "https://t.me/Tomarket_ai_bot",
    "CATI":  "https://t.me/catizenbot",
    "STON":  "https://app.ston.fi",
    "SCALE": "https://app.ston.fi",
}

# ── Main scan ─────────────────────────────────────────────────────────────────

def scan_airdrops(address: str) -> dict:
    """
    Escanea una wallet TON en busca de:
    - Jettons con valor (tokens recibidos / airdrops)
    - NFTs recibidos
    - Eventos recientes con keywords de airdrop
    """
    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")

    ton_balance = get_ton_balance(address)
    jettons     = get_jetton_balances(address)
    nfts        = get_nft_balances(address)
    recent      = get_recent_incoming(address)

    # Enrich jettons with claim URLs
    for j in jettons:
        sym = j.get("symbol", "").upper()
        if sym in KNOWN_CLAIM_URLS:
            j["claim_url"] = KNOWN_CLAIM_URLS[sym]

    # Total value
    total_usd = sum(j.get("value_usd", 0) for j in jettons if "error" not in j)

    return {
        "address":     address,
        "ton_balance": ton_balance,
        "jettons":     jettons,
        "nfts":        nfts,
        "recent_airdrops": recent,
        "total_usd":   total_usd,
        "ts":          ts,
        "scanned_at":  datetime.now(timezone.utc).isoformat(),
    }

# ── Formatters ────────────────────────────────────────────────────────────────

def format_airdrops(data: dict) -> str:
    lines = [f"🪂 Airdrops TON — {data['ts']}", f"📍 {data['address'][:12]}…{data['address'][-6:]}", ""]

    ton = data.get("ton_balance", 0)
    lines.append(f"💎 TON: {ton:.4f}")

    jettons = [j for j in data.get("jettons", []) if "error" not in j]
    if jettons:
        lines.append("")
        lines.append("🪙 Tokens en wallet:")
        for j in jettons[:10]:
            val = f" ≈ ${j['value_usd']:.2f}" if j['value_usd'] > 0.01 else ""
            verified = "✅" if j.get("verified") else "⚠️"
            claim = f" → {j['claim_url']}" if j.get("claim_url") else ""
            lines.append(f"  {verified} {j['symbol']}: {j['amount']:,.4f}{val}{claim}")
    else:
        lines.append("Sin tokens encontrados en esta wallet.")

    nfts = data.get("nfts", [])
    if nfts:
        lines.append("")
        lines.append(f"🖼 NFTs recibidos: {len(nfts)}")
        for n in nfts[:5]:
            v = "✅" if n.get("verified") else "⚠️"
            lines.append(f"  {v} {n['name']} ({n['collection']})")

    recent = data.get("recent_airdrops", [])
    if recent:
        lines.append("")
        lines.append("📨 Transferencias con keyword airdrop/claim:")
        for r in recent[:5]:
            lines.append(f"  {r['symbol']}: {r['amount']:.2f} — {r['comment']}")

    total = data.get("total_usd", 0)
    if total > 0:
        lines.append("")
        lines.append(f"💵 Valor total tokens: ${total:.2f}")

    return "\n".join(lines)

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="BAGO Airdrop Scanner")
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="Escanear wallet")
    p_scan.add_argument("address", nargs="?", help="TON address (o usa la configurada)")

    p_set = sub.add_parser("set", help="Guardar TON address")
    p_set.add_argument("address")

    p_show = sub.add_parser("show", help="Mostrar address configurada")

    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.cmd == "set":
        set_ton_address(args.address)
        print(f"✅ TON address guardada: {args.address}")
        return

    if args.cmd == "show":
        addr = get_ton_address()
        print(addr or "No configurada. Usa: python3 airdrop_scanner.py set <ADDRESS>")
        return

    # scan
    address = None
    if args.cmd == "scan" and hasattr(args, "address") and args.address:
        address = args.address
    else:
        address = get_ton_address()

    if not address:
        print("❌ No hay TON address configurada.")
        print("   Usa: python3 airdrop_scanner.py set <TU_TON_ADDRESS>")
        print("   O en el bot: /airdrop set <ADDRESS>")
        sys.exit(1)

    print(f"🔍 Escaneando {address[:12]}…")
    data = scan_airdrops(address)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_airdrops(data))



def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()