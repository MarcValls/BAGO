#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from bago_core.resolver import add_piece_paths

BAGO_ROOT = Path(__file__).resolve().parents[2]
add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")

def cmd_engine(args: argparse.Namespace) -> int:
    from bago_core.bago_true_bridge import collect_status, render_status

    action = args.engine_action or "status"
    if action != "status":
        print("Uso: bago engine status")
        return 1
    status = collect_status(args.true_root or None, args.appdata_root or None)
    print(render_status(status, section="engine"))
    return 0

def cmd_appdata(args: argparse.Namespace) -> int:
    from bago_core.bago_true_bridge import collect_status, render_status

    action = args.appdata_action or "status"
    if action != "status":
        print("Uso: bago appdata status")
        return 1
    status = collect_status(args.true_root or None, args.appdata_root or None)
    print(render_status(status, section="appdata"))
    return 0

def cmd_cmd_rl(args: argparse.Namespace) -> int:
    from bago_core.bago_true_bridge import collect_status, render_status

    action = args.cmd_rl_action or "status"
    if action != "status":
        print("Uso: bago cmd-rl status")
        return 1
    status = collect_status(args.true_root or None, args.appdata_root or None)
    print(render_status(status, section="cmd-rl"))
    return 0

def cmd_rl(args: argparse.Namespace) -> int:
    from bago_core.rl_bridge import RLBridge, render_status

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
        from bago_core.rl_policies import render_policy_report, train_bc_policy
        report = train_bc_policy(args.base_path, args.n_actions, args.n_features)
        print(render_policy_report(report, "BAGO RL TRAIN BC"))
        return 0

    if action == "eval":
        from bago_core.rl_policies import eval_bc_policy, render_policy_report
        report = eval_bc_policy(args.base_path, args.n_features)
        print(render_policy_report(report, "BAGO RL EVAL"))
        return 0

    print("Uso: bago rl [status|shadow|train|eval]")
    return 1

def cmd_validate(args: argparse.Namespace) -> int:
    """Gate real de validacion -- no solo health checks de providers."""
    import ast
    import json as _json
    import re
    import tempfile

    def _is_bago_root(candidate: Path) -> bool:
        return (candidate / "bago_core" / "cli.py").exists() and (candidate / ".bago").is_dir()

    requested_base = Path(getattr(args, "base_path", "") or ".").resolve()
    module_base = BAGO_ROOT.resolve()
    base = requested_base if _is_bago_root(requested_base) else module_base
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
            line += f" -- {detail}"
        print(line)

    print("\nBAGO VALIDATE\n" + "-" * 40)

    # -- 1. Syntax: compilar todos los .py en el estado y en bago_core/ ---------
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

    # -- 2. Contratos presentes -------------------------------------------------
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

    # -- 3. auto_allow_tools = false --------------------------------------------
    config_file = bago_dir / "config.json"
    config_manager_file = bago_dir / "core" / "config_manager.py"
    auto_allow_ok = False
    runtime_val: Any = None
    default_val: Any = None
    config_detail = "config.json/config_manager.py no encontrados"
    if config_file.exists():
        try:
            # PowerShell 5.1 emits a BOM for `Set-Content -Encoding UTF8`.
            # Installed runtime configs must be accepted in either UTF-8 form.
            cfg = _json.loads(config_file.read_text(encoding="utf-8-sig"))
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
    # If no runtime config exists, the default governs; only require default_val is False.
    # If a runtime config exists, it must also explicitly disable auto_allow_tools.
    if runtime_val is None:
        auto_allow_ok = default_val is False
    else:
        auto_allow_ok = runtime_val is False and default_val is False
    if config_detail.startswith("config.json"):
        config_detail = f"runtime={runtime_val}, default={default_val}"
    _check("auto_allow_tools_false", auto_allow_ok, config_detail)

    # -- 4. execute_command sin shell=True expuesto -----------------------------
    tool_registry = bago_dir / "core" / "tool_registry.py"
    shell_true_ok = tool_registry.exists()
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

    # -- 5. API no arranca en 0.0.0.0 por defecto ------------------------------
    bridge_file = bago_dir / "api" / "bridge.py"
    api_host_ok = bridge_file.exists()
    api_detail = "bridge.py no encontrado"
    if bridge_file.exists():
        src = bridge_file.read_text(encoding="utf-8")
        # Buscar HTTPServer(("0.0.0.0" como hardcode (no dentro de self.host)
        hardcoded = re.search(r'HTTPServer\(\s*\(\s*["\']0\.0\.0\.0["\']', src)
        api_host_ok = hardcoded is None
        api_detail = "hardcode 0.0.0.0 detectado" if hardcoded else "host proviene de parametro"
    _check("api_host_not_hardcoded", api_host_ok, api_detail)

    # -- 6. CORS sin wildcard --------------------------------------------------
    cors_ok = bridge_file.exists()
    cors_detail = "bridge.py no encontrado"
    if bridge_file.exists():
        src = bridge_file.read_text(encoding="utf-8")
        wildcard = 'Access-Control-Allow-Origin", "*"' in src or "Access-Control-Allow-Origin', '*'" in src
        cors_ok = not wildcard
        cors_detail = "sin wildcard" if cors_ok else "wildcard CORS detectado"
    _check("cors_no_wildcard", cors_ok, cors_detail)

    # -- 7. .gitignore excluye la carpeta de estado -----------------------------
    gitignore = base / ".gitignore"
    gitignore_ok = False
    gitignore_detail = ".gitignore no encontrado"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        gitignore_ok = ".gabo/state/" in content or ".gabo/state" in content
        gitignore_detail = "excluye la carpeta de estado" if gitignore_ok else "carpeta de estado no excluida"
    _check("state_excluded_from_vcs", gitignore_ok, gitignore_detail)

    # -- 8. Culpas abiertas -----------------------------------------------------
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

    # -- 8. Claims ledger: no hay claims fallados -------------------------------
    claims_file = base / "evidence" / "claims.jsonl"
    claims_ok = True
    claims_detail = "sin claims registrados"
    if claims_file.exists():
        add_piece_paths("core.package")
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

    # -- 9. Provider health (comportamiento original, ahora un check mas) -------
    print("  [->] provider_health (requiere providers activos):")
    add_piece_paths("core.package")
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
                        print(f"       [{marker}] {name:15} -- {health.detail}")
                        if health.ok:
                            any_provider_ok = True
                    except Exception as exc:
                        print(f"       [·] {name:15} -- error: {exc}")
            finally:
                mgr.close()
        _check("at_least_one_provider_healthy", any_provider_ok,
               "al menos un provider responde" if any_provider_ok else "ningun provider disponible (normal si no hay LLM activo)")
    except Exception as exc:
        _check("at_least_one_provider_healthy", False, f"error al cargar session_manager: {exc}")

    # In CI, no providers are configured. Downgrade the provider health check from
    # a blocking gate to a skipped check so CI does not fail on missing LLMs.
    if not any([c["status"] == "PASS" for c in checks if c["check"] == "at_least_one_provider_healthy"]):
        import os as _os
        if _os.environ.get("CI") or _os.environ.get("GITHUB_ACTIONS"):
            for c in checks:
                if c["check"] == "at_least_one_provider_healthy" and c["status"] == "FAIL":
                    c["status"] = "SKIP"
                    c["detail"] += " [skipped in CI]"
                    fails -= 1
                    break

    # -- 10. Translator layer: encode->decode roundtrip por cada pieza ----------
    try:
        from bago_core.translators import smoke_test_all
        translator_results = smoke_test_all()
        ok_count = sum(1 for r in translator_results if r.get("ok"))
        translator_ok = ok_count == len(translator_results)
        _check(
            "translators_roundtrip",
            translator_ok,
            f"{ok_count}/{len(translator_results)} piezas roundtrip OK" if translator_results else "no hay piezas traductoras",
        )
    except Exception as exc:
        _check("translators_roundtrip", False, f"error al cargar translator layer: {exc}")

    # -- Resultado final --------------------------------------------------------
    print("\n" + "-" * 40)
    if fails == 0:
        print(f"✓ VALIDATE PASS -- {len(checks)} checks OK")
    else:
        print(f"✗ VALIDATE FAIL -- {fails}/{len(checks)} checks fallaron")
        for c in checks:
            if c["status"] == "FAIL":
                print(f"  -> [{c['check']}]: {c['detail']}")
    print()
    return 0 if fails == 0 else 1
