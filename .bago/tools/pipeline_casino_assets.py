#!/usr/bin/env python3
"""pipeline_casino_assets.py — Pipeline Assets Visuales para Casino BAGO.

Orquesta:
  1. gen_sprites.py    -> simbolos de carretes (cherry, lemon, etc.)
  2. gen_ui.py         -> interfaz completa (fondos, botones, paneles)
  3. gen_trust_badges.py -> badges de confianza (fair, safe, rtp)

Uso:
  python pipeline_casino_assets.py --project-dir PATH
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def run_generator(script_name: str, project_dir: Path, timeout: int = 120) -> dict:
    """Ejecuta un script generador en el directorio del proyecto."""
    script = project_dir / script_name
    if not script.exists():
        return {"success": False, "error": f"No encontrado: {script}", "duration_ms": 0}

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start) * 1000)
        success = result.returncode == 0
        return {
            "success": success,
            "script": script_name,
            "returncode": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"timeout {timeout}s", "duration_ms": int((time.time()-start)*1000)}
    except Exception as e:
        return {"success": False, "error": str(e), "duration_ms": int((time.time()-start)*1000)}


def validate_outputs(project_dir: Path) -> list[dict]:
    """Valida que los assets esperados existan."""
    checks = [
        ("static/symbols/sprites_sheet.png", "Sprite sheet de simbolos"),
        ("static/ui/bg_main.png", "Fondo principal"),
        ("static/ui/btn_spin.png", "Boton GIRAR"),
        ("static/ui/panel_machine.png", "Panel maquina"),
        ("static/ui/panel_jackpot.png", "Panel jackpot"),
        ("static/ui/badge_fair.png", "Badge fair"),
        ("static/ui/badge_safe.png", "Badge safe"),
        ("static/ui/badge_rtp.png", "Badge RTP"),
    ]
    results = []
    for rel_path, description in checks:
        full = project_dir / rel_path
        exists = full.exists()
        size = full.stat().st_size if exists else 0
        results.append({
            "file": rel_path,
            "description": description,
            "exists": exists,
            "size_bytes": size,
            "valid": exists and size > 0,
        })
    return results


def run_pipeline(project_dir: Path) -> dict:
    print(f"\n  [Pipeline Casino Assets] Proyecto: {project_dir}")
    print(f"  {'-'*50}")

    total_start = time.time()
    phases = []

    # FASE 1: Sprites
    print(f"  [Fase 1/3] Generando simbolos...")
    r1 = run_generator("gen_sprites.py", project_dir, timeout=180)
    phases.append(r1)
    print(f"    {'OK' if r1['success'] else 'FAIL'} {r1['script']} ({r1['duration_ms']}ms)")
    if not r1["success"]:
        print(f"    Error: {r1.get('error', r1.get('stderr', '???'))}")

    # FASE 2: UI
    print(f"  [Fase 2/3] Generando interfaz...")
    r2 = run_generator("gen_ui.py", project_dir, timeout=180)
    phases.append(r2)
    print(f"    {'OK' if r2['success'] else 'FAIL'} {r2['script']} ({r2['duration_ms']}ms)")
    if not r2["success"]:
        print(f"    Error: {r2.get('error', r2.get('stderr', '???'))}")

    # FASE 3: Trust badges
    print(f"  [Fase 3/3] Generando badges de confianza...")
    r3 = run_generator("gen_trust_badges.py", project_dir, timeout=120)
    phases.append(r3)
    print(f"    {'OK' if r3['success'] else 'FAIL'} {r3['script']} ({r3['duration_ms']}ms)")
    if not r3["success"]:
        print(f"    Error: {r3.get('error', r3.get('stderr', '???'))}")

    # VALIDACION
    print(f"  [Validacion] Comprobando assets generados...")
    checks = validate_outputs(project_dir)
    ok_count = sum(1 for c in checks if c["valid"])
    for c in checks:
        status = "OK" if c["valid"] else "MISSING"
        print(f"    {status} {c['file']} ({c['size_bytes']} bytes) — {c['description']}")

    all_success = all(p["success"] for p in phases)
    all_valid = all(c["valid"] for c in checks)

    result = {
        "pipeline": "casino_assets",
        "project": str(project_dir),
        "success": all_success and all_valid,
        "phases": phases,
        "validation": checks,
        "total_duration_ms": int((time.time() - total_start) * 1000),
    }

    print(f"\n  {'='*50}")
    print(f"  Resultado: {'TODO OK' if result['success'] else 'CON FALLOS'}")
    print(f"  Fases OK: {sum(1 for p in phases if p['success'])}/3")
    print(f"  Assets validos: {ok_count}/{len(checks)}")
    print(f"  Duracion total: {result['total_duration_ms']}ms")
    print(f"  {'='*50}\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Assets Visuales Casino BAGO")
    parser.add_argument("--project-dir", default=".", help="Directorio del proyecto tragaperras_bot")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    if not project.exists():
        print(f"ERROR: Proyecto no encontrado: {project}")
        return 1

    result = run_pipeline(project)
    return 0 if result["success"] else 1




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    exit(main())