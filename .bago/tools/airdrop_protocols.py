"""airdrop_protocols.py — Catálogo y detección de airdrops reclamables.

Modelo de seguridad:
- BAGO **nunca** tiene mnemonic/clave privada del usuario.
- BAGO **construye** mensajes de transacción y los **propone** al cliente
  (la miniapp), que los pasa a TonConnect; la wallet del usuario firma.
- Cero firma server-side. Cero custodia.

Tipos de airdrop:
- "passive": el protocolo envía a la address del usuario sin requerir
  acción. BAGO solo detecta llegada (vía scan de balance).
- "active": el usuario debe llamar a un método claim() del contrato del
  protocolo, gastando gas. BAGO construye la TX, el usuario firma.

Schema de cada protocolo (.bago/state/airdrop_protocols.json):
    {
      "id": "<slug-único>",
      "name": "<nombre legible>",
      "type": "passive" | "active",
      "claim_contract": "<address>",          # solo si type=active
      "claim_amount_ton": 0.05,               # gas estimado
      "claim_payload_b64": "te6...",          # opcional, body BOC en base64
      "claim_comment": "claim",               # opcional, alternativa a payload
      "eligibility_url": "https://...",       # GET ?address=... → JSON
      "eligibility_field": "amount",          # campo del JSON con el monto
      "info_url": "https://..."               # link público del proyecto
    }
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import ssl
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

CATALOG_PATH = Path(__file__).resolve().parents[1] / "state" / "airdrop_protocols.json"


def load_catalog() -> dict:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "protocols": []}


def list_protocols() -> list:
    return load_catalog().get("protocols", []) or []


def get_protocol(protocol_id: str) -> Optional[dict]:
    for p in list_protocols():
        if p.get("id") == protocol_id:
            return p
    return None


def _http_get(url: str, timeout: int = 8) -> Optional[dict]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "BAGO/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def check_eligibility(protocol: dict, address: str) -> dict:
    """Consulta si la address es elegible para el airdrop del protocolo.

    Returns:
        {"eligible": bool, "amount": float|None, "raw": dict|None, "error": str|None}
    """
    url_tpl = protocol.get("eligibility_url")
    if not url_tpl:
        return {"eligible": False, "amount": None, "raw": None,
                "error": "protocolo sin eligibility_url"}
    url = url_tpl.replace("{address}", urllib.parse.quote(address))
    raw = _http_get(url)
    if raw is None:
        return {"eligible": False, "amount": None, "raw": None,
                "error": "fallo http al verificar elegibilidad"}
    field = protocol.get("eligibility_field") or "amount"
    amount = raw.get(field)
    try:
        amount_f = float(amount) if amount is not None else 0.0
    except (TypeError, ValueError):
        amount_f = 0.0
    return {
        "eligible": amount_f > 0,
        "amount": amount_f if amount_f > 0 else None,
        "raw": raw,
        "error": None,
    }


def scan_claimable(address: str) -> list:
    """Devuelve la lista de airdrops reclamables para esta address.

    Cada item:
        {"protocol_id", "name", "type", "amount", "info_url",
         "claim_contract", "claim_amount_ton", "claim_payload_b64",
         "claim_comment"}
    """
    if not address:
        return []
    out = []
    for p in list_protocols():
        elig = check_eligibility(p, address)
        if not elig["eligible"]:
            continue
        out.append({
            "protocol_id":      p["id"],
            "name":             p.get("name", p["id"]),
            "type":             p.get("type", "active"),
            "amount":           elig["amount"],
            "info_url":         p.get("info_url"),
            "claim_contract":   p.get("claim_contract"),
            "claim_amount_ton": p.get("claim_amount_ton", 0.05),
            "claim_payload_b64": p.get("claim_payload_b64"),
            "claim_comment":    p.get("claim_comment"),
        })
    return out


def build_claim_transaction(protocol: dict) -> dict:
    """Construye un objeto Transaction para TonConnect sendTransaction().

    Spec: https://docs.ton.org/develop/dapps/ton-connect/transactions
    El cliente lo pasa tal cual a tonConnectUI.sendTransaction(tx).
    El usuario firma en su wallet — BAGO nunca firma.
    """
    if protocol.get("type") != "active":
        raise ValueError("Este protocolo es passive: no requiere claim transaction.")
    if not protocol.get("claim_contract"):
        raise ValueError("Protocolo sin claim_contract.")

    # amount en nanoton (1 TON = 1e9 nanoton)
    ton = float(protocol.get("claim_amount_ton") or 0.05)
    amount_nano = str(int(ton * 1_000_000_000))

    msg = {
        "address": protocol["claim_contract"],
        "amount":  amount_nano,
    }
    if protocol.get("claim_payload_b64"):
        msg["payload"] = protocol["claim_payload_b64"]
    elif protocol.get("claim_comment"):
        # Comment-only: el cliente puede convertir a payload o usarlo directo.
        msg["stateInit"] = None
        msg["_comment"] = protocol["claim_comment"]

    # validUntil: 5 minutos
    import time
    tx = {
        "validUntil": int(time.time()) + 300,
        "messages":   [msg],
    }
    return tx


# Demo opt-in para devs (no se muestra al usuario en producción).
# Activar con BAGO_AIRDROP_DEMO=1.
def is_demo_mode() -> bool:
    return os.environ.get("BAGO_AIRDROP_DEMO") == "1"


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

