#!/usr/bin/env python3
"""
debt_guard.py — BAGO Guardián de Deuda Técnica

Previene que patrones de deuda técnica ENTREN al repositorio.
Se instala como git pre-commit hook. Bloquea commits con patrones configurados.

Diferencia con debt_scanner.py:
  scanner  → audita deuda EXISTENTE (diagnóstico)
  guard    → bloquea deuda NUEVA antes de que entre (prevención)

Comandos:
  install          Instala como git pre-commit hook
  uninstall        Elimina el hook instalado por BAGO
  check            Verifica archivos staged (usado por el hook)
  check --all      Verifica todos los archivos Python del proyecto
  config           Muestra/modifica la configuración de reglas activas
  status           Muestra estado del hook y reglas activas

Integrado como:
  bago guard [install|uninstall|check|config|status] [--root DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
from _path_helper import ensure_tools_path
ensure_tools_path()  # noqa: E402
try:
    from bago_utils import get_scan_root
except ImportError:
    def get_scan_root(override=None):
        return Path(override) if override else Path(os.environ.get("BAGO_SCAN_ROOT", os.getcwd()))

try:
    from debt_scanner import (
        DebtReport, Finding, scan,
        detect_anonymous_parsers, detect_silent_exceptions,
        detect_wildcard_imports, detect_large_files,
        detect_long_functions, SEVERITY_ORDER, _python_files, _read, _rel,
    )
    _SCANNER_AVAILABLE = True
except ImportError:
    _SCANNER_AVAILABLE = False

_BACKEND_ROOT = _THIS_DIR.parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
from bago_core.cli_execution import execute_cli_effect
from execution_request import build_execution_request


def _repository_session_id(root: Path) -> str:
    canonical = root.resolve(strict=True)
    return "repository:" + hashlib.sha256(str(canonical).encode("utf-8")).hexdigest()[:20]


def _execute_repository_mutation(
    root: Path,
    *,
    resource: str,
    operation: str,
    content: str | None,
    before_bytes: bytes,
) -> dict[str, Any]:
    canonical = root.resolve(strict=True)
    target: dict[str, Any] = {
        "repository_root": str(canonical),
        "resource": resource,
        "operation": operation,
        "before_sha256": hashlib.sha256(before_bytes).hexdigest() if before_bytes else "",
    }
    if content is not None:
        target["content"] = content
        target["after_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    request = build_execution_request(
        effect_id="repository.guard.manage",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=_repository_session_id(canonical),
        source_surface=f"cli.debt_guard.{resource}.{operation}",
        target=target,
        arguments={},
        scope="workspace",
    )
    result, _authorization = execute_cli_effect(
        request,
        confirmation_text=(
            f"{operation} debt guard {resource} en {canonical}; "
            f"contenido sha256 {target.get('after_sha256', 'delete')}"
        ),
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Repository guard mutation returned no success receipt")
    return result

GUARD_VERSION = "1.0.0"

# ── Configuración de reglas por defecto ───────────────────────────────────────
DEFAULT_CONFIG: dict[str, Any] = {
    "version": GUARD_VERSION,
    "enabled": True,
    "block_on_error": True,        # bloquea commit si hay errores
    "block_on_warning": False,     # sólo avisa en warnings
    "rules": {
        "D01": {"active": True,  "action": "block",  "desc": "Parsers argparse anónimos"},
        "D02": {"active": True,  "action": "warn",   "desc": "Archivos demasiado grandes"},
        "D03": {"active": True,  "action": "warn",   "desc": "Funciones demasiado largas"},
        "D04": {"active": False, "action": "warn",   "desc": "Demasiados parámetros"},
        "D05": {"active": True,  "action": "warn",   "desc": "Rutas absolutas hardcodeadas"},
        "D06": {"active": True,  "action": "block",  "desc": "Excepciones tragadas en silencio"},
        "D07": {"active": True,  "action": "block",  "desc": "Wildcard imports"},
        "D08": {"active": False, "action": "warn",   "desc": "sys.path.insert hacks"},
        "D09": {"active": False, "action": "warn",   "desc": "Funciones sin type hints"},
        "D10": {"active": False, "action": "warn",   "desc": "Nombres de función duplicados"},
    },
    "exclude_paths": [
        "test_",
        "_test.py",
        "tests/",
        ".bago/tools/",            # las sondas no se guardan a sí mismas
    ],
}

CONFIG_FILENAME = ".bago/debt_guard_config.json"
HOOK_MARKER    = "# BAGO-DEBT-GUARD"
HOOK_FILENAME  = ".git/hooks/pre-commit"

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _config_path(root: Path) -> Path:
    return root / CONFIG_FILENAME


def load_config(root: Path) -> dict[str, Any]:
    path = _config_path(root)
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Merge con defaults para claves nuevas
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        merged["rules"] = {**DEFAULT_CONFIG["rules"], **data.get("rules", {})}
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(root: Path, config: dict[str, Any]) -> None:
    path = _config_path(root)
    before = path.read_bytes() if path.is_file() else b""
    content = json.dumps(config, indent=2, ensure_ascii=False)
    _execute_repository_mutation(
        root, resource="config", operation="write", content=content,
        before_bytes=before,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  STAGED FILES
# ══════════════════════════════════════════════════════════════════════════════

def _staged_python_files(root: Path) -> list[Path]:
    """Devuelve los .py staged (git diff --cached)."""
    canonical = root.resolve(strict=True)
    request = build_execution_request(
        effect_id="repository.inspect",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=_repository_session_id(canonical),
        source_surface="cli.debt_guard.staged_files",
        target={"operation": "staged_files", "repository_root": str(canonical)},
        arguments={},
        scope="workspace",
    )
    result, _authorization = execute_cli_effect(
        request, confirmation_text=f"leer los archivos staged para Debt Guard en {canonical}"
    )
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Repository inspection returned no success receipt")
    files = []
    for line in str(result.get("stdout") or "").split("\0"):
        if line.endswith(".py"):
            candidate = canonical / line
            if candidate.is_symlink():
                continue
            try:
                full = candidate.resolve(strict=True)
                full.relative_to(canonical)
            except (OSError, ValueError):
                continue
            if full.is_file():
                files.append(full)
    return files


def _is_excluded(path: Path, root: Path, exclude_paths: list[str]) -> bool:
    rel = _rel(path, root).replace("\\", "/")
    return any(exc in rel for exc in exclude_paths)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPROBACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _check_files(
    files: list[Path],
    root: Path,
    config: dict[str, Any],
) -> tuple[list[Finding], list[Finding]]:
    """
    Devuelve (blocked, warned):
    - blocked: findings con action=block (impiden commit)
    - warned:  findings con action=warn  (avisos sin bloqueo)
    """
    if not _SCANNER_AVAILABLE:
        print("[Guard] debt_scanner.py no disponible — omitiendo checks", file=sys.stderr)
        return [], []

    rules = config.get("rules", {})
    exclude = config.get("exclude_paths", [])
    blocked: list[Finding] = []
    warned: list[Finding] = []

    for path in files:
        if _is_excluded(path, root, exclude):
            continue
        src = _read(path)
        if not src:
            continue

        # Ejecutar detectores por archivo
        from debt_scanner import (
            detect_anonymous_parsers, detect_large_files, detect_long_functions,
            detect_many_params, detect_hardcoded_paths, detect_silent_exceptions,
            detect_wildcard_imports, detect_syspath_hacks, detect_missing_type_hints,
        )
        detectors = {
            "D01": detect_anonymous_parsers,
            "D02": detect_large_files,
            "D03": detect_long_functions,
            "D04": detect_many_params,
            "D05": detect_hardcoded_paths,
            "D06": detect_silent_exceptions,
            "D07": detect_wildcard_imports,
            "D08": detect_syspath_hacks,
            "D09": detect_missing_type_hints,
        }

        for code, detector in detectors.items():
            rule = rules.get(code, {})
            if not rule.get("active", False):
                continue
            findings = detector(path, src, root)
            for f in findings:
                if rule.get("action") == "block":
                    blocked.append(f)
                else:
                    warned.append(f)

    return blocked, warned


def _print_findings(label: str, icon: str, findings: list[Finding]) -> None:
    if not findings:
        return
    print(f"\n  {icon} {label} ({len(findings)}):")
    for f in findings:
        print(f"    {f.code}  {f.file}:{f.line}")
        print(f"         {f.message}")
        print(f"         → {f.remedy}")


# ══════════════════════════════════════════════════════════════════════════════
#  HOOK
# ══════════════════════════════════════════════════════════════════════════════

_HOOK_SCRIPT = """\
#!/bin/sh
{marker}
# Instalado por BAGO debt_guard — no editar manualmente
python "{guard_path}" check
"""


def _hook_path(root: Path) -> Path:
    return root / HOOK_FILENAME


def cmd_install(root: Path) -> int:
    hook = _hook_path(root)
    git_dir = root / ".git"
    if not git_dir.exists():
        print(f"[Guard] No es un repositorio git: {root}")
        return 1

    guard_path = str(_THIS_DIR / "debt_guard.py").replace("\\", "/")

    # Si ya existe un hook, añadir al final sin romperlo
    before_bytes = hook.read_bytes() if hook.is_file() else b""
    if before_bytes:
        content = before_bytes.decode("utf-8")
        if HOOK_MARKER in content:
            print("[Guard] Hook ya instalado.")
            return 0
        # Append al hook existente
        new_content = content.rstrip() + "\n\n" + _HOOK_SCRIPT.format(
            marker=HOOK_MARKER, guard_path=guard_path,
        )
    else:
        new_content = _HOOK_SCRIPT.format(marker=HOOK_MARKER, guard_path=guard_path)

    _execute_repository_mutation(
        root, resource="hook", operation="write", content=new_content,
        before_bytes=before_bytes,
    )
    print(f"[Guard] Hook instalado en {hook}")
    print(f"[Guard] Cada 'git commit' ejecutará debt_guard.py check")
    return 0


def cmd_uninstall(root: Path) -> int:
    hook = _hook_path(root)
    if not hook.exists():
        print("[Guard] No hay hook instalado.")
        return 0

    before_bytes = hook.read_bytes()
    content = before_bytes.decode("utf-8")
    if HOOK_MARKER not in content:
        print("[Guard] El hook existente no fue instalado por BAGO. No se toca.")
        return 0

    # Eliminar bloque BAGO del hook
    lines = content.splitlines()
    new_lines = []
    skip = False
    for line in lines:
        if HOOK_MARKER in line:
            skip = True
        if not skip:
            new_lines.append(line)
        # Fin del bloque: la siguiente línea limpia reactiva
        if skip and line.strip() == "" and new_lines:
            skip = False

    new_content = "\n".join(new_lines).rstrip() + "\n"

    if new_content.strip() in ("#!/bin/sh", ""):
        _execute_repository_mutation(
            root, resource="hook", operation="delete", content=None,
            before_bytes=before_bytes,
        )
        print("[Guard] Hook eliminado completamente.")
    else:
        _execute_repository_mutation(
            root, resource="hook", operation="write", content=new_content,
            before_bytes=before_bytes,
        )
        print("[Guard] Bloque BAGO eliminado del hook existente.")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
#  SUBCOMANDOS
# ══════════════════════════════════════════════════════════════════════════════

def cmd_check(root: Path, all_files: bool, config: dict[str, Any]) -> int:
    if all_files:
        files = list(_python_files(root)) if _SCANNER_AVAILABLE else []
        source_label = "todos los archivos Python"
    else:
        files = _staged_python_files(root)
        source_label = "archivos staged"

    if not files:
        print(f"[Guard] Sin archivos .py en {source_label}. OK.")
        return 0

    blocked, warned = _check_files(files, root, config)

    _print_findings("BLOQUEADO (impiden commit)", "🔴", blocked)
    _print_findings("AVISO (no bloquea)", "🟡", warned)

    if not blocked and not warned:
        print(f"[Guard] ✅ Sin deuda nueva en {source_label}.")
        return 0

    if warned and not blocked:
        print(f"\n[Guard] 🟡 {len(warned)} aviso(s) — commit permitido.")
        return 0

    if blocked:
        print(f"\n[Guard] 🔴 COMMIT BLOQUEADO — {len(blocked)} patrón(es) de deuda crítica.")
        print( "[Guard]    Corrige los errores o usa `git commit --no-verify` para omitir.")
        return 1

    return 0


def cmd_config(root: Path, config: dict[str, Any], args: argparse.Namespace) -> int:
    action = getattr(args, "config_action", "show")

    if action == "show" or action is None:
        print(f"\n  Configuración debt_guard — {root / CONFIG_FILENAME}")
        print(f"  Guard {'habilitado' if config['enabled'] else 'DESHABILITADO'}")
        print(f"  Bloquea en error:   {config['block_on_error']}")
        print(f"  Bloquea en warning: {config['block_on_warning']}")
        print()
        print(f"  {'Código':<6} {'Activa':<8} {'Acción':<8} Descripción")
        print(f"  {'──────':<6} {'──────':<8} {'──────':<8} ───────────────────────────")
        for code, rule in config["rules"].items():
            active = "✓" if rule.get("active") else "·"
            action_s = rule.get("action", "warn")
            desc = rule.get("desc", "")
            print(f"  {code:<6} {active:<8} {action_s:<8} {desc}")
        print()
        return 0

    if action == "enable":
        code = getattr(args, "rule_code", "").upper()
        if code not in config["rules"]:
            print(f"[Guard] Código desconocido: {code}")
            return 1
        config["rules"][code]["active"] = True
        save_config(root, config)
        print(f"[Guard] Regla {code} activada.")
        return 0

    if action == "disable":
        code = getattr(args, "rule_code", "").upper()
        if code not in config["rules"]:
            print(f"[Guard] Código desconocido: {code}")
            return 1
        config["rules"][code]["active"] = False
        save_config(root, config)
        print(f"[Guard] Regla {code} desactivada.")
        return 0

    if action == "set-action":
        code   = getattr(args, "rule_code", "").upper()
        action_val = getattr(args, "action_value", "warn")
        if code not in config["rules"]:
            print(f"[Guard] Código desconocido: {code}")
            return 1
        if action_val not in ("block", "warn"):
            print("[Guard] Acción debe ser 'block' o 'warn'")
            return 1
        config["rules"][code]["action"] = action_val
        save_config(root, config)
        print(f"[Guard] Regla {code} → acción '{action_val}'.")
        return 0

    if action == "reset":
        save_config(root, DEFAULT_CONFIG)
        print("[Guard] Configuración restaurada a defaults.")
        return 0

    return 0


def cmd_status(root: Path, config: dict[str, Any]) -> int:
    hook = _hook_path(root)
    hook_installed = hook.exists() and HOOK_MARKER in (hook.read_text(encoding="utf-8") if hook.exists() else "")
    active_rules = [c for c, r in config["rules"].items() if r.get("active")]
    blocked_rules = [c for c, r in config["rules"].items() if r.get("active") and r.get("action") == "block"]

    print(f"\n  BAGO Debt Guard v{GUARD_VERSION}")
    print(f"  Raíz:           {root}")
    print(f"  Guard:          {'habilitado' if config['enabled'] else 'DESHABILITADO'}")
    print(f"  Hook git:       {'instalado ✓' if hook_installed else 'NO instalado'}")
    print(f"  Reglas activas: {len(active_rules)} ({', '.join(active_rules)})")
    print(f"  Bloquean:       {', '.join(blocked_rules) or 'ninguna'}")
    print(f"  Config:         {_config_path(root)}")
    print()
    if not hook_installed:
        print("  Para instalar el hook: bago guard install")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="debt_guard",
        description="BAGO Guardián de Deuda Técnica — previene deuda antes de commitear",
    )
    parser.add_argument("--root", default="", help="Raíz del proyecto (default: cwd)")
    parser.add_argument("--test", action="store_true", help="Ejecuta tests internos")
    sub = parser.add_subparsers(dest="cmd")

    install_p   = sub.add_parser("install",   help="Instala hook pre-commit")          # noqa: F841
    uninstall_p = sub.add_parser("uninstall", help="Elimina hook pre-commit")           # noqa: F841
    status_p    = sub.add_parser("status",    help="Muestra estado del guard y reglas") # noqa: F841

    check_p = sub.add_parser("check", help="Verifica archivos staged (o todos con --all)")
    check_p.add_argument("--all", dest="all_files", action="store_true",
                         help="Verificar todos los .py, no sólo staged")

    config_p = sub.add_parser("config", help="Gestiona reglas activas")
    config_sub = config_p.add_subparsers(dest="config_action")
    config_sub.add_parser("show",  help="Muestra configuración actual")   # noqa: F841
    config_sub.add_parser("reset", help="Restaura configuración a defaults") # noqa: F841
    cfg_enable = config_sub.add_parser("enable",  help="Activa una regla")
    cfg_enable.add_argument("rule_code", help="Código de regla (D01…D10)")
    cfg_disable = config_sub.add_parser("disable", help="Desactiva una regla")
    cfg_disable.add_argument("rule_code", help="Código de regla (D01…D10)")
    cfg_set = config_sub.add_parser("set-action", help="Cambia acción de una regla (block|warn)")
    cfg_set.add_argument("rule_code",    help="Código de regla (D01…D10)")
    cfg_set.add_argument("action_value", help="block o warn")

    args = parser.parse_args(argv)

    if args.test:
        print("Las pruebas viven en backend/tests/test_debt_guard.py; ejecútalas con pytest.", file=sys.stderr)
        return 2

    root   = get_scan_root(args.root or None)
    config = load_config(root)

    if not config.get("enabled", True) and args.cmd == "check":
        print("[Guard] Guard deshabilitado — omitiendo checks.")
        return 0

    if args.cmd == "install":
        return cmd_install(root)
    elif args.cmd == "uninstall":
        return cmd_uninstall(root)
    elif args.cmd == "check":
        return cmd_check(root, getattr(args, "all_files", False), config)
    elif args.cmd == "config":
        return cmd_config(root, config, args)
    elif args.cmd == "status":
        return cmd_status(root, config)
    else:
        # Invocado sin subcomando = modo hook (check staged)
        return cmd_check(root, all_files=False, config=config)


if __name__ == "__main__":
    sys.exit(main())
