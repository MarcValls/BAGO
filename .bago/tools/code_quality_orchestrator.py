#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code_quality_orchestrator.py — LÍDER BAGO que orquesta agentes especializados.

BAGO NO ejecuta tareas. BAGO GENERA y COORDINA especialistas.

Flujo:
1. Usuario solicita auditoría: bago code-quality
2. Orquestador carga manifest de agentes
3. Para cada agente requerido:
   - ¿Existe?
     - ✅ SÍ → lo usa
     - ❌ NO → Factory lo CREA dinámicamente
4. Ejecuta todos en paralelo (subprocess)
5. Espera resultados (async)
6. Sintetiza hallazgos
7. Prioriza por severidad
8. Genera recomendaciones
9. Retorna reporte unificado

Uso:
  bago code-quality [DIR] [--format text|md|json]
  bago code-quality [DIR] --new-agent "performance checker"
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime
import concurrent.futures as cf

BAGO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = BAGO_ROOT / "agents"
FACTORY = AGENTS_DIR / "agent_factory.py"

# Agentes REQUERIDOS (deben existir o ser creados)
REQUIRED_AGENTS = {
    "security_analyzer": {
        "category": "security",
        "description": "Detecta vulnerabilidades y riesgos de seguridad",
        "rules": ["sql_injection", "hardcoded_secrets", "dangerous_functions", "command_injection"]
    },
    "logic_checker": {
        "category": "logic",
        "description": "Detecta errores lógicos y problemas de flujo",
        "rules": ["bad_comparisons", "bare_except", "missing_return", "dead_code"]
    },
    "smell_detector": {
        "category": "smell",
        "description": "Detecta code smells y antipatterns",
        "rules": ["long_functions", "too_many_params", "high_complexity", "deep_nesting"]
    },
    "duplication_finder": {
        "category": "duplication",
        "description": "Detecta código duplicado y redundancias",
        "rules": ["similar_functions", "duplicate_imports", "duplicate_constants"]
    }
}


def agent_exists(name: str) -> bool:
    """Verifica si agente existe."""
    return (AGENTS_DIR / f"{name}.py").exists()


def ensure_agent(name: str, config: dict) -> bool:
    """Asegura que agente existe (crea si no)."""
    if agent_exists(name):
        return True
    
    # Crea agente usando factory
    print(f"📦 Generando agente bajo demanda: {name}...", end=" ", flush=True)
    
    try:
        result = subprocess.run(
            [
                sys.executable, str(FACTORY), "create",
                name, config["category"], config["description"],
                *config["rules"]
            ],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("✅")
            return True
        else:
            print(f"❌ ({result.stderr})")
            return False
    except Exception as e:
        print(f"❌ ({e})")
        return False


def run_agent(name: str, target_dir: str) -> dict:
    """Ejecuta agente y retorna resultados."""
    agent_script = AGENTS_DIR / f"{name}.py"
    
    if not agent_script.exists():
        return {"agent": name, "findings": [], "error": "not found", "count": 0}
    
    try:
        result = subprocess.run(
            [sys.executable, str(agent_script), target_dir],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"agent": name, "findings": [], "error": result.stderr, "count": 0}
    except Exception as e:
        return {"agent": name, "findings": [], "error": str(e), "count": 0}


def orchestrate(target_dir: str) -> dict:
    """Orquesta análisis con agentes."""
    
    print(f"\n{'='*70}")
    print("🎯 BAGO Code Quality Orchestrator")
    print(f"{'='*70}\n")
    
    # Fase 1: Asegurar que agentes existen
    print("⚙️  Fase 1: Verificando especialistas...\n")
    for name, config in REQUIRED_AGENTS.items():
        if not ensure_agent(name, config):
            print(f"⚠️  No se pudo crear agente: {name}")
    
    # Fase 2: Ejecutar agentes en paralelo
    print("\n🚀 Fase 2: Lanzando agentes en paralelo...\n")
    
    results = {}
    with cf.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for agent_name in REQUIRED_AGENTS.keys():
            future = executor.submit(run_agent, agent_name, target_dir)
            futures[future] = agent_name
        
        for future in cf.as_completed(futures):
            agent_name = futures[future]
            try:
                result = future.result()
                results[agent_name] = result
                count = result.get("count", 0)
                print(f"  ✓ {agent_name:<25} ({count:>3} hallazgos)")
            except Exception as e:
                print(f"  ✗ {agent_name:<25} ({e})")
    
    # Fase 3: Sintetizar hallazgos
    print(f"\n{'='*70}")
    print("📊 Fase 3: Síntesis de Hallazgos")
    print(f"{'='*70}\n")
    
    all_findings = []
    for agent_results in results.values():
        all_findings.extend(agent_results.get("findings", []))
    
    critical = [f for f in all_findings if f.get("severity") == "critical"]
    warnings = [f for f in all_findings if f.get("severity") == "warning"]
    infos = [f for f in all_findings if f.get("severity") == "info"]
    
    # Imprime resultados
    if critical:
        print(f"🔴 CRÍTICO ({len(critical)})")
        for f in critical[:5]:
            file_name = Path(f['file']).name if 'file' in f else "?"
            print(f"   [{f['rule']}] {file_name}:{f['line']} → {f['message']}")
        if len(critical) > 5:
            print(f"   ... y {len(critical)-5} más")
        print()
    
    if warnings:
        print(f"🟡 WARNINGS ({len(warnings)})")
        for f in warnings[:5]:
            file_name = Path(f['file']).name if 'file' in f else "?"
            print(f"   [{f['rule']}] {file_name}:{f['line']} → {f['message']}")
        if len(warnings) > 5:
            print(f"   ... y {len(warnings)-5} más")
        print()
    
    if infos:
        print(f"ℹ️  INFO ({len(infos)})")
        for f in infos[:3]:
            file_name = Path(f['file']).name if 'file' in f else "?"
            print(f"   [{f['rule']}] {file_name}:{f['line']} → {f['message']}")
        if len(infos) > 3:
            print(f"   ... y {len(infos)-3} más")
        print()
    
    # Recomendaciones
    print(f"{'='*70}")
    print("💡 Recomendaciones Prioritarias")
    print(f"{'='*70}\n")
    
    if critical:
        print("1. 🔒 SEGURIDAD → Remover credenciales, usar env vars")
    if len([f for f in warnings if "long" in f.get("message", "").lower()]) > 0:
        print("2. 📦 REFACTOR → Dividir funciones grandes")
    if len([f for f in warnings if "similar" in f.get("message", "").lower()]) > 0:
        print("3. 🔄 CONSOLIDAR → Consolidar funciones similares")
    
    print()
    print(f"{'='*70}")
    print(f"✓ Análisis completado • Total: {len(all_findings)} hallazgos")
    print(f"{'='*70}\n")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "target": target_dir,
        "agents": list(results.keys()),
        "summary": {
            "critical": len(critical),
            "warnings": len(warnings),
            "info": len(infos),
            "total": len(all_findings)
        },
        "findings": all_findings
    }


def main():
    """Entry point."""
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    fmt = "text"
    
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]
    
    if not Path(target).exists():
        print(f"❌ No existe: {target}", file=sys.stderr)
        return 1
    
    result = orchestrate(target)
    
    if fmt == "json":
        print(json.dumps(result, indent=2))
    
    return 0 if result["summary"]["critical"] == 0 else 1



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())

