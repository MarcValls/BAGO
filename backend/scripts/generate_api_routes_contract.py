from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / ".bago" / "api"
GABO_API_DIR = ROOT / ".gabo" / "api"
CONTRACT_PATH = ROOT / "contracts" / "api_routes.generated.json"
FRONTEND_CLIENT = ROOT.parent / "frontend" / "src" / "api" / "client.ts"

DYNAMIC_PREFIXES = (
    "/models/",
    "/files/read/",
    "/evidence/receipts/",
    "/evidence/claims/",
    "/jobs/",
    "/router/toggle/",
)


def _load_dispatch_meta(api_dir: Path) -> tuple[list[tuple[str, str, str, str]], tuple[str, ...]]:
    sys.path.insert(0, str(api_dir))
    try:
      mod = importlib.import_module("api_dispatch")
      importlib.reload(mod)
      return list(getattr(mod, "ROUTE_META", [])), tuple(getattr(mod, "API_PREFIXES", ()))
    finally:
      for key in list(sys.modules.keys()):
          if key == "api_dispatch" or key.startswith("handlers_"):
              sys.modules.pop(key, None)
      sys.path.remove(str(api_dir))


def _route_entry(method: str, path: str, handler_module: str, handler_fn: str) -> dict:
    return {
        "method": method,
        "path": path,
        "handler_module": handler_module,
        "handler_fn": handler_fn,
        "pattern": "<" in path,
    }


def _extract_frontend_endpoints(client_file: Path) -> set[str]:
    text = client_file.read_text(encoding="utf-8")
    matches = re.findall(r"request(?:<[^>]*>)?\('([^']+)'", text)
    matches += re.findall(r'fetch\(this\.url\(\'([^\']+)\'', text)
    matches += ["/api/v1" + item for item in re.findall(r'fetch\(this\.modernUrl\(\'([^\']+)\'', text)]
    return {item.split("?", 1)[0] for item in matches}


def build_contract() -> dict:
    route_meta, api_prefixes = _load_dispatch_meta(API_DIR)
    routes = [_route_entry(*entry) for entry in route_meta]
    dynamic_routes = [
        _route_entry("GET", "/models/<provider>", "handlers_models", "handle"),
        _route_entry("GET", "/files/read/<path:filepath>", "handlers_files", "handle_read"),
        _route_entry("GET", "/evidence/receipts/<receipt_id>", "handlers_evidence", "handle_receipt"),
        _route_entry("GET", "/evidence/claims/<claim_id>", "handlers_evidence", "handle_claim"),
        _route_entry("GET", "/jobs/<execution_id>", "handlers_jobs", "handle_get"),
        _route_entry("POST", "/jobs/<execution_id>/cancel", "handlers_jobs", "handle_cancel"),
        _route_entry("POST", "/jobs/<execution_id>/retry", "handlers_jobs", "handle_retry"),
        _route_entry("POST", "/router/toggle/<key>", "handlers_router", "handle_toggle"),
    ]
    return {
        "source": "backend/.bago/api/api_dispatch.py",
        "routes": routes,
        "dynamic_routes": dynamic_routes,
        "api_prefixes": list(api_prefixes),
    }


def write_contract(contract: dict) -> None:
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate(contract: dict) -> int:
    errors: list[str] = []
    route_index = {(entry["method"], entry["path"]) for entry in contract["routes"]}
    if not route_index:
        errors.append("no static routes found")

    try:
        gabo_meta, _ = _load_dispatch_meta(GABO_API_DIR)
    except Exception as exc:
        errors.append(f"could not load .gabo api_dispatch: {exc}")
        gabo_meta = []
    gabo_routes = {(method, path) for method, path, *_ in gabo_meta}
    missing_in_gabo = sorted(route_index - gabo_routes)
    if missing_in_gabo:
        errors.append(f".gabo missing routes: {missing_in_gabo[:10]}")

    frontend_endpoints = _extract_frontend_endpoints(FRONTEND_CLIENT) if FRONTEND_CLIENT.exists() else set()
    missing_frontend = []
    for method, path in sorted(route_index):
        if path in frontend_endpoints:
            continue
        if any(path.startswith(prefix) for prefix in DYNAMIC_PREFIXES):
            continue
        missing_frontend.append(f"{method} {path}")
    if missing_frontend:
        print(f"[routes-contract] frontend not referencing routes (warning): {missing_frontend[:10]}", file=sys.stderr)

    if errors:
        for item in errors:
            print(f"[routes-contract] {item}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate/validate the canonical API routes contract.")
    parser.add_argument("--check", action="store_true", help="Validate instead of writing the generated contract.")
    args = parser.parse_args(argv)
    contract = build_contract()
    if args.check:
        if not CONTRACT_PATH.exists():
            print(f"[routes-contract] missing contract file: {CONTRACT_PATH}", file=sys.stderr)
            return 1
        existing = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        if existing != contract:
            print(f"[routes-contract] generated contract differs from {CONTRACT_PATH}", file=sys.stderr)
            return 1
        return validate(contract)
    write_contract(contract)
    print(f"[routes-contract] wrote {CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
