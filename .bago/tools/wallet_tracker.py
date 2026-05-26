#!/usr/bin/env python3
"""
wallet_tracker.py — BAGO Portfolio Tracker (READ-ONLY)

Lee precios de CoinGecko (gratis, sin auth) y muestra el valor
del portfolio definido en notify_config.json → "wallet".

⚠️  Este módulo NUNCA mueve fondos. Solo lectura.

Uso CLI:
  python3 wallet_tracker.py            # resumen de portfolio
  python3 wallet_tracker.py --json     # JSON crudo
  python3 wallet_tracker.py --add BTC 0.5   # añadir/actualizar holding
  python3 wallet_tracker.py --set-address solana <ADDR>  # wallet pública para leer saldo
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
import sys
import urllib.request
import urllib.parse
import ssl
from pathlib import Path
from datetime import datetime, timezone

CONFIG_PATH = Path(__file__).parent / "notify_config.json"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Mapa símbolo → id de CoinGecko
SYMBOL_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "USDT": "tether", "USDC": "usd-coin", "BNB": "binancecoin",
    "ADA": "cardano", "AVAX": "avalanche-2", "DOT": "polkadot",
    "MATIC": "matic-network", "LINK": "chainlink", "XRP": "ripple",
    "DOGE": "dogecoin", "LTC": "litecoin", "UNI": "uniswap",
    "OP": "optimism", "ARB": "arbitrum", "INJ": "injective-protocol",
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


def get_wallet_cfg() -> dict:
    cfg = load_config()
    return cfg.setdefault("wallet", {
        "holdings": {},      # {"BTC": 0.5, "ETH": 2.0, ...}
        "addresses": {},     # {"solana": "<ADDR>", ...}
        "currency": "eur",
        "alerts": []         # [{"coin": "BTC", "above": 90000}, ...]
    })


def coingecko_get(path: str, params: dict = None) -> dict:
    url = f"{COINGECKO_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BAGO/3.3"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def get_prices(symbols: list[str], currency: str = "eur") -> dict:
    """Devuelve {símbolo: precio_en_currency}"""
    ids = [SYMBOL_MAP.get(s.upper(), s.lower()) for s in symbols]
    data = coingecko_get("/simple/price", {
        "ids": ",".join(ids),
        "vs_currencies": currency,
        "include_24hr_change": "true",
        "include_market_cap": "true",
    })
    if "error" in data:
        return {}
    # Reverse map: id → symbol
    id_to_sym = {v: k for k, v in SYMBOL_MAP.items()}
    result = {}
    for coin_id, vals in data.items():
        sym = id_to_sym.get(coin_id, coin_id.upper())
        result[sym] = {
            "price":    vals.get(currency, 0),
            "change24": vals.get(f"{currency}_24h_change", 0),
            "mcap":     vals.get(f"{currency}_market_cap", 0),
        }
    return result


def portfolio_summary(currency: str = None) -> dict:
    """Calcula valor total del portfolio."""
    wcfg = get_wallet_cfg()
    currency = currency or wcfg.get("currency", "eur")
    holdings = wcfg.get("holdings", {})

    if not holdings:
        return {"total": 0, "currency": currency, "positions": [], "updated": datetime.now(datetime.timezone.utc).isoformat()}

    symbols = list(holdings.keys())
    prices = get_prices(symbols, currency)

    positions = []
    total = 0.0
    for sym, amount in holdings.items():
        info = prices.get(sym.upper(), {})
        price = info.get("price", 0)
        value = price * amount
        total += value
        positions.append({
            "symbol":    sym.upper(),
            "amount":    amount,
            "price":     price,
            "value":     value,
            "change24":  info.get("change24", 0),
        })

    # Sort by value desc
    positions.sort(key=lambda x: x["value"], reverse=True)

    return {
        "total":     total,
        "currency":  currency,
        "positions": positions,
        "updated":   datetime.now(timezone.utc).isoformat(),
    }


def format_summary(data: dict) -> str:
    """Formatea el portfolio para Telegram (MarkdownV2-safe plain text)."""
    cur = data["currency"].upper()
    total = data["total"]
    lines = [f"💰 Portfolio BAGO — {datetime.now(timezone.utc).strftime('%H:%M UTC')}", ""]

    if not data["positions"]:
        lines.append("Sin holdings configurados. Usa /cartera add BTC 0.5")
        return "\n".join(lines)

    for p in data["positions"]:
        arrow = "🟢" if p["change24"] >= 0 else "🔴"
        pct = f"{p['change24']:+.1f}%"
        lines.append(
            f"{arrow} {p['symbol']}: {p['amount']} × {p['price']:,.2f} {cur} = {p['value']:,.2f} {cur} ({pct})"
        )

    lines.append("")
    lines.append(f"📊 Total: {total:,.2f} {cur}")
    return "\n".join(lines)


def check_alerts(data: dict) -> list[str]:
    """Devuelve lista de alertas disparadas."""
    wcfg = get_wallet_cfg()
    alerts = wcfg.get("alerts", [])
    triggered = []
    prices_map = {p["symbol"]: p["price"] for p in data.get("positions", [])}
    for alert in alerts:
        sym = alert.get("coin", "").upper()
        price = prices_map.get(sym, 0)
        if "above" in alert and price > alert["above"]:
            triggered.append(f"🚨 {sym} por encima de {alert['above']:,} — precio actual: {price:,}")
        if "below" in alert and price < alert["below"]:
            triggered.append(f"🚨 {sym} por debajo de {alert['below']:,} — precio actual: {price:,}")
    return triggered


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--add" in args:
        idx = args.index("--add")
        sym, amount = args[idx+1].upper(), float(args[idx+2])
        cfg = load_config()
        cfg.setdefault("wallet", {}).setdefault("holdings", {})[sym] = amount
        save_config(cfg)
        print(f"✅ {sym}: {amount} guardado en portfolio")
        sys.exit(0)

    if "--set-address" in args:
        idx = args.index("--set-address")
        chain, addr = args[idx+1].lower(), args[idx+2]
        cfg = load_config()
        cfg.setdefault("wallet", {}).setdefault("addresses", {})[chain] = addr
        save_config(cfg)
        print(f"✅ Dirección {chain}: {addr[:8]}... guardada")
        sys.exit(0)

    if "--alert-above" in args:
        idx = args.index("--alert-above")
        sym, price = args[idx+1].upper(), float(args[idx+2])
        cfg = load_config()
        cfg.setdefault("wallet", {}).setdefault("alerts", []).append({"coin": sym, "above": price})
        save_config(cfg)
        print(f"✅ Alerta: {sym} > {price:,}")
        sys.exit(0)

    data = portfolio_summary()

    if "--json" in args:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_summary(data))
        alerts = check_alerts(data)
        for a in alerts:
            print(a)
