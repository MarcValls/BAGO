#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

BAGO_ROOT = Path(__file__).resolve().parents[2]

for _path in (
    BAGO_ROOT / "bago_core",
    BAGO_ROOT / ".bago" / "core",
    BAGO_ROOT / ".bago" / "chat",
    BAGO_ROOT / ".bago" / "providers",
    BAGO_ROOT / ".bago" / "api",
    BAGO_ROOT / ".bago" / "tools",
):
    _path_s = str(_path)
    if _path_s not in sys.path:
        sys.path.insert(0, _path_s)

from version import CURRENT as _BAGO_VERSION

def cmd_claim(args: argparse.Namespace) -> int:
    """Gestiona el Claim Evidence Ledger."""
    sys.path.insert(0, str(BAGO_ROOT / "bago_core"))
    from claim_ledger import _cli as claim_cli
    # Reconstruir argv para claim_ledger
    argv: list[str] = ["--base-path", args.base_path]
    if args.claim_action:
        argv.append(args.claim_action)
        if args.claim_action == "add":
            argv += ["--claim", args.claim_text, "--basis", args.basis]
            if args.command:
                argv += ["--command", args.command]
            if args.artifacts:
                argv += ["--artifacts", args.artifacts]
            if args.limits:
                argv += ["--limits", args.limits]
            if args.status_val:
                argv += ["--status", args.status_val]
            if args.stdout_val:
                argv += ["--stdout", args.stdout_val]
            if args.notes:
                argv += ["--notes", args.notes]
        elif args.claim_action == "verify":
            argv.append(args.claim_id)
        elif args.claim_action == "list":
            if args.filter_status:
                argv += ["--status", args.filter_status]
    return claim_cli(argv)

def cmd_config(args: argparse.Namespace) -> int:
    import sys
    sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
    from config_manager import ConfigManager
    from credential_manager import CredentialManager

    cm = ConfigManager(base_path=args.base_path)
    creds = CredentialManager(base_path=args.base_path)

    if args.config_cmd == "set":
        if not args.key:
            print("Uso: bago config set <clave> <valor>")
            return 1
        val = " ".join(args.value) if hasattr(args, "value") and args.value else ""
        # Intentar parsear bool/numeric
        if val.lower() in ("true", "yes", "1"):
            val_parsed: Any = True
        elif val.lower() in ("false", "no", "0"):
            val_parsed = False
        else:
            try:
                val_parsed = int(val)
            except ValueError:
                try:
                    val_parsed = float(val)
                except ValueError:
                    val_parsed = val
        cm.set(args.key, val_parsed)
        print(f"✓ {args.key} = {val_parsed}")
        return 0

    if args.config_cmd == "get":
        if not args.key:
            print("Uso: bago config get <clave>")
            return 1
        print(cm.get(args.key, "(no definido)"))
        return 0

    if args.config_cmd == "list" or args.config_cmd is None:
        print(f"Configuracion de BAGO {_BAGO_VERSION}:")
        print(f"  Base path      : {args.base_path or os.getcwd()}")
        print(f"  Default provider: {cm.default_provider}")
        print(f"  Default model   : {cm.default_model}")
        print(f"  Temperature     : {cm.get('temperature')}")
        print(f"  Streaming       : {cm.feature_streaming}")
        print(f"  Compression     : {cm.feature_compression}")
        print(f"  RL Learning     : {cm.feature_rl}")
        print("\nProviders:")
        for name in cm.get("providers", {}):
            enabled = cm.is_provider_enabled(name)
            status = "✓" if enabled else "✗"
            has_creds = creds.is_configured(name)
            cred_status = " [cred]" if has_creds else ""
            print(f"  [{status}] {name:15}{cred_status}")
        return 0

    if args.config_cmd == "reset":
        cm.reset()
        print("✓ Configuracion restaurada a valores por defecto.")
        return 0

    print("Uso: bago config [set|get|list|reset]")
    return 1

def cmd_serve(args: argparse.Namespace) -> int:
    import sys
    sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
    sys.path.insert(0, str(BAGO_ROOT / ".bago" / "api"))
    from session_manager import SessionManager
    from switch_engine import SwitchEngine
    from bridge import BagoAPIServer

    mgr = SessionManager(
        provider=args.provider,
        model=args.model,
        base_path=args.base_path,
    )
    engine = SwitchEngine(mgr.adapters)
    ui_dist = None
    if getattr(args, "ui_dist", ""):
        ui_dist = args.ui_dist
    else:
        default_ui_dist = BAGO_ROOT / "ui-react" / "dist"
        if default_ui_dist.exists():
            ui_dist = str(default_ui_dist)
    server = BagoAPIServer(mgr, engine, port=args.port, host=args.host, token=args.token, static_dir=ui_dist)
    server.start()
    try:
        while server.running:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    finally:
        mgr.close()
    return 0

def cmd_api(args: argparse.Namespace) -> int:
    """Inspeccion offline del bridge HTTP.

    No arranca el server. Importa `api_routes` desde `.bago/api/` y
    imprime la tabla viva de rutas. Pensado para que un agente (humano
    o IA) descubra que endpoints existen antes de hacer curl.
    """
    root = Path(args.root).resolve() if args.root else BAGO_ROOT
    sys.path.insert(0, str(root / ".bago" / "api"))
    try:
        from api_routes import all_routes, api_prefixes  # type: ignore
    except Exception as exc:
        print(f"[bago api] ERROR importando api_routes: {exc}", file=sys.stderr)
        return 1

    routes = all_routes()
    method_filter = args.method.upper()
    if method_filter != "ALL":
        routes = [r for r in routes if r["method"] == method_filter]
    if getattr(args, "pattern", False):
        routes = [r for r in routes if r["pattern"]]

    if getattr(args, "as_json", False):
        import json as _json
        print(_json.dumps({
            "ok": True,
            "count": len(routes),
            "method_filter": method_filter,
            "only_patterns": bool(getattr(args, "pattern", False)),
            "api_prefixes": list(api_prefixes()),
            "routes": routes,
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"# Bridge BAGO -- {len(routes)} rutas"
          + (f" (metodo={method_filter})" if method_filter != "ALL" else "")
          + (" [solo patrones]" if getattr(args, "pattern", False) else ""))
    print(f"# Auth: X-Bago-Token  |  API prefixes: {len(api_prefixes())}")
    print()
    print(f"{'METHOD':6} {'PATH':32} {'HANDLER_MODULE':25} {'HANDLER_FN':18} PATTERN")
    print("-" * 100)
    for r in routes:
        pat = "P" if r["pattern"] else ""
        print(f"{r['method']:6} {r['path']:32} {r['handler_module']:25} {r['handler_fn']:18} {pat}")
    return 0

def cmd_evidence(args: argparse.Namespace) -> int:
    from evidence_bundle import run
    return run(args)
