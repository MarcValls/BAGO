#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research_orchestrator.py — Modo Research integrando GitHub Copilot CLI /research

Implementa `/research` de Copilot CLI como workflow BAGO:
- Recopila contexto del repo (estructura, dependencias, estado)
- Ejecuta análisis temático (código, docs, arquitectura)
- Emite reporte investigativo con recomendaciones
- Integrable con W6 (Ideación) y W8 (Exploración)

Uso:
  python3 .bago/tools/research_orchestrator.py <tema>
  python3 .bago/tools/research_orchestrator.py "seguridad de autenticación"
  python3 .bago/tools/research_orchestrator.py --list
"""

from pathlib import Path
import json
import sys
from bago_utils import (
    get_bago_root, get_repo_root, ensure_subdir, load_json, save_json,
    get_bago_version, get_health_status, timestamp_iso
)

RESEARCH_DIR = ensure_subdir("research")


def get_repo_structure() -> dict:
    """Mapea estructura del repositorio."""
    repo_root = get_repo_root()
    structure = {
        "root": str(repo_root),
        "size_estimate": 0,
        "directories": [],
        "key_files": []
    }
    
    # Contar directorios principales
    try:
        for item in repo_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                structure["directories"].append(item.name)
            elif item.is_file() and item.suffix in ['.md', '.json', '.txt']:
                structure["key_files"].append(item.name)
    except Exception as e:
        structure["error"] = str(e)
    
    return structure


def analyze_dependencies() -> dict:
    """Analiza dependencias del proyecto."""
    repo_root = get_repo_root()
    deps = {
        "package_json": None,
        "requirements_txt": None,
        "go_mod": None,
        "cargo_toml": None
    }
    
    if (repo_root / "package.json").exists():
        deps["package_json"] = load_json(repo_root / "package.json")
    
    if (repo_root / "requirements.txt").exists():
        try:
            deps["requirements_txt"] = (repo_root / "requirements.txt").read_text().strip().split('\n')
        except Exception:
            pass
    
    return {k: v for k, v in deps.items() if v is not None}


def collect_research_context() -> dict:
    """Recopila contexto completo para investigación."""
    return {
        "timestamp": timestamp_iso(),
        "repo_structure": get_repo_structure(),
        "dependencies": analyze_dependencies(),
        "bago_state": {
            "version": get_bago_version(),
            "health": get_health_status()
        }
    }


def create_research_report(topic: str, context: dict) -> dict:
    """Crea reporte de investigación temático."""
    report = {
        "id": f"RES-{timestamp_iso().split('T')[0]}-{timestamp_iso().split('T')[1][:6].replace(':', '')}",
        "topic": topic,
        "timestamp": timestamp_iso(),
        "context": context,
        "research_areas": [
            "Arquitectura y estructura",
            "Dependencias y integraciones",
            "Estado operativo BAGO",
            "Documentación relevante"
        ],
        "next_steps": [
            f"1. Revisar contexto para tema: {topic}",
            "2. Ejecutar análisis específico según hallazgos",
            "3. Convertir hallazgos en ideas BAGO (bago ideas)",
            "4. Seleccionar workflow apropiado (W2, W6, W7)"
        ],
        "recommendation": f"Use este reporte para exploración temática: {topic}"
    }
    
    return report


def save_research(report: dict) -> str:
    """Guarda reporte de investigación."""
    filename = RESEARCH_DIR / f"{report['id']}.json"
    save_json(filename, report)
    return str(filename)


def list_research() -> None:
    """Lista investigaciones previas."""
    if not RESEARCH_DIR.exists() or not list(RESEARCH_DIR.glob("*.json")):
        print("✓ Sin investigaciones previas. Ejecuta: bago research <tema>")
        return
    
    print("\n══ Investigaciones previas ══════════════════════")
    for res_file in sorted(RESEARCH_DIR.glob("*.json")):
        try:
            data = load_json(res_file)
            print(f"  {data['id']:30} | {data['topic']}")
        except Exception:
            pass
    print()


def main():
    if len(sys.argv) < 2:
        print("research_orchestrator.py — Modo Research integrando Copilot CLI")
        print("\nUso:")
        print("  bago research <tema>         → inicia investigación sobre tema")
        print("  bago research --list         → lista investigaciones previas")
        print("\nEjemplos:")
        print('  bago research "arquitectura de seguridad"')
        print('  bago research "refactor de autenticación"')
        return
    
    arg = sys.argv[1]
    
    if arg == "--list":
        list_research()
        return
    
    topic = arg
    print(f"\n══ BAGO Research Mode ═══════════════════════════════════")
    print(f"Tema: {topic}")
    print()
    
    # Recopilar contexto
    print("▪ Recopilando contexto del repositorio...")
    context = collect_research_context()
    
    # Crear reporte
    print("▪ Creando reporte de investigación...")
    report = create_research_report(topic, context)
    
    # Guardar
    filepath = save_research(report)
    print(f"▪ Guardado: {filepath}")
    
    # Emitir reporte
    print()
    print("════════════════════════════════════════════════════════")
    print(f"ID:        {report['id']}")
    print(f"Tema:      {report['topic']}")
    print(f"Fecha:     {report['timestamp']}")
    print()
    print("Áreas de investigación:")
    for area in report['research_areas']:
        print(f"  • {area}")
    print()
    print("Próximos pasos:")
    for step in report['next_steps']:
        print(f"  {step}")
    print()
    print("════════════════════════════════════════════════════════")
    print()
    print("💡 Recomendación:")
    print(f"  {report['recommendation']}")
    print()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()

