from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from bago_core.launcher._paths import (
    BAGO_ROOT, BAGO_CORE_DIR, TOOLS, CORE,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, default_user_home,
)
from bago_core.launcher._config import (
    load_bp, load_dispatcher, load_context, load_registry_mod,
    build_commands, build_deprecated_map, get_module_for_cmd,
    COMMANDS, DEPRECATED_MAP,
)

from bago_core.launcher._preflight import _run_preflight, _check_risk, _requires_registry_safety
from bago_core.launcher._preflight import _run_preflight, _check_risk, _requires_registry_safety, _start_session, _load_telemetry, _run_self_test, _detect_session_mode, _persist_session_mode
from bago_core.launcher._dispatch import _dispatch, _cmd_session_last, _cmd_session_history, _cmd_telemetry, _cmd_registry, _find_tool, _cmd_neural, _cmd_heal_paths, _cmd_npath_dispatch
from bago_core.launcher._dev import _cmd_dev, _install_extensions, _cmd_extensions, _read_state, _write_state, _set_mode, _is_template_seed, _scaffold_project, _prompt_mode, _cmd_versions, _resolve_engine_profile, _auto_sync
from bago_core.launcher._cmds import _cmd_token_analytics, _cmd_token_brake, _cmd_spiral_prompt, _cmd_autonomous, _cmd_inbox_launcher, _cmd_router



# Commands that trigger auto-sync of repo context
_SYNC_CMDS = frozenset({
    "setup", "session", "cosecha", "audit", "dashboard", "detector", "task",
})
def main():
    # Deteccion de modo de sesion para agentes
    _persist_session_mode(_detect_session_mode())

    args = sys.argv[1:]

    if args and args[0] in ("--version", "-V"):
        print("bago 3.4.5")
        return

    # ── First-run wizard ───────────────────────────────────────────────────────
    # Fires on any first run (with or without args) unless bypassed.
    # CI/BAGO_SKIP_WIZARD bypass is handled inside bago_wizard.py itself.
    _wizard_marker = BAGO_ROOT / "state" / "install_complete.json"
    _skip_wizard = (
        "--skip-wizard" in args
        or os.environ.get("CI")
        or os.environ.get("BAGO_SKIP_WIZARD")
    )
    if not _wizard_marker.exists() and not _skip_wizard:
        _wiz_path = TOOLS / "bago_wizard.py"
        if _wiz_path.exists():
            _wiz_result = subprocess.run(
                [sys.executable, str(_wiz_path)],
                cwd=str(BAGO_ROOT.parent),
            )
            if _wiz_result.returncode != 0:
                sys.exit(_wiz_result.returncode)
            if not args:
                return  # No command given: wizard already showed banner, we're done
            # With args: continue below to dispatch the requested command

    # Remove --skip-wizard from args before dispatching
    args = [a for a in args if a != "--skip-wizard"]

    # Prompt de primera ejecución (solo sin args y con TTY)
    if not args and sys.stdin.isatty() and _is_template_seed():
        result = _prompt_mode()
        if result in ("done", "error", "invalid"):
            sys.exit(1 if result == "error" else 0)
        # result == "banner" → continúa al banner normal

    if not args:
        if sys.stdin.isatty():
            # Menú principal interactivo (curses TUI)
            result = subprocess.run(
                [sys.executable, str(TOOLS / "bago_menu.py")],
                cwd=str(BAGO_ROOT.parent)
            )
            sys.exit(result.returncode)
        else:
            subprocess.run(
                [sys.executable, str(TOOLS / "bago_banner.py")],
                cwd=str(BAGO_ROOT.parent)
            )
        return

    cmd = args[0].lower()
    rest = args[1:]
    preflight_only = "--preflight" in rest
    skip_preflight = "--skip-preflight" in rest
    clean_rest = [a for a in rest if a not in ("--preflight", "--skip-preflight")]

    if cmd in COMMANDS and (preflight_only or _requires_registry_safety(cmd)):
        _dispatch(
            cmd,
            clean_rest,
            preflight_only=preflight_only,
            skip_preflight=skip_preflight,
        )
        return

    # Only run auto-sync for commands that need fresh context.
    # Avoids writing repo_context.json (git-tracked generated_artifact) on
    # every bago invocation (bago help, bago health, etc. were dirtying git status).
    if cmd in _SYNC_CMDS:
        _auto_sync()

    if cmd == "setup":
        subprocess.run(
            [sys.executable, str(TOOLS / "repo_context_guard.py"), "sync"],
            cwd=str(BAGO_ROOT.parent)
        )
        _install_extensions()
    elif cmd == "extensions":
        _cmd_extensions()
    elif cmd == "versions":
        _cmd_versions()
    elif cmd == "last":
        _cmd_session_last(rest)
    elif cmd == "history":
        _cmd_session_history()
    elif cmd == "telemetry":
        _cmd_telemetry(rest)
    elif cmd == "registry":
        _cmd_registry()
    elif cmd == "neural":
        _cmd_neural(rest)
    elif cmd == "heal-paths":
        _cmd_heal_paths(rest)
    elif cmd == "npath":
        _cmd_npath_dispatch(rest)
    elif cmd == "dev":
        _cmd_dev(rest)
    elif cmd == "wizard":
        subprocess.run(
            [sys.executable, str(TOOLS / "bago_wizard.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd in ("rubber-duck", "rubber_duck"):
        subprocess.run(
            [sys.executable, str(TOOLS / "bago_rubber_duck.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "siembra" and rest and rest[0].lower() in ("ideas", "idea", "seed", "semilla"):
        # Disambiguation: "bago siembra ideas" → ideas catalog (emit_ideas.py)
        # "bago siembra" alone = project management (siembra_manager.py)
        print("  💡 Redirigiendo 'bago siembra ideas' → bago ideas (catálogo de ideas W2)")
        print("     Tip: usa 'bago siembra' para gestionar proyectos hijo, 'bago ideas' para el catálogo.\n")
        subprocess.run(
            [sys.executable, str(TOOLS / "emit_ideas.py")] + rest[1:],
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd in ("seed-ideas", "semilla-ideas", "ideas-seed"):
        # Alias explícito para sembrar catálogo de ideas
        subprocess.run(
            [sys.executable, str(TOOLS / "emit_ideas.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "agent":
        # Multi-Agent Gateway — orquesta herramientas BAGO desde cualquier LLM
        subprocess.run(
            [sys.executable, str(BAGO_ROOT / "agents" / "agent_gateway.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "model":
        # Gestión dinámica de modelos por agente
        subprocess.run(
            [sys.executable, str(TOOLS / "agent_model_manager.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "assign":
        # Asignación de tareas a agentes/roles CAP
        subprocess.run(
            [sys.executable, str(TOOLS / "task_assign.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "benchmark":
        # Banco de pruebas de eficiencia BAGO
        subprocess.run(
            [sys.executable, str(TOOLS / "bago_benchmark.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "seed":
        # BAGO Seed — planta huella mínima en proyecto externo
        subprocess.run(
            [sys.executable, str(TOOLS / "bago_seed.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "validate":
        subprocess.run([sys.executable, str(TOOLS / "validate.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "validate-goal":
        subprocess.run([sys.executable, str(TOOLS / "goal_validator.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "health":
        subprocess.run([sys.executable, str(TOOLS / "health_score.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "audit":
        subprocess.run([sys.executable, str(TOOLS / "audit_v2.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "version":
        subprocess.run([sys.executable, str(TOOLS / "version_truth.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "autonomous":
        subprocess.run([sys.executable, str(CORE / "autonomous_loop.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "git-dirty":
        subprocess.run([sys.executable, str(TOOLS / "git_dirty_guard.py"), "--json"] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "test":
        subprocess.run([sys.executable, "-m", "pytest", str(BAGO_ROOT.parent / "tests")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "encoding":
        subprocess.run([sys.executable, str(TOOLS / "encoding_guard.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "census":
        subprocess.run([sys.executable, str(TOOLS / "tool_registry.py"), "--list"] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "map":
        subprocess.run([sys.executable, str(TOOLS / "context_map.py")] + rest, cwd=str(BAGO_ROOT.parent))
    elif cmd == "prompt-router":
        subprocess.run(
            [sys.executable, str(CORE / "prompt_router.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "role-spiral":
        subprocess.run(
            [sys.executable, str(TOOLS / "role_embedded.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "model-gate":
        subprocess.run(
            [sys.executable, str(TOOLS / "model_gate.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
    elif cmd == "api-only":
        print("  API-only: toggle con bago api-only on|off")
        print("  Desactiva login interactivo, usa solo API keys con freno de tokens")
    elif cmd == "token-analytics":
        _cmd_token_analytics(rest)
        return

    elif cmd == "token-brake":
        _cmd_token_brake(rest)
        return
    elif cmd == "router":
        _cmd_router(rest)
        return


    elif cmd == "spiral-prompt":
        _cmd_spiral_prompt(rest)
        return

    elif cmd == "music":
        result = subprocess.run(
            [sys.executable, str(TOOLS / "bago_music.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
        sys.exit(result.returncode)

    elif cmd in ("image_gen", "image-gen"):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "image_gen.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
        sys.exit(result.returncode)

    elif cmd == "image-studio":
        result = subprocess.run(
            [sys.executable, str(TOOLS / "image_studio.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
        sys.exit(result.returncode)

    elif cmd == "sprite-studio":
        result = subprocess.run(
            [sys.executable, str(TOOLS / "sprite_studio.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
        sys.exit(result.returncode)

    elif cmd in ("splash", "start", "inicio", "menu"):
        # Menú principal interactivo BAGO (curses TUI)
        result = subprocess.run(
            [sys.executable, str(TOOLS / "bago_menu.py")] + rest,
            cwd=str(BAGO_ROOT.parent),
        )
        sys.exit(result.returncode)
    elif cmd == "serve":
        tools_dir = str(TOOLS)
        env = dict(os.environ, PYTHONPATH=tools_dir)
        subprocess.run(
            [sys.executable, "-m", "bago.api.server"] + rest,
            cwd=str(BAGO_ROOT.parent),
            env=env,
        )
    elif cmd == "bot":
        tools_dir = str(TOOLS)
        env = dict(os.environ, PYTHONPATH=tools_dir)
        if rest and rest[0].lower() == "telegram":
            subprocess.run(
                [sys.executable, "-m", "bago.api.services.telegram_bot"],
                cwd=str(BAGO_ROOT.parent),
                env=env,
            )
        elif rest and rest[0].lower() == "utopia":
            subprocess.run(
                [sys.executable, "-m", "bago.api.services.utopia_bot"],
                cwd=str(BAGO_ROOT.parent),
                env=env,
            )
        else:
            print("  Uso: bago bot telegram | bago bot utopia")
    elif cmd in COMMANDS:
        _dispatch(cmd, clean_rest, preflight_only=preflight_only, skip_preflight=skip_preflight)
    elif cmd in ("help", "--help", "-h"):
        subprocess.run(
            [sys.executable, str(TOOLS / "bago_banner.py"), "--mini"],
            cwd=str(BAGO_ROOT.parent)
        )
        # Build grouped help output
        reg = load_registry_mod()
        if reg and hasattr(reg, "REGISTRY"):
            core_cmds       = sorted(k for k,v in reg.REGISTRY.items() if v.stability == "core")
            dangerous_cmds  = sorted(k for k,v in reg.REGISTRY.items() if v.stability == "dangerous")
            exp_cmds        = sorted(k for k,v in reg.REGISTRY.items() if v.stability == "experimental")
            legacy_cmds     = sorted(k for k,v in reg.REGISTRY.items() if v.stability == "legacy")
            print("  ⚙️  Core (contrato estable):")
            for k in core_cmds:
                print(f"    bago {k}")
            print()
            print("  ⚠️  Dangerous (requieren --yes):")
            for k in dangerous_cmds:
                print(f"    bago {k}")
            print()
            print(f"  ⚗️  Experimental ({len(exp_cmds)} comandos — fuera del contrato, aviso al ejecutar):")
            print(f"    " + " | ".join(exp_cmds[:12]) + (" | …" if len(exp_cmds) > 12 else ""))
            print(f"    Usa BAGO_LABS=1 para suprimir avisos. Ver docs/API_CONTRACT.md para la lista completa.")
            print()
            print(f"  🗄️  Legacy (deprecated, {len(legacy_cmds)} — redirigen al equivalente actual):")
            print(f"    " + " | ".join(legacy_cmds[:8]) + (" | …" if len(legacy_cmds) > 8 else ""))
        else:
            print("  Comandos disponibles:")
            print("    bago setup | extensions | versions | registry | last | history | telemetry | neural | heal-paths | npath | project | siembra | siembra ideas | wizard")
            for k in sorted(COMMANDS):
                print(f"    bago {k}")
        print()
    else:
        import difflib
        all_cmds = list(COMMANDS.keys()) + ["setup", "extensions", "versions", "registry", "last", "history", "telemetry", "help", "neural", "heal-paths", "npath", "project", "siembra", "wizard", "rubber-duck", "seed-ideas", "assign", "music", "image_gen", "image-studio", "sprite-studio"]
        suggestions = difflib.get_close_matches(cmd, all_cmds, n=1, cutoff=0.5)
        print(f"  Comando desconocido: '{cmd}'")
        if suggestions:
            print(f"  ¿Quisiste decir: {GREEN(suggestions[0])}?  →  bago {suggestions[0]}")
        else:
            print("  Usa: bago help")
        sys.exit(1)
