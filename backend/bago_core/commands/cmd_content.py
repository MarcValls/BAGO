#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

from bago_core.resolver import add_piece_paths
from bago_core.user_state_paths import bago_lock_file, ensure_user_roots

BAGO_ROOT = Path(__file__).resolve().parents[2]
add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")

from version import CURRENT as _BAGO_VERSION


def _pick_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_bago_lock() -> tuple[bool, Path, int | None]:
    ensure_user_roots()
    lock_path = bago_lock_file()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    if lock_path.exists():
        try:
            payload = lock_path.read_text(encoding='utf-8').strip().splitlines()
            existing_pid = int(payload[0].strip()) if payload and payload[0].strip().isdigit() else None
        except Exception:
            existing_pid = None
        if existing_pid and _pid_alive(existing_pid):
            return False, lock_path, existing_pid
        try:
            lock_path.unlink()
        except Exception:
            return False, lock_path, existing_pid
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(f"{os.getpid()}\n{time.time()}\n")
        return True, lock_path, None
    except FileExistsError:
        return False, lock_path, None


def _release_bago_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass

def cmd_claim(args: argparse.Namespace) -> int:
    """Gestiona el Claim Evidence Ledger."""
    add_piece_paths("core.package")
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
    add_piece_paths("core.package")
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
    add_piece_paths("core.package", "api.package")
    from session_manager import SessionManager
    from switch_engine import SwitchEngine
    from bridge import BagoAPIServer

    acquired, lock_path, existing_pid = _acquire_bago_lock()
    if not acquired:
        if existing_pid:
            print(f"Ya hay una instancia de BAGO activa (pid {existing_pid}).")
        else:
            print("Ya hay una instancia de BAGO activa.")
        return 0

    mgr = None
    try:
        mgr = SessionManager(
            provider=args.provider,
            model=args.model,
            base_path=args.base_path,
        )
        engine = SwitchEngine(mgr.adapters)
        host = str(getattr(args, "host", "") or "127.0.0.1").strip() or "127.0.0.1"
        port = int(getattr(args, "port", 0) or 0)
        if port <= 0:
            port = _pick_free_port(host)
        ui_dist = None
        if getattr(args, "ui_dist", ""):
            ui_dist = args.ui_dist
        else:
            default_ui_dist = BAGO_ROOT / "ui-react" / "dist"
            if default_ui_dist.exists():
                ui_dist = str(default_ui_dist)
        server = BagoAPIServer(mgr, engine, port=port, host=host, token=args.token, static_dir=ui_dist)
        server.start()
        try:
            while server.running:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
    finally:
        try:
            if mgr is not None:
                mgr.close()
        except Exception:
            pass
        _release_bago_lock(lock_path)
    return 0

def cmd_manager(args: argparse.Namespace) -> int:
    """Abre la UI compilada unificada en background y la lanza en el navegador."""
    import subprocess
    import time
    import webbrowser
    from urllib.error import URLError
    from urllib.request import urlopen

    root = Path(getattr(args, "base_path", "") or BAGO_ROOT).resolve()
    lock_path = bago_lock_file()
    if lock_path.exists():
        try:
            pid_text = lock_path.read_text(encoding='utf-8').splitlines()[0].strip()
            if pid_text.isdigit() and _pid_alive(int(pid_text)):
                print(f"Ya hay una instancia de BAGO activa (pid {pid_text}).")
                return 0
        except Exception:
            print("Ya hay una instancia de BAGO activa.")
            return 0
    host = str(getattr(args, "host", "") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(getattr(args, "port", 0) or 0)
    if port <= 0:
        port = _pick_free_port(host)
    ui_dist = str(getattr(args, "ui_dist", "") or (root / "ui-react" / "dist")).strip()
    index_html = Path(ui_dist) / "index.html"

    if not index_html.exists():
        print(f"UI compilada no encontrada: {index_html}")
        print("Ejecuta `npm run build` dentro de `ui-react/` antes de abrir el manager.")
        return 1

    url = f"http://{host}:{port}/"

    def _probe() -> bool:
        try:
            with urlopen(url, timeout=1) as response:
                return 200 <= getattr(response, "status", 200) < 500
        except (URLError, TimeoutError, OSError):
            return False

    if not _probe():
        cmd = [
            sys.executable,
            "-m",
            "bago_core.launcher",
            "--base-path",
            str(root),
            "serve",
            "--host",
            host,
            "--port",
            str(port),
            "--ui-dist",
            ui_dist,
        ]
        popen_kwargs: dict[str, Any] = {
            "cwd": str(root),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **popen_kwargs)
        deadline = time.time() + 20
        while time.time() < deadline:
            if _probe():
                break
            time.sleep(0.35)
    webbrowser.open(url)
    print(f"✓ Manager abierto en {url}")
    return 0

def cmd_api(args: argparse.Namespace) -> int:
    """Inspeccion offline del bridge HTTP.

    No arranca el server. Importa `api_routes` desde la pieza de API local y
    imprime la tabla viva de rutas. Pensado para que un agente (humano o IA)
    descubra que endpoints existen antes de hacer curl.
    """
    root = Path(args.root).resolve() if args.root else BAGO_ROOT
    add_piece_paths("api.package")
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
