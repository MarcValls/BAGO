#!/usr/bin/env python3
"""bago_boot.py — Boot Examiner de BAGO.

Arranca BAGO de forma examinada: detecta el directorio/repo actual,
lee el índice resumido del proyecto, escanea el campo de modelos,
fabrica frases-operador y forma el enfoque inicial de la sesión.

Flujo:
  detectar repo/proyecto
    ↓
  leer project_index (si existe)
    ↓
  escanear campo (bago_field)
    ↓
  fabricar frases-operador
    ↓
  guardar boot_state.json + boot_phrases.jsonl
    ↓
  mostrar enfoque inicial

Uso:
  bago boot              → arranca boot examiner (resumen)
  bago boot examine      → boot completo con frases-operador
  bago boot status       → estado del último boot
  bago boot phrases      → mostrar frases-operador generadas
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

BAGO_ROOT   = Path(__file__).resolve().parents[2]
BOOT_DIR    = BAGO_ROOT / ".bago" / "state" / "boot"
BOOT_STATE  = BOOT_DIR / "boot_state.json"
BOOT_PHRASES = BOOT_DIR / "boot_phrases.jsonl"
FIELD_FILE  = BAGO_ROOT / ".bago" / "state" / "field" / "model_field_matrix.json"
SAFEGUARDS_FILE = BAGO_ROOT / ".bago" / "state" / "reactor" / "safeguards.json"

# ── helpers ──────────────────────────────────────────────────────────────────

def _detect_project(cwd: Path) -> dict:
    """Detecta repo git, nombre de proyecto, y archivos clave."""
    info = {
        "cwd": str(cwd),
        "is_git": False,
        "repo_name": None,
        "branch": None,
        "has_readme": False,
        "has_pyproject": False,
        "has_packagejson": False,
        "top_files": [],
        "project_type": "unknown",
    }
    # Git
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            info["is_git"] = True
            info["repo_root"] = r.stdout.strip()
            info["repo_name"] = Path(r.stdout.strip()).name
        r2 = subprocess.run(
            ["git", "-C", str(cwd), "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        if r2.returncode == 0:
            info["branch"] = r2.stdout.strip()
    except Exception:
        pass

    # Archivos clave
    for fname in ["README.md", "README.txt", "readme.md"]:
        if (cwd / fname).exists():
            info["has_readme"] = True
            break
    info["has_pyproject"] = (cwd / "pyproject.toml").exists()
    info["has_packagejson"] = (cwd / "package.json").exists()

    # Tipo de proyecto
    if info["has_pyproject"]:
        info["project_type"] = "python"
    elif info["has_packagejson"]:
        info["project_type"] = "node"
    elif (cwd / "Cargo.toml").exists():
        info["project_type"] = "rust"
    elif (cwd / "go.mod").exists():
        info["project_type"] = "go"

    # Top level files (no ocultos)
    try:
        files = [f.name for f in cwd.iterdir() if not f.name.startswith(".")][:12]
        info["top_files"] = sorted(files)
    except Exception:
        pass

    return info

def _read_readme_summary(cwd: Path, max_lines: int = 20) -> str:
    """Lee primeras líneas del README."""
    for fname in ["README.md", "README.txt", "readme.md"]:
        p = cwd / fname
        if p.exists():
            try:
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                return "\n".join(lines[:max_lines])
            except Exception:
                pass
    return ""

def _load_field() -> dict:
    try:
        return json.loads(FIELD_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

def _load_safeguards() -> dict:
    try:
        return json.loads(SAFEGUARDS_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

def _field_summary(field: dict) -> str:
    """Resumen compacto del campo para incluir en el contexto de arranque."""
    nodes = field.get("nodes", {})
    available = [n for n, d in nodes.items() if d.get("available")]
    poles = field.get("poles", {})
    local = poles.get("local_pole", {}).get("primary", "?")
    lines = [
        f"Nodos disponibles: {', '.join(available) or 'ninguno'}",
        f"Polo local: {local}",
        f"Polo código: {poles.get('coding_pole', {}).get('primary', '?')}",
    ]
    return "; ".join(lines)

# ── frases-operador ───────────────────────────────────────────────────────────

def _fabricate_phrases(project: dict, field: dict, safeguards: dict) -> list[dict]:
    """Genera frases-operador de arranque según el estado del sistema."""
    phrases = []
    now = datetime.datetime.now().isoformat()

    def phrase(text, anchor, force, operation):
        return {"phrase": text, "anchor": anchor, "force": force,
                "operation": operation, "generated_at": now, "generated_by": "boot_examiner"}

    # Proyecto
    repo = project.get("repo_name") or Path(project.get("cwd", ".")).name
    ptype = project.get("project_type", "unknown")
    branch = project.get("branch", "")
    phrases.append(phrase(
        f"Proyecto activo: {repo} ({ptype}){', rama: ' + branch if branch else ''}.",
        "project_context", 1.0, "anclar"
    ))

    # Git
    if project.get("is_git"):
        phrases.append(phrase(
            "Repositorio git detectado. Respetar rama activa antes de cualquier cambio.",
            "git_state", 0.9, "bloquear"
        ))

    # Campo de modelos
    nodes = field.get("nodes", {})
    available = [n for n, d in nodes.items() if d.get("available")]
    if available:
        phrases.append(phrase(
            f"Modelos disponibles: {', '.join(available)}. Usar local primero cuando sea posible.",
            "field_state", 0.85, "enfocar"
        ))
    else:
        phrases.append(phrase(
            "Sin modelos disponibles detectados. Verificar providers antes de ejecutar tareas.",
            "field_state", 1.0, "alertar"
        ))

    # bago-local
    bago_local = nodes.get("bago-local", {})
    if bago_local.get("available"):
        phrases.append(phrase(
            "bago-local disponible. Usarlo para boot phrases, resúmenes y reactor OBSERVE.",
            "bago_local_node", 0.8, "crear"
        ))
    else:
        phrases.append(phrase(
            "bago-local no instalado. Instalar con: bago field pull bago-local.",
            "bago_local_node", 0.6, "sugerir"
        ))

    # Safeguards
    genes = safeguards.get("genes", {})
    for gene, state in genes.items():
        if state.get("state") == "OFF":
            phrases.append(phrase(
                f"ATENCIÓN: safeguard '{gene}' está OFF. Operar con máxima precaución.",
                f"safeguard_{gene}", 1.0, "alertar"
            ))
        elif state.get("state") == "BROKEN":
            phrases.append(phrase(
                f"CRÍTICO: safeguard '{gene}' en estado BROKEN. Registrar y revisar.",
                f"safeguard_{gene}", 1.0, "bloquear"
            ))

    # Reactor
    reactor = safeguards.get("reactor", {})
    reactor_state = reactor.get("state", "OFF")
    if reactor_state in ("ACTIVE", "ARMED"):
        phrases.append(phrase(
            f"Reactor en estado {reactor_state}. Confirmar antes de ejecutar autonomía.",
            "reactor_state", 0.95, "alertar"
        ))
    else:
        phrases.append(phrase(
            "El reactor está OFF; no ejecutar autonomía infinita sin activación explícita.",
            "reactor_state", 1.0, "bloquear"
        ))

    return phrases

# ── boot examine ──────────────────────────────────────────────────────────────

def cmd_examine(verbose: bool = True) -> dict:
    """Ejecuta el boot examiner completo."""
    cwd = Path.cwd()
    print("\n  ◈ BAGO BOOT EXAMINER\n")

    # 1. Detectar proyecto
    print("  [1/4] Detectando proyecto...")
    project = _detect_project(cwd)
    repo = project.get("repo_name") or cwd.name
    print(f"        → {repo} ({project['project_type']}) | git: {'sí' if project['is_git'] else 'no'}")
    readme_summary = _read_readme_summary(cwd)

    # 2. Escanear campo
    print("  [2/4] Escaneando campo de modelos...")
    try:
        sys.path.insert(0, str(BAGO_ROOT / ".bago" / "tools"))
        from bago_field import cmd_scan
        cmd_scan(verbose=False)
    except Exception as e:
        print(f"        → advertencia: {e}")
    field = _load_field()
    available_count = sum(1 for d in field.get("nodes", {}).values() if d.get("available"))
    print(f"        → {available_count} nodos disponibles")

    # 3. Leer safeguards
    print("  [3/4] Verificando safeguards...")
    safeguards = _load_safeguards()
    genes = safeguards.get("genes", {})
    broken = [g for g, s in genes.items() if s.get("state") in ("OFF", "BROKEN")]
    if broken:
        print(f"        → ⚠  safeguards en estado no seguro: {', '.join(broken)}")
    else:
        print(f"        → {len(genes)} safeguards activos" if genes else "        → safeguards no configurados (usa: bago safeguard status)")

    # 4. Fabricar frases-operador
    print("  [4/4] Fabricando frases-operador...")
    phrases = _fabricate_phrases(project, field, safeguards)
    print(f"        → {len(phrases)} frases generadas")

    # Guardar estado
    BOOT_DIR.mkdir(parents=True, exist_ok=True)
    boot_state = {
        "timestamp": datetime.datetime.now().isoformat(),
        "project": project,
        "readme_summary": readme_summary[:500] if readme_summary else "",
        "field_summary": _field_summary(field),
        "safeguards_summary": {g: s.get("state") for g, s in genes.items()},
        "reactor_state": safeguards.get("reactor", {}).get("state", "OFF"),
        "phrases_count": len(phrases),
    }
    BOOT_STATE.write_text(json.dumps(boot_state, indent=2, ensure_ascii=False), encoding="utf-8")

    # Guardar frases
    with BOOT_PHRASES.open("w", encoding="utf-8") as f:
        for p in phrases:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # Mostrar enfoque
    if verbose:
        _print_focus(boot_state, phrases)

    return boot_state

def _print_focus(state: dict, phrases: list[dict]):
    proj = state.get("project", {})
    print(f"\n  ┌─ ENFOQUE INICIAL ──────────────────────────────────────────")
    print(f"  │  Proyecto : {proj.get('repo_name', '?')} ({proj.get('project_type', '?')})")
    if proj.get("branch"):
        print(f"  │  Rama     : {proj['branch']}")
    print(f"  │  Campo    : {state.get('field_summary', '?')}")
    print(f"  │  Reactor  : {state.get('reactor_state', 'OFF')}")
    sfg = state.get("safeguards_summary", {})
    if sfg:
        sfg_str = " | ".join(f"{k}:{v}" for k, v in sfg.items())
        print(f"  │  Safeguards: {sfg_str}")
    print(f"  │")
    print(f"  │  Frases-operador activas:")
    for p in phrases[:6]:
        force_bar = "█" * int(p["force"] * 5) + "░" * (5 - int(p["force"] * 5))
        print(f"  │    [{force_bar}] [{p['operation']:8}] {p['phrase'][:65]}")
    if len(phrases) > 6:
        print(f"  │    ... y {len(phrases) - 6} más (bago boot phrases)")
    print(f"  └────────────────────────────────────────────────────────────\n")

# ── status / phrases ──────────────────────────────────────────────────────────

def cmd_status():
    if not BOOT_STATE.exists():
        print("  Sin boot ejecutado. Usa: bago boot examine")
        return
    state = json.loads(BOOT_STATE.read_text(encoding="utf-8"))
    print(f"\n  Último boot: {state.get('timestamp', '?')}")
    proj = state.get("project", {})
    print(f"  Proyecto: {proj.get('repo_name', '?')} ({proj.get('project_type', '?')})")
    print(f"  Campo: {state.get('field_summary', '?')}")
    print(f"  Reactor: {state.get('reactor_state', 'OFF')}")
    print(f"  Frases: {state.get('phrases_count', 0)}")
    sfg = state.get("safeguards_summary", {})
    if sfg:
        print(f"  Safeguards: {' | '.join(f'{k}:{v}' for k, v in sfg.items())}")
    print()

def cmd_phrases():
    if not BOOT_PHRASES.exists():
        print("  Sin frases generadas. Usa: bago boot examine")
        return
    print(f"\n  ◈ FRASES-OPERADOR (último boot)\n")
    with BOOT_PHRASES.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            p = json.loads(line)
            force = p.get("force", 0)
            bar = "█" * int(force * 5) + "░" * (5 - int(force * 5))
            op = p.get("operation", "?")
            anchor = p.get("anchor", "?")
            phrase = p.get("phrase", "")
            print(f"  {i:2}. [{bar}] [{op:8}] [{anchor}]")
            print(f"       {phrase}")
    print()

# ── main ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    args = (argv or sys.argv[1:])
    sub = args[0] if args else "examine"

    if sub in ("examine", "scan", "full"):
        cmd_examine()
    elif sub == "status":
        cmd_status()
    elif sub == "phrases":
        cmd_phrases()
    elif sub in ("-h", "--help", "help"):
        print(__doc__)
    else:
        # Sin args: resumen rápido
        cmd_examine()

if __name__ == "__main__":
    main()
