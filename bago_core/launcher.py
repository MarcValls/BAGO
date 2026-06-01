#!/usr/bin/env python3
"""
launcher.py — BAGO Launcher

Punto de entrada principal para BAGO CLI.
Encarga:
1. Parsear argumentos
2. Detectar comando (chat, validate, config, help)
3. Delegar al módulo correspondiente
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Insert .bago paths
BAGO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "chat"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "providers"))

_CREATED_VERSION = "4.0.0"

# Lee la versión desde el índice central (versions.json)
from version import CURRENT as _BAGO_VERSION  # noqa: E402


def _read_release_label(root: Path) -> str:
    for candidate in (root / "release_version.txt", root / ".bago" / "release_version.txt"):
        if candidate.exists():
            try:
                value = candidate.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if value:
                return value
    cfg = _load_install_config(root)
    for key in ("release_version", "version", "tag"):
        value = cfg.get(key)
        if value:
            return str(value)
    return "latest release"


RELEASE_LABEL = _read_release_label(BAGO_ROOT)


def cmd_chat(args: argparse.Namespace) -> int:
    from repl import BagoREPL
    from system_prompt import get_system_prompt

    repl = BagoREPL(
        provider=args.provider,
        model=args.model,
        system_prompt=get_system_prompt(),
        base_path=args.base_path,
    )
    repl.run()
    return 0


EXPERIMENTAL_PROVIDERS = {"cpp-local"}


def _load_install_config(root: Path) -> dict[str, Any]:
    path = root / "install_config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _provider_inventory(base_path: str, include_experimental: bool = False) -> list[dict[str, Any]]:
    from session_manager import ADAPTER_REGISTRY, SessionManager

    mgr = SessionManager(base_path=base_path)
    try:
        providers = {item["name"]: item for item in mgr.available_providers()}
        inventory = []
        for name in ADAPTER_REGISTRY:
            if name in EXPERIMENTAL_PROVIDERS and not include_experimental:
                continue
            info = providers.get(name, {"name": name, "configured": False, "models": []})
            enabled = mgr.config.is_provider_enabled(name)
            configured = bool(info.get("configured"))
            models = list(info.get("models") or [])
            inventory.append({
                "name": name,
                "enabled": enabled,
                "configured": configured,
                "installed": enabled or configured,
                "models": models,
            })
        return inventory
    finally:
        mgr.close()


def _default_model_for_provider(base_path: str, provider: str) -> str:
    from session_manager import SessionManager

    mgr = SessionManager(base_path=base_path, provider=provider)
    try:
        models = mgr.list_models(provider)
        if provider == mgr.config.default_provider and mgr.config.default_model in models:
            return mgr.config.default_model
        return models[0] if models else mgr.config.default_model
    finally:
        mgr.close()


def _write_llm_start_state(base_path: str, provider: str, model: str, mode: str) -> Path:
    import json as _json
    from datetime import datetime, timezone

    state_dir = Path(base_path) / ".bago" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "llm_start.json"
    payload = {
        "provider": provider,
        "model": model,
        "mode": mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(_json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def cmd_llm(args: argparse.Namespace) -> int:
    from config_manager import ConfigManager

    action = args.llm_action or "list"
    inventory = _provider_inventory(args.base_path, include_experimental=getattr(args, "include_experimental", False))

    if action == "list":
        print("BAGO LLM providers")
        print("Instalados/configurados:")
        installed = [item for item in inventory if item["installed"]]
        pending = [item for item in inventory if not item["installed"]]
        if installed:
            for item in installed:
                markers = []
                if item["enabled"]:
                    markers.append("enabled")
                if item["configured"]:
                    markers.append("configured")
                markers_s = ", ".join(markers) or "local"
                models = len(item["models"])
                print(f"  [ok] {item['name']} ({markers_s}, {models} modelos)")
        else:
            print("  ninguno")
        print("Disponibles para configurar:")
        for item in pending:
            print(f"  [--] {item['name']}")
        if not getattr(args, "include_experimental", False):
            print("Experimentales ocultos: usa --include-experimental para verlos.")
        return 0

    if action != "start":
        print("Uso: bago llm [list|start]")
        return 1

    provider = getattr(args, "llm_provider", "") or ""
    model = getattr(args, "llm_model", "") or ""
    installed = [item for item in inventory if item["installed"]]
    installed_names = {item["name"] for item in installed}
    all_names = {item["name"] for item in inventory}

    if not provider:
        if hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            print("Providers instalados/configurados:")
            for idx, item in enumerate(installed, 1):
                print(f"  {idx}. {item['name']} ({len(item['models'])} modelos)")
            print("Providers disponibles para configurar:")
            for item in inventory:
                if not item["installed"]:
                    print(f"  - {item['name']}")
            choice = input("Elige provider instalado: ").strip()
            try:
                provider = installed[int(choice) - 1]["name"]
            except Exception:
                print("Selección inválida.")
                return 1
        elif installed:
            provider = installed[0]["name"]
        else:
            cm = ConfigManager(base_path=args.base_path)
            provider = cm.default_provider

    if provider in EXPERIMENTAL_PROVIDERS and not getattr(args, "include_experimental", False):
        print(f"Provider experimental fuera del camino principal: {provider}")
        print("Usa --include-experimental si quieres probarlo explícitamente.")
        return 1
    if provider not in all_names:
        print(f"Provider no registrado: {provider}")
        return 1
    if provider not in installed_names and not getattr(args, "allow_unconfigured", False):
        print(f"Provider no instalado/configurado: {provider}")
        print("Usa 'bago llm list' para ver instalados y disponibles.")
        return 1

    if not model:
        model = _default_model_for_provider(args.base_path, provider)

    _write_llm_start_state(args.base_path, provider, model, mode="dry-run" if args.dry_run else "chat")
    print(f"LLM session: {provider}/{model}")

    if getattr(args, "persist_default", False):
        cm = ConfigManager(base_path=args.base_path)
        cm.default_provider = provider
        cm.default_model = model
        print("Default provider/model actualizado.")

    if args.dry_run:
        return 0

    args.provider = provider
    args.model = model
    return cmd_chat(args)


def cmd_engine(args: argparse.Namespace) -> int:
    from bago_true_bridge import collect_status, render_status

    action = args.engine_action or "status"
    if action != "status":
        print("Uso: bago engine status")
        return 1
    status = collect_status(args.true_root or None, args.appdata_root or None)
    print(render_status(status, section="engine"))
    return 0


def cmd_appdata(args: argparse.Namespace) -> int:
    from bago_true_bridge import collect_status, render_status

    action = args.appdata_action or "status"
    if action != "status":
        print("Uso: bago appdata status")
        return 1
    status = collect_status(args.true_root or None, args.appdata_root or None)
    print(render_status(status, section="appdata"))
    return 0


def cmd_cmd_rl(args: argparse.Namespace) -> int:
    from bago_true_bridge import collect_status, render_status

    action = args.cmd_rl_action or "status"
    if action != "status":
        print("Uso: bago cmd-rl status")
        return 1
    status = collect_status(args.true_root or None, args.appdata_root or None)
    print(render_status(status, section="cmd-rl"))
    return 0


def cmd_rl(args: argparse.Namespace) -> int:
    from rl_bridge import RLBridge, render_status

    bridge = RLBridge(args.base_path, true_root=args.true_root or None)
    action = args.rl_action or "status"

    if action == "status":
        print(render_status(bridge.status()))
        return 0

    if action == "shadow":
        shadow_action = args.shadow_action or "status"
        if shadow_action == "on":
            print(render_status(bridge.shadow(True)))
            return 0
        if shadow_action == "off":
            print(render_status(bridge.shadow(False)))
            return 0
        if shadow_action == "status":
            print(render_status(bridge.status()))
            return 0
        print("Uso: bago rl shadow [on|off|status]")
        return 1

    if action == "train":
        train_action = args.train_action or ""
        if train_action != "bc":
            print("Uso: bago rl train bc")
            return 1
        from rl_policies import render_policy_report, train_bc_policy
        report = train_bc_policy(args.base_path, args.n_actions, args.n_features)
        print(render_policy_report(report, "BAGO RL TRAIN BC"))
        return 0

    if action == "eval":
        from rl_policies import eval_bc_policy, render_policy_report
        report = eval_bc_policy(args.base_path, args.n_features)
        print(render_policy_report(report, "BAGO RL EVAL"))
        return 0

    print("Uso: bago rl [status|shadow|train|eval]")
    return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Gate real de validación — no solo health checks de providers."""
    import ast
    import json as _json
    import re
    import tempfile

    base = Path(args.base_path)
    bago_dir = base / ".bago"
    checks: list[dict] = []
    fails = 0

    def _check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        status = "PASS" if ok else "FAIL"
        if not ok:
            fails += 1
        checks.append({"check": name, "status": status, "detail": detail})
        marker = "✓" if ok else "✗"
        line = f"  [{marker}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    print("\nBAGO VALIDATE\n" + "─" * 40)

    # ── 1. Syntax: compilar todos los .py en .bago/ y bago_core/ ──────────────
    py_errors: list[str] = []
    for search_root in [bago_dir, base / "bago_core"]:
        if not search_root.exists():
            continue
        for py_file in search_root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                src = py_file.read_text(encoding="utf-8", errors="replace")
                ast.parse(src, filename=str(py_file))
            except SyntaxError as e:
                py_errors.append(f"{py_file.relative_to(base)}: {e}")
    _check("syntax", not py_errors, f"{len(py_errors)} error(es)" if py_errors else "todos los .py compilables")

    # ── 2. Contratos presentes ─────────────────────────────────────────────────
    contracts_dir = base / "docs" / "contracts"
    required_contracts = [
        "bago_v4_runtime_contract.json",
        "bago_v4_repl_contract.md",
        "bago_v4_evidence_contract.md",
        "bago_v4_knowledge_contract.md",
        "bago_v4_governance_contract.md",
        "bago_v4_engineering_contract.md",
    ]
    missing_contracts = [c for c in required_contracts if not (contracts_dir / c).exists()]
    _check("contracts_present", not missing_contracts,
           f"faltan: {missing_contracts}" if missing_contracts else f"{len(required_contracts)} contratos presentes")

    # ── 3. auto_allow_tools = false ────────────────────────────────────────────
    config_file = bago_dir / "config.json"
    config_manager_file = bago_dir / "core" / "config_manager.py"
    auto_allow_ok = False
    runtime_val: Any = None
    default_val: Any = None
    config_detail = "config.json/config_manager.py no encontrados"
    if config_file.exists():
        try:
            cfg = _json.loads(config_file.read_text(encoding="utf-8"))
            runtime_val = cfg.get("features", {}).get("auto_allow_tools", True)
        except Exception as exc:
            config_detail = f"runtime config error: {exc}"
    if config_manager_file.exists():
        try:
            tree = ast.parse(config_manager_file.read_text(encoding="utf-8"), filename=str(config_manager_file))
            for node in tree.body:
                if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "DEFAULT_CONFIG":
                    defaults = ast.literal_eval(node.value)
                    default_val = defaults.get("features", {}).get("auto_allow_tools", True)
                    break
        except Exception as exc:
            config_detail = f"default config error: {exc}"
    auto_allow_ok = runtime_val is False and default_val is False
    if config_detail.startswith("config.json"):
        config_detail = f"runtime={runtime_val}, default={default_val}"
    _check("auto_allow_tools_false", auto_allow_ok, config_detail)

    # ── 4. execute_command sin shell=True expuesto ─────────────────────────────
    tool_registry = bago_dir / "core" / "tool_registry.py"
    shell_true_ok = True
    shell_detail = "tool_registry.py no encontrado"
    if tool_registry.exists():
        src = tool_registry.read_text(encoding="utf-8")
        # shell=True is ONLY forbidden in the execute_command implementation
        # (it's allowed in comments or other internal uses)
        exposed = [
            ln.strip() for ln in src.splitlines()
            if "shell=True" in ln and not ln.strip().startswith("#")
        ]
        shell_true_ok = len(exposed) == 0
        shell_detail = f"{len(exposed)} ocurrencia(s) de shell=True" if exposed else "no expuesto"
    _check("no_shell_true", shell_true_ok, shell_detail)

    # ── 5. API no arranca en 0.0.0.0 por defecto ──────────────────────────────
    bridge_file = bago_dir / "api" / "bridge.py"
    api_host_ok = True
    api_detail = "bridge.py no encontrado"
    if bridge_file.exists():
        src = bridge_file.read_text(encoding="utf-8")
        # Buscar HTTPServer(("0.0.0.0" como hardcode (no dentro de self.host)
        hardcoded = re.search(r'HTTPServer\(\s*\(\s*["\']0\.0\.0\.0["\']', src)
        api_host_ok = hardcoded is None
        api_detail = "hardcode 0.0.0.0 detectado" if hardcoded else "host proviene de parámetro"
    _check("api_host_not_hardcoded", api_host_ok, api_detail)

    # ── 6. CORS sin wildcard ──────────────────────────────────────────────────
    cors_ok = True
    cors_detail = "bridge.py no encontrado"
    if bridge_file.exists():
        src = bridge_file.read_text(encoding="utf-8")
        wildcard = 'Access-Control-Allow-Origin", "*"' in src or "Access-Control-Allow-Origin', '*'" in src
        cors_ok = not wildcard
        cors_detail = "sin wildcard" if cors_ok else "wildcard CORS detectado"
    _check("cors_no_wildcard", cors_ok, cors_detail)

    # ── 7. .gitignore excluye .bago/state/ ────────────────────────────────────
    gitignore = base / ".gitignore"
    gitignore_ok = False
    gitignore_detail = ".gitignore no encontrado"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        gitignore_ok = ".bago/state/" in content or ".bago/state" in content
        gitignore_detail = "excluye .bago/state/" if gitignore_ok else ".bago/state/ no excluido"
    _check("state_excluded_from_vcs", gitignore_ok, gitignore_detail)

    # ── 8. Culpas abiertas ─────────────────────────────────────────────────────
    culpas_file = bago_dir / "state" / "culpas" / "culpas.jsonl"
    culpas_ok = True
    culpas_detail = "sin culpas registradas"
    if culpas_file.exists():
        open_culpas = []
        for line in culpas_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = _json.loads(line)
                if entry.get("status") == "open":
                    open_culpas.append(entry.get("culpa_id", "?"))
            except Exception:
                pass
        culpas_ok = len(open_culpas) == 0
        culpas_detail = f"{len(open_culpas)} culpas abiertas: {open_culpas}" if open_culpas else "sin culpas abiertas"
    _check("no_open_culpas", culpas_ok, culpas_detail)

    # ── 8. Claims ledger: no hay claims fallados ───────────────────────────────
    claims_file = bago_dir / "state" / "evidence" / "claims.jsonl"
    claims_ok = True
    claims_detail = "sin claims registrados"
    if claims_file.exists():
        sys.path.insert(0, str(base / "bago_core"))
        try:
            from claim_ledger import ClaimLedger
            ledger = ClaimLedger(base_path=str(base))
            r = ledger.report()
            failed = r.get("failed", 0)
            claims_ok = failed == 0
            claims_detail = (
                f"total={r['total_claims']}, verified={r['verified']}, "
                f"open={r['open']}, simulated={r['simulated']}, failed={failed}"
            )
        except Exception as exc:
            claims_detail = f"error al leer ledger: {exc}"
    _check("no_failed_claims", claims_ok, claims_detail)

    # ── 9. Provider health (comportamiento original, ahora un check más) ───────
    print("  [→] provider_health (requiere providers activos):")
    sys.path.insert(0, str(bago_dir / "core"))
    try:
        from session_manager import SessionManager
        any_provider_ok = False
        with tempfile.TemporaryDirectory() as td:
            mgr = SessionManager(base_path=td, provider="ollama-local", model="llama3.2:3b")
            try:
                for name, adapter_cls in mgr.adapters.items():
                    try:
                        inst = adapter_cls(config=mgr.config.provider_config(name))
                        health = inst.health_check()
                        marker = "✓" if health.ok else "·"
                        print(f"       [{marker}] {name:15} — {health.detail}")
                        if health.ok:
                            any_provider_ok = True
                    except Exception as exc:
                        print(f"       [·] {name:15} — error: {exc}")
            finally:
                mgr.close()
        _check("at_least_one_provider_healthy", any_provider_ok,
               "al menos un provider responde" if any_provider_ok else "ningún provider disponible (normal si no hay LLM activo)")
    except Exception as exc:
        _check("at_least_one_provider_healthy", False, f"error al cargar session_manager: {exc}")

    # ── Resultado final ────────────────────────────────────────────────────────
    print("\n" + "─" * 40)
    if fails == 0:
        print(f"✓ VALIDATE PASS — {len(checks)} checks OK")
    else:
        print(f"✗ VALIDATE FAIL — {fails}/{len(checks)} checks fallaron")
        for c in checks:
            if c["status"] == "FAIL":
                print(f"  → [{c['check']}]: {c['detail']}")
    print()
    return 0 if fails == 0 else 1


def cmd_claim(args: argparse.Namespace) -> int:
    """Gestiona el Claim Evidence Ledger."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
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
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "core"))
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
        print(f"Configuración de BAGO {_BAGO_VERSION}:")
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
        print("✓ Configuración restaurada a valores por defecto.")
        return 0

    print("Uso: bago config [set|get|list|reset]")
    return 1


def cmd_serve(args: argparse.Namespace) -> int:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "core"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "api"))
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
        default_ui_dist = Path(__file__).resolve().parents[1] / "ui-react" / "dist"
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


def cmd_evidence(args: argparse.Namespace) -> int:
    from evidence_bundle import run
    return run(args)


def _load_tool_module(module_name: str, file_name: str):
    import importlib.util

    tool_path = BAGO_ROOT / ".bago" / "tools" / file_name
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar la herramienta: {tool_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_project(args: argparse.Namespace) -> int:
    mod = _load_tool_module("project_memory", "project_memory.py")
    action = getattr(args, "project_cmd", None) or "status"
    root = getattr(args, "root", "") or None
    if action == "init":
        return mod.cmd_init(root)
    if action == "status":
        return mod.cmd_status(root)
    if action == "link":
        return mod.cmd_link(root)
    print("Uso: bago project <init|status|link> [--root DIR]")
    return 1


def cmd_preflight(args: argparse.Namespace) -> int:
    mod = _load_tool_module("preflight_engine", "preflight_engine.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    cmd = getattr(args, "cmd", "") or ""
    if root:
        argv += ["--root", root]
    if cmd:
        argv += ["--cmd", cmd]
    return mod.main(argv)


def cmd_toolsmith(args: argparse.Namespace) -> int:
    mod = _load_tool_module("toolsmith", "toolsmith.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    if getattr(args, "toolsmith_json", False):
        argv.append("--json")
    subcmd = getattr(args, "toolsmith_cmd", None)
    if subcmd == "catalog":
        argv.append("catalog")
    elif subcmd == "assign":
        argv += ["assign", "--task", getattr(args, "task", "")]
        if getattr(args, "agent_name", ""):
            argv += ["--agent", args.agent_name]
        if getattr(args, "sprint", ""):
            argv += ["--sprint", args.sprint]
    elif subcmd == "sprint":
        argv += ["sprint", getattr(args, "sprint_id", "")]
        if getattr(args, "tasks", ""):
            argv += ["--tasks", args.tasks]
    elif subcmd == "missing":
        argv.append("missing")
    elif subcmd == "create":
        argv += ["create", getattr(args, "tool_name", "")]
        if getattr(args, "desc", ""):
            argv += ["--desc", args.desc]
        if getattr(args, "category", ""):
            argv += ["--category", args.category]
    elif subcmd == "listen":
        argv += ["listen"]
        if getattr(args, "limit", 1) != 1:
            argv += ["--limit", str(args.limit)]
    else:
        argv += ["--help"]
    return mod.main(argv)


def cmd_agent(args: argparse.Namespace) -> int:
    mod = _load_tool_module("spiral_agent", "spiral_agent.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    subcmd = getattr(args, "agent_cmd", None)
    if subcmd == "spawn":
        argv += ["spawn", getattr(args, "agent_id", "")]
        if getattr(args, "phase", None) is not None:
            argv += ["--phase", str(args.phase)]
        if getattr(args, "skills", ""):
            argv += ["--skills", args.skills]
    elif subcmd in {"list", "status"}:
        argv += [subcmd]
    elif subcmd in {"run", "kill"}:
        argv += [subcmd, getattr(args, "agent_id", "")]
    else:
        argv += ["--help"]
    return mod.main(argv)


def cmd_route(args: argparse.Namespace) -> int:
    mod = _load_tool_module("agent_router", "agent_router.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    task_text = getattr(args, "task", "") or ""
    if task_text:
        argv += ["--task", task_text]
    if getattr(args, "route_json", False):
        argv.append("--json")
    if getattr(args, "history", False):
        argv.append("--history")
    if getattr(args, "limit", 10) != 10:
        argv += ["--limit", str(args.limit)]
    if getattr(args, "no_classifier", False):
        argv.append("--no-classifier")
    if not task_text and not getattr(args, "history", False):
        argv += ["--help"]
    return mod.main(argv)


def cmd_scan(args: argparse.Namespace) -> int:
    """Herramientas de análisis portables. Funcionan en cualquier proyecto."""
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    subcmd = getattr(args, "scan_cmd", None)
    root   = getattr(args, "root", "") or ""

    def _base_argv() -> list[str]:
        return ["--root", root] if root else []

    if subcmd == "secrets":
        import secret_scan
        argv = _base_argv()
        sev = getattr(args, "severity", "warning")
        if sev != "warning":
            argv += ["--severity", sev]
        if getattr(args, "as_json", False):
            argv.append("--json")
        return secret_scan.main(argv)

    elif subcmd == "deps":
        import dep_audit
        argv = _base_argv()
        fmt = getattr(args, "format", "text")
        if fmt != "text":
            argv += ["--format", fmt]
        if getattr(args, "pip_audit", False):
            argv.append("--pip-audit")
        return dep_audit.main(argv)

    elif subcmd == "todos":
        import todo_scan
        argv = _base_argv()
        if getattr(args, "fixme_only", False):
            argv.append("--fixme")
        if getattr(args, "count", False):
            argv.append("--count")
        if getattr(args, "as_json", False):
            argv.append("--json")
        return todo_scan.main(argv)

    elif subcmd == "tokens":
        import token_rotation_guard
        argv = _base_argv()
        if getattr(args, "fix", False):
            argv.append("--fix")
        if getattr(args, "as_json", False):
            argv.append("--json")
        return token_rotation_guard.main(argv)

    elif subcmd == "dead":
        import dead_code
        argv = [root or "./"]
        if getattr(args, "as_json", False):
            argv.append("--json")
        return dead_code.main(argv)

    elif subcmd == "names":
        import naming_check
        argv = [root or "./"]
        if getattr(args, "as_json", False):
            argv.append("--json")
        return naming_check.main(argv)

    elif subcmd == "all":
        scanners = [
            ("secrets", "secret_scan",           _base_argv()),
            ("deps",    "dep_audit",             _base_argv()),
            ("todos",   "todo_scan",             _base_argv() + ["--count"]),
            ("tokens",  "token_rotation_guard",  _base_argv()),
        ]
        results: dict[str, str] = {}
        has_errors = False
        for name, mod_name, argv in scanners:
            try:
                mod = __import__(mod_name)
                rc = mod.main(argv)
                results[name] = "[OK]" if rc == 0 else "[WARN]"
                if rc != 0:
                    has_errors = True
            except Exception as exc:  # noqa: BLE001
                results[name] = f"[ERROR] {exc}"
                has_errors = True
        print("\n[bago scan all] Resumen:")
        for k, v in results.items():
            print(f"  {k:10} {v}")
        return 1 if has_errors else 0

    elif subcmd == "doctor":
        import doctor
        argv = _base_argv()
        if getattr(args, 'fix', False): argv.append('--fix')
        if getattr(args, 'quiet', False): argv.append('--quiet')
        if getattr(args, 'as_json', False): argv.append('--json')
        return doctor.main(argv)
    elif subcmd == "commit":
        import commit_readiness
        argv = _base_argv()
        if getattr(args, 'all_files', False): argv.append('--all')
        if getattr(args, 'strict', False): argv.append('--strict')
        if getattr(args, 'as_json', False): argv.append('--json')
        return commit_readiness.main(argv)
    elif subcmd == "git":
        import git_context
        argv = _base_argv()
        if getattr(args, 'brief', False): argv.append('--brief')
        if getattr(args, 'as_json', False): argv.append('--json')
        n_log = getattr(args, 'log', 10)
        if n_log != 10: argv += ['--log', str(n_log)]
        return git_context.main(argv)
    elif subcmd == "sincerity":
        import sincerity_detector
        argv = _base_argv()
        if getattr(args, 'strict', False): argv.append('--strict')
        if getattr(args, 'as_json', False): argv.append('--json')
        path_arg = getattr(args, 'path', '')
        if path_arg: argv += ['--path', path_arg]
        return sincerity_detector.main(argv)
    elif subcmd == "net":
        import net_scan
        argv = []
        if getattr(args, 'scan_net', False): argv.append('--scan')
        if getattr(args, 'adapters', False): argv.append('--adapters')
        if getattr(args, 'as_json', False): argv.append('--json')
        return net_scan.main(argv)
    elif subcmd == "metrics":
        import code_metrics
        argv = _base_argv()
        if getattr(args, 'as_json', False): argv.append('--json')
        ext_arg = getattr(args, 'ext', '')
        if ext_arg: argv += ['--ext', ext_arg]
        return code_metrics.main(argv)
    elif subcmd == "infra":
        mod = _load_tool_module("bago_infra_scan", "bago_infra_scan.py")
        argv = _base_argv()
        if getattr(args, 'quick', False):
            argv.append('--quick')
        if getattr(args, 'as_json', False):
            argv.append('--json')
        if getattr(args, 'all_ports', False):
            argv.append('--all')
        return mod.main(argv)
    elif subcmd == "heal":
        import auto_heal
        argv = _base_argv()
        if getattr(args, 'fix', False): argv.append('--fix')
        if getattr(args, 'dry_run', False): argv.append('--dry-run')
        if getattr(args, 'as_json', False): argv.append('--json')
        return auto_heal.main(argv)
    elif subcmd == "security":
        import bago_security_audit
        argv = _base_argv()
        if getattr(args, 'fix', False): argv.append('--fix')
        if getattr(args, 'as_json', False): argv.append('--json')
        return bago_security_audit.main(argv)

    else:
        print("Uso: bago scan <subcomando> [--root DIR] [opciones]")
        print()
        print("  Subcomandos disponibles:")
        print("    secrets   Detecta secretos hardcodeados (API keys, passwords)")
        print("    deps      Audita dependencias Python (CVEs, versiones sin pinear)")
        print("    todos     Lista TODOs, FIXMEs y HACKs en el codigo fuente")
        print("    tokens    Detecta tokens de API expuestos")
        print("    dead      Detecta codigo muerto (imports, funciones no usadas)")
        print("    names     Valida convenciones de nombres (PEP 8)")
        print("    sincerity Detecta marketing vacio en la documentacion")
        print("    net       Escanea adaptadores de red y dispositivos locales")
        print("    metrics   Metricas de codigo: LOC, archivos, tipos")
        print("    infra     Escanea servicios locales LLM (Ollama, LM Studio, APIs)")
        print("    heal      Sistema inmune: detecta y repara inconsistencias")
        print("    security  Auditoria de seguridad: tokens, permisos, configs")
        print("    doctor    Diagnostico de integridad del proyecto")
        print("    commit    Pre-commit check rapido")
        print("    git       Snapshot del contexto git")
        print("    all       Ejecuta todos los scans")
        print()
        print("  Opciones comunes:")
        print("    --root DIR    Directorio a escanear (default: directorio actual)")
        print("    --json        Output estructurado en JSON")
        print()
        print("  Estas herramientas tambien funcionan standalone:")
        print("    python .bago/tools/secret_scan.py --root /mi/proyecto")
        return 0


def cmd_canary(args):
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import bago_canary
    root = getattr(args, 'root', '') or ''
    subcmd = getattr(args, 'canary_cmd', None)
    argv = ['--root', root] if root else []
    if subcmd == 'deploy':
        argv += ['deploy', '--type', getattr(args, 'type', 'aws_keys')]
    elif subcmd:
        argv.append(subcmd)
    else:
        argv.append('list')
    return bago_canary.main(argv)


def cmd_backup(args):
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import bago_backup_vault
    root = getattr(args, 'root', '') or ''
    subcmd = getattr(args, 'backup_cmd', None)
    argv = ['--root', root] if root else []
    if subcmd == 'create':
        argv += ['create', '--max', str(getattr(args, 'max', 10))]
    elif subcmd == 'restore':
        argv += ['restore', '--index', str(getattr(args, 'index', 1))]
    elif subcmd:
        argv.append(subcmd)
    else:
        argv.append('list')
    return bago_backup_vault.main(argv)


def cmd_inventory(args):
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import bago_inventory
    root = getattr(args, 'root', '') or ''
    argv = ['--root', root] if root else []
    fmt = getattr(args, 'format', 'text')
    if fmt != 'text':
        argv += ['--format', fmt]
    return bago_inventory.main(argv)


def cmd_cpp_runtime(args: argparse.Namespace) -> int:
    from cpp_runtime_host import main as runtime_main
    argv = ["--host", args.host, "--port", str(args.port), "--model", args.runtime_model]
    if args.test:
        argv.append("--test")
    return runtime_main(argv)


def cmd_install(args: argparse.Namespace) -> int:
    import subprocess

    root = Path(__file__).resolve().parents[1]
    install_dir = Path(args.install_dir)
    source_root = Path(args.source_root) if args.source_root else root
    same_source_and_target = False
    try:
        same_source_and_target = source_root.resolve() == install_dir.resolve()
    except Exception:
        same_source_and_target = str(source_root).rstrip("\\/").lower() == str(install_dir).rstrip("\\/").lower()
    repair_only = bool(args.repair_only or (same_source_and_target and not args.package_zip))
    script = root / "install-v4.ps1"
    if not script.exists():
        print(f"[ERROR] No se encontro instalador local: {script}")
        return 1

    ps = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
    command = [
        ps,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    if args.source_root:
        command += ["-SourceRoot", args.source_root]
    if args.package_zip:
        command += ["-PackageZip", args.package_zip]
    if args.install_dir:
        command += ["-InstallDir", args.install_dir]
    if args.mode:
        command += ["-Mode", args.mode]
    elif repair_only:
        command += ["-Mode", "Express"]
    if repair_only:
        command.append("-RepairOnly")
    if args.skip_tests:
        command.append("-SkipTests")
    if args.no_path_update:
        command.append("-NoPathUpdate")

    print("BAGO local install")
    print(f"Fuente local : {args.source_root or str(root)}")
    print(f"Destino      : {install_dir}")
    print(f"Modo         : {'repair' if repair_only else 'install'}")
    print("Red          : no descarga nada")
    if args.dry_run:
        print("Dry-run      : no ejecutado")
        return 0
    return subprocess.call(command)


def _normalize_path_entry(entry: str) -> str:
    return entry.strip().rstrip("\\").lower()


def _remove_install_from_path(install_path: str) -> str:
    removed_scopes: list[str] = []
    install_norm = _normalize_path_entry(install_path)
    current = os.environ.get("Path", "")
    entries = []
    for entry in current.split(";"):
        clean = entry.strip()
        if clean and _normalize_path_entry(clean) != install_norm:
            entries.append(clean)
    os.environ["Path"] = ";".join(entries)

    try:
        import winreg  # type: ignore
    except Exception:
        return "process"

    def _rewrite(scope_root: int) -> bool:
        try:
            with winreg.OpenKey(scope_root, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                value, reg_type = winreg.QueryValueEx(key, "Path")
                kept = []
                for entry in str(value or "").split(";"):
                    clean = entry.strip()
                    if clean and _normalize_path_entry(clean) != install_norm:
                        kept.append(clean)
                winreg.SetValueEx(key, "Path", 0, reg_type, ";".join(kept))
            return True
        except Exception:
            return False

    if _rewrite(winreg.HKEY_CURRENT_USER):
        removed_scopes.append("user")
    if _rewrite(winreg.HKEY_LOCAL_MACHINE):
        removed_scopes.append("machine")
    return "+".join(removed_scopes) if removed_scopes else "process"


def _zip_tree(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))


def _is_windows_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _is_under_path(path: Path, parent: str) -> bool:
    if not parent:
        return False
    try:
        path.resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False


def _needs_uninstall_elevation(install_dir: Path) -> bool:
    if os.name != "nt" or _is_windows_admin():
        return False
    protected_roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    return any(_is_under_path(install_dir, root) for root in protected_roots if root)


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _relaunch_uninstall_elevated(args: argparse.Namespace, install_dir: Path) -> int:
    ps = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
    cli_path = Path(__file__).with_name("cli.py")
    argv = [
        str(cli_path if cli_path.exists() else Path(__file__)),
        "--base-path",
        str(args.base_path),
        "uninstall",
        "--install-dir",
        str(install_dir),
        "--elevated-child",
    ]
    if args.backup_root:
        argv += ["--backup-root", args.backup_root]
    if args.user_state_dir:
        argv += ["--user-state-dir", args.user_state_dir]
    if args.purge_state:
        argv.append("--purge-state")
    arg_list = "@(" + ",".join(_ps_literal(item) for item in argv) + ")"
    command = (
        "$p = Start-Process -FilePath "
        + _ps_literal(sys.executable)
        + " -ArgumentList "
        + arg_list
        + " -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    )
    print("Elevacion    : requerida para borrar Program Files")
    return subprocess.call([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command])


def _rmtree_writable(path: Path) -> None:
    def _fix_permissions(func: Any, target: str, exc_info: Any) -> None:
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except Exception:
            raise exc_info[1]

    shutil.rmtree(path, onerror=_fix_permissions)


def cmd_uninstall(args: argparse.Namespace) -> int:
    install_dir = Path(args.install_dir or Path(__file__).resolve().parents[1])
    backup_root = Path(args.backup_root or (Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "BAGO" / "backups"))
    user_state_dir = Path(args.user_state_dir or (Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "BAGO" / "user"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if not install_dir.exists():
        print(f"[ERROR] No se encontro la instalacion: {install_dir}")
        return 1

    backup_zip = backup_root / f"bago-programfiles-uninstall-{stamp}.zip"
    print("BAGO local uninstall")
    print(f"Destino      : {install_dir}")
    print(f"Backup       : {backup_zip}")
    print(f"Estado user  : {user_state_dir}")
    print(f"Purga state  : {'si' if args.purge_state else 'no'}")
    if args.dry_run:
        print("Dry-run      : no ejecutado")
        return 0

    if _needs_uninstall_elevation(install_dir) and not args.elevated_child and not args.no_elevate:
        return _relaunch_uninstall_elevated(args, install_dir)

    try:
        _zip_tree(install_dir, backup_zip)
        removed_scope = _remove_install_from_path(str(install_dir))
        if args.purge_state and user_state_dir.exists():
            _rmtree_writable(user_state_dir)
        _rmtree_writable(install_dir)
    except PermissionError as exc:
        print(f"[ERROR] Sin permisos para desinstalar: {exc}")
        if os.name == "nt" and not _is_windows_admin():
            print("Ejecuta PowerShell como administrador o usa el prompt UAC del comando sin --no-elevate.")
        return 1
    except OSError as exc:
        print(f"[ERROR] No se pudo completar la desinstalacion: {exc}")
        return 1
    print(f"Backup creado: {backup_zip}")
    print(f"PATH limpiado : {removed_scope}")
    return 0


def main(argv: list[str] | None = None) -> int:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "core"))
    from config_manager import ConfigManager

    install_root = Path(__file__).resolve().parents[1]
    install_config = _load_install_config(install_root)

    # Leer defaults desde config.json si existe
    base = str(install_root) if install_config else os.getcwd()
    try:
        cm_defaults = ConfigManager(base_path=base)
        default_provider = install_config.get("runtime", {}).get("default_provider") or cm_defaults.default_provider
        default_model = install_config.get("runtime", {}).get("default_model") or cm_defaults.default_model
    except Exception:
        default_provider = "ollama-local"
        default_model = "llama3.2:3b"

    parser = argparse.ArgumentParser(prog="bago", description=f"BAGO {_BAGO_VERSION} — Session-First AI Chat")
    parser.add_argument("--provider", default=default_provider, help="Provider por defecto")
    parser.add_argument("--model", default=default_model, help="Modelo por defecto")
    parser.add_argument("--base-path", default=base, help="Directorio base del proyecto")
    sub = parser.add_subparsers(dest="command", help="Comandos disponibles")

    sub.add_parser("chat", help="Inicia el REPL de chat")
    sub.add_parser("launch", help="Alias de chat: inicia BAGO")
    sub.add_parser("start", help="Inicia BAGO y autoevoluciona (alias de chat con auto-aprendizaje al arrancar)")
    sub.add_parser("validate", help="Gate real de validación: security, contratos, culpas, claims, providers")

    install_parser = sub.add_parser("install", help="Instala/repara BAGO desde la copia local, sin descarga")
    install_parser.add_argument("--source-root", default="", help="Raiz local desde la que instalar")
    install_parser.add_argument("--package-zip", default="", help="ZIP local desde el que instalar")
    install_parser.add_argument("--install-dir", default="C:\\Program Files\\BAGO", help="Destino de instalacion")
    install_parser.add_argument("--mode", choices=("Express", "Advanced"), default="", help="Modo de asistente")
    install_parser.add_argument("--repair-only", action="store_true", help="Solo repara registro PATH/comando")
    install_parser.add_argument("--skip-tests", action="store_true", help="Omite tests internos del instalador")
    install_parser.add_argument("--no-path-update", action="store_true", help="No modifica PATH")
    install_parser.add_argument("--dry-run", action="store_true", help="Muestra lo que haria sin ejecutar")

    uninstall_parser = sub.add_parser("uninstall", help="Desinstala BAGO de la ruta indicada")
    uninstall_parser.add_argument("--install-dir", default="C:\\Program Files\\BAGO", help="Destino a desinstalar")
    uninstall_parser.add_argument("--backup-root", default="", help="Carpeta para el ZIP de backup")
    uninstall_parser.add_argument("--user-state-dir", default="", help="Carpeta de estado a preservar o purgar")
    uninstall_parser.add_argument("--purge-state", action="store_true", help="Borra tambien el estado de usuario")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Muestra lo que haria sin ejecutar")
    uninstall_parser.add_argument("--no-elevate", action="store_true", help=argparse.SUPPRESS)
    uninstall_parser.add_argument("--elevated-child", action="store_true", help=argparse.SUPPRESS)

    claim_parser = sub.add_parser("claim", help="Claim Evidence Ledger — afirmaciones trazables")
    claim_sub = claim_parser.add_subparsers(dest="claim_action")
    claim_add = claim_sub.add_parser("add", help="Añade un claim trazable")
    claim_add.add_argument("--claim",     dest="claim_text", required=True)
    claim_add.add_argument("--basis",     required=True)
    claim_add.add_argument("--command",   default="")
    claim_add.add_argument("--artifacts", default="")
    claim_add.add_argument("--limits",    default="")
    claim_add.add_argument("--status",    dest="status_val", default="open")
    claim_add.add_argument("--stdout",    dest="stdout_val", default="")
    claim_add.add_argument("--notes",     default="")
    claim_list = claim_sub.add_parser("list", help="Lista claims")
    claim_list.add_argument("--status",   dest="filter_status", default="")
    claim_verify = claim_sub.add_parser("verify", help="Verifica artefactos de un claim")
    claim_verify.add_argument("claim_id")
    claim_sub.add_parser("report", help="Resumen del ledger")

    config_parser = sub.add_parser("config", help="Gestiona configuración")
    config_sub = config_parser.add_subparsers(dest="config_cmd", help="Subcomandos de config")
    config_set_parser = config_sub.add_parser("set", help="Establece clave de config")
    config_set_parser.add_argument("key", nargs="?")
    config_set_parser.add_argument("value", nargs=argparse.REMAINDER)
    config_get_parser = config_sub.add_parser("get", help="Obtiene clave de config")
    config_get_parser.add_argument("key", nargs="?")
    config_sub.add_parser("list", help="Lista configuración completa")
    config_sub.add_parser("reset", help="Restaura defaults")

    llm_parser = sub.add_parser("llm", help="Gestiona arranque provider-aware")
    llm_parser.add_argument("--include-experimental", action="store_true", help="Incluye providers experimentales fuera del release principal")
    llm_sub = llm_parser.add_subparsers(dest="llm_action")
    llm_sub.add_parser("list", help="Lista providers instalados/configurados y disponibles")
    llm_start = llm_sub.add_parser("start", help="Inicia BAGO con provider/modelo seleccionado")
    llm_start.add_argument("--provider", dest="llm_provider", default="", help="Provider instalado/configurado")
    llm_start.add_argument("--model", dest="llm_model", default="", help="Modelo para la sesión")
    llm_start.add_argument("--allow-unconfigured", action="store_true", help="Permite arrancar contra provider no configurado")
    llm_start.add_argument("--persist-default", action="store_true", help="Guarda provider/modelo como default")
    llm_start.add_argument("--dry-run", action="store_true", help="Registra selección sin abrir chat")

    engine_parser = sub.add_parser("engine", help="Estado del backend avanzado bago_true")
    engine_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    engine_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    engine_sub = engine_parser.add_subparsers(dest="engine_action")
    engine_sub.add_parser("status", help="Muestra estado de bago_true")

    appdata_parser = sub.add_parser("appdata", help="Estado de instalacion AppData BAGO")
    appdata_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    appdata_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    appdata_sub = appdata_parser.add_subparsers(dest="appdata_action")
    appdata_sub.add_parser("status", help="Muestra estado de AppData BAGO")

    cmd_rl_parser = sub.add_parser("cmd-rl", help="Estado del puente AppData cmd-rl/Spiral")
    cmd_rl_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    cmd_rl_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    cmd_rl_sub = cmd_rl_parser.add_subparsers(dest="cmd_rl_action")
    cmd_rl_sub.add_parser("status", help="Muestra soporte cmd-rl/Spiral")

    rl_parser = sub.add_parser("rl", help="RL shadow bridge")
    rl_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    rl_sub = rl_parser.add_subparsers(dest="rl_action")
    rl_sub.add_parser("status", help="Muestra estado RL")
    rl_shadow = rl_sub.add_parser("shadow", help="Controla modo shadow")
    rl_shadow.add_argument("shadow_action", nargs="?", choices=("on", "off", "status"), default="status")
    rl_train = rl_sub.add_parser("train", help="Entrena politicas RL opcionales")
    rl_train_sub = rl_train.add_subparsers(dest="train_action")
    rl_train_bc = rl_train_sub.add_parser("bc", help="Entrena Behavioral Cloning desde transiciones disponibles")
    rl_train_bc.add_argument("--n-actions", type=int, default=4)
    rl_train_bc.add_argument("--n-features", type=int, default=4)
    rl_eval = rl_sub.add_parser("eval", help="Evalua politicas RL opcionales")
    rl_eval.add_argument("--n-features", type=int, default=4)

    serve_parser = sub.add_parser("serve", help="Inicia servidor API HTTP")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host de escucha (default: 127.0.0.1). Usar 0.0.0.0 requiere --token.")
    serve_parser.add_argument("--port", type=int, default=8080, help="Puerto (default: 8080)")
    serve_parser.add_argument("--token", default="", help="Token de autenticación API")
    serve_parser.add_argument("--ui-dist", default="", help="Directorio dist de la UI React (si se omite, intenta ui-react\\dist)")

    evidence_parser = sub.add_parser("evidence", help="Genera bundle de evidencias verificables")
    evidence_parser.add_argument("--mode", choices=("simulated", "real"), default="simulated", help="Modo de evidencia")
    evidence_parser.add_argument("--objective", default="community-knowledge", help="Objetivo demostrable")
    evidence_parser.add_argument("--output", help="Directorio de salida del bundle")
    evidence_parser.add_argument("--overwrite", action="store_true", help="Sobrescribe el directorio de salida")
    evidence_parser.add_argument("--test", action="store_true", help="Ejecuta la prueba interna del generador")

    runtime_parser = sub.add_parser("cpp-runtime", help="Inicia host de referencia para cpp-local")
    runtime_parser.add_argument("--host", default="127.0.0.1", help="Host del runtime")
    runtime_parser.add_argument("--port", type=int, default=8765, help="Puerto del runtime")
    runtime_parser.add_argument("--runtime-model", default="bago-cpp:default", help="Modelo expuesto por el runtime")
    runtime_parser.add_argument("--test", action="store_true", help="Ejecuta la prueba interna del host")

    scan_parser = sub.add_parser("scan", help="Herramientas de analisis portables (secrets, deps, todos, tokens, dead, names, sincerity, net, metrics, infra, heal, security, doctor, commit, git, all)")
    scan_parser.add_argument("--root", default="", help="Directorio raiz a escanear (default: cwd)")
    scan_sub = scan_parser.add_subparsers(dest="scan_cmd")

    scan_secrets = scan_sub.add_parser("secrets", help="Detecta secretos hardcodeados")
    scan_secrets.add_argument("--severity", default="warning", choices=["error", "warning", "info"])
    scan_secrets.add_argument("--json", dest="as_json", action="store_true")

    scan_deps = scan_sub.add_parser("deps", help="Audita dependencias Python")
    scan_deps.add_argument("--format", default="text", choices=["text", "md", "json"])
    scan_deps.add_argument("--pip-audit", dest="pip_audit", action="store_true")

    scan_todos = scan_sub.add_parser("todos", help="Lista TODOs, FIXMEs y HACKs")
    scan_todos.add_argument("--fixme", dest="fixme_only", action="store_true")
    scan_todos.add_argument("--count", action="store_true")
    scan_todos.add_argument("--json", dest="as_json", action="store_true")

    scan_tokens = scan_sub.add_parser("tokens", help="Detecta tokens de API expuestos")
    scan_tokens.add_argument("--fix", action="store_true", help="Instrucciones de rotacion")
    scan_tokens.add_argument("--json", dest="as_json", action="store_true")

    scan_dead = scan_sub.add_parser("dead", help="Detecta codigo muerto (Python)")
    scan_dead.add_argument("--json", dest="as_json", action="store_true")

    scan_names = scan_sub.add_parser("names", help="Valida convenciones de nombres (PEP 8)")
    scan_names.add_argument("--json", dest="as_json", action="store_true")

    scan_sub.add_parser("all", help="Ejecuta todos los scans y muestra resumen")

    scan_sincerity = scan_sub.add_parser("sincerity", help="Detecta marketing vacio en la documentacion")
    scan_sincerity.add_argument("--strict", action="store_true")
    scan_sincerity.add_argument("--path", default="")
    scan_sincerity.add_argument("--json", dest="as_json", action="store_true")

    scan_net = scan_sub.add_parser("net", help="Escanea adaptadores de red y dispositivos locales")
    scan_net.add_argument("--scan", dest="scan_net", action="store_true")
    scan_net.add_argument("--adapters", action="store_true")
    scan_net.add_argument("--json", dest="as_json", action="store_true")

    scan_metrics = scan_sub.add_parser("metrics", help="Metricas de codigo: LOC, archivos, tipos")
    scan_metrics.add_argument("--ext", default="")
    scan_metrics.add_argument("--json", dest="as_json", action="store_true")

    scan_infra = scan_sub.add_parser("infra", help="Escanea servicios locales LLM (Ollama, LM Studio, APIs)")
    scan_infra.add_argument("--quick", action="store_true")
    scan_infra.add_argument("--all", dest="all_ports", action="store_true")
    scan_infra.add_argument("--json", dest="as_json", action="store_true")

    scan_heal = scan_sub.add_parser("heal", help="Sistema inmune: detecta y repara inconsistencias")
    scan_heal.add_argument("--fix", action="store_true")
    scan_heal.add_argument("--dry-run", dest="dry_run", action="store_true")
    scan_heal.add_argument("--json", dest="as_json", action="store_true")

    scan_security = scan_sub.add_parser("security", help="Auditoria de seguridad: tokens, permisos, configs")
    scan_security.add_argument("--fix", action="store_true")
    scan_security.add_argument("--json", dest="as_json", action="store_true")

    scan_doctor = scan_sub.add_parser("doctor", help="Diagnostico de integridad del proyecto")
    scan_doctor.add_argument("--fix", action="store_true")
    scan_doctor.add_argument("--quiet", action="store_true")
    scan_doctor.add_argument("--json", dest="as_json", action="store_true")

    scan_commit = scan_sub.add_parser("commit", help="Pre-commit check rapido")
    scan_commit.add_argument("--all", dest="all_files", action="store_true")
    scan_commit.add_argument("--strict", action="store_true")
    scan_commit.add_argument("--json", dest="as_json", action="store_true")

    scan_git = scan_sub.add_parser("git", help="Snapshot del contexto git")
    scan_git.add_argument("--brief", action="store_true")
    scan_git.add_argument("--log", type=int, default=10)
    scan_git.add_argument("--json", dest="as_json", action="store_true")

    canary_parser = sub.add_parser("canary", help="Honeytokens - trampas de deteccion de intrusos")
    canary_parser.add_argument("--root", default="")
    canary_sub = canary_parser.add_subparsers(dest="canary_cmd")
    canary_deploy = canary_sub.add_parser("deploy")
    canary_deploy.add_argument("--type", default="aws_keys", choices=["aws_keys","openai_api","github_pat","telegram_bot","google_api","all"])
    canary_sub.add_parser("check")
    canary_sub.add_parser("list")
    canary_sub.add_parser("purge")

    backup_parser = sub.add_parser("backup", help="Backups del proyecto con rotacion")
    backup_parser.add_argument("--root", default="")
    backup_sub = backup_parser.add_subparsers(dest="backup_cmd")
    bc = backup_sub.add_parser("create")
    bc.add_argument("--max", type=int, default=10)
    backup_sub.add_parser("list")
    br = backup_sub.add_parser("restore")
    br.add_argument("--index", type=int, default=1)

    project_parser = sub.add_parser("project", help="Gestiona la estructura portable .bago del proyecto")
    project_parser.add_argument("--root", default="")
    project_sub = project_parser.add_subparsers(dest="project_cmd")
    project_sub.add_parser("init", help="Inicializa la estructura .bago")
    project_sub.add_parser("status", help="Muestra el estado actual")
    project_sub.add_parser("link", help="Crea el enlace portable del proyecto")

    preflight_parser = sub.add_parser("preflight", help="Ejecuta checks de preflight portables")
    preflight_parser.add_argument("--root", default="")
    preflight_parser.add_argument("--cmd", default="")

    toolsmith_parser = sub.add_parser("toolsmith", help="Gestiona toolboxes de agentes")
    toolsmith_parser.add_argument("--root", default="")
    toolsmith_parser.add_argument("--json", dest="toolsmith_json", action="store_true")
    toolsmith_sub = toolsmith_parser.add_subparsers(dest="toolsmith_cmd")
    toolsmith_sub.add_parser("catalog", help="Muestra el catalogo")
    toolsmith_assign = toolsmith_sub.add_parser("assign", help="Asigna herramientas a un agente")
    toolsmith_assign.add_argument("--task", required=True)
    toolsmith_assign.add_argument("--agent", dest="agent_name", default="")
    toolsmith_assign.add_argument("--sprint", default="backlog")
    toolsmith_sprint = toolsmith_sub.add_parser("sprint", help="Crea toolboxes para un sprint")
    toolsmith_sprint.add_argument("sprint_id")
    toolsmith_sprint.add_argument("--tasks", default="")
    toolsmith_sub.add_parser("missing", help="Lista herramientas faltantes")
    toolsmith_create = toolsmith_sub.add_parser("create", help="Crea un nuevo tool stub")
    toolsmith_create.add_argument("tool_name")
    toolsmith_create.add_argument("--desc", default="")
    toolsmith_create.add_argument("--category", default="general")
    toolsmith_listen = toolsmith_sub.add_parser("listen", help="Escucha eventos del bus neural")
    toolsmith_listen.add_argument("--limit", type=int, default=1)

    agent_parser = sub.add_parser("agent", help="Gestiona spiral agents")
    agent_parser.add_argument("--root", default="")
    agent_sub = agent_parser.add_subparsers(dest="agent_cmd")
    agent_spawn = agent_sub.add_parser("spawn", help="Crea un agente")
    agent_spawn.add_argument("agent_id")
    agent_spawn.add_argument("--phase", type=int, default=0)
    agent_spawn.add_argument("--skills", default="")
    agent_sub.add_parser("list", help="Lista agentes")
    agent_run = agent_sub.add_parser("run", help="Ejecuta un agente")
    agent_run.add_argument("agent_id")
    agent_kill = agent_sub.add_parser("kill", help="Desactiva un agente")
    agent_kill.add_argument("agent_id")
    agent_sub.add_parser("status", help="Muestra consonancia entre agentes")

    route_parser = sub.add_parser("route", help="Ruta tareas al mejor agente AI")
    route_parser.add_argument("--root", default="")
    route_parser.add_argument("--task", default="")
    route_parser.add_argument("--json", dest="route_json", action="store_true")
    route_parser.add_argument("--history", action="store_true")
    route_parser.add_argument("--limit", type=int, default=10)
    route_parser.add_argument("--no-classifier", action="store_true")

    inv_parser = sub.add_parser("inventory", help="Cataloga capacidades del proyecto")
    inv_parser.add_argument("--root", default="")
    inv_parser.add_argument("--format", default="text", choices=["text","md","json"])

    args = parser.parse_args(argv)

    if args.command in ("chat", "launch", "start") or args.command is None:
        return cmd_chat(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "install":
        return cmd_install(args)
    elif args.command == "uninstall":
        return cmd_uninstall(args)
    elif args.command == "claim":
        return cmd_claim(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "llm":
        return cmd_llm(args)
    elif args.command == "engine":
        return cmd_engine(args)
    elif args.command == "appdata":
        return cmd_appdata(args)
    elif args.command == "cmd-rl":
        return cmd_cmd_rl(args)
    elif args.command == "rl":
        return cmd_rl(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "evidence":
        return cmd_evidence(args)
    elif args.command == "cpp-runtime":
        return cmd_cpp_runtime(args)
    elif args.command == "scan":
        return cmd_scan(args)
    elif args.command == "canary":
        return cmd_canary(args)
    elif args.command == "backup":
        return cmd_backup(args)
    elif args.command == "project":
        return cmd_project(args)
    elif args.command == "preflight":
        return cmd_preflight(args)
    elif args.command == "toolsmith":
        return cmd_toolsmith(args)
    elif args.command == "agent":
        return cmd_agent(args)
    elif args.command == "route":
        return cmd_route(args)
    elif args.command == "inventory":
        return cmd_inventory(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        # Quick smoke test
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg = {"runtime": {"default_provider": "codex", "default_model": "gpt-5.4-mini"}}
            (Path(td) / "install_config.json").write_text(json.dumps(cfg), encoding="utf-8")
            assert _load_install_config(Path(td))["runtime"]["default_provider"] == "codex"
            assert main(["--base-path", td, "config", "set", "providers.cpp-local.enabled", "true"]) == 0
            assert main(["--base-path", td, "config", "get", "providers.cpp-local.enabled"]) == 0
            assert main(["--base-path", td, "llm", "list"]) == 0
            assert main(["--base-path", td, "llm", "start", "--provider", "ollama-local", "--model", "llama3.2:3b", "--dry-run"]) == 0
            assert (Path(td) / ".bago" / "state" / "llm_start.json").exists()
            assert main(["--base-path", td, "llm", "start", "--provider", "cpp-local", "--dry-run"]) == 1
            assert main(["--base-path", td, "engine", "status"]) == 0
            assert main(["--base-path", td, "appdata", "status"]) == 0
            assert main(["--base-path", td, "cmd-rl", "status"]) == 0
            assert main(["--base-path", td, "rl", "status"]) == 0
            assert main(["--base-path", td, "rl", "shadow", "off"]) == 0
            assert main(["--base-path", td, "rl", "shadow", "on"]) == 0
            assert main(["--base-path", td, "rl", "train", "bc"]) == 0
            assert main(["--base-path", td, "rl", "eval"]) == 0
            assert main(["--base-path", td, "evidence", "--test"]) == 0
            assert main(["--base-path", td, "install", "--dry-run"]) == 0
            tmp_install = Path(td) / "fake-install"
            tmp_install.mkdir()
            (tmp_install / "keep.txt").write_text("x", encoding="utf-8")
            assert main(["--base-path", td, "uninstall", "--install-dir", str(tmp_install), "--dry-run"]) == 0
        print("launcher.py --test: ALL PASS")
        raise SystemExit(0)
    raise SystemExit(main())
