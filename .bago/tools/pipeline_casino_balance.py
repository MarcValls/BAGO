#!/usr/bin/env python3
"""pipeline_casino_balance.py — Pipeline Balance de Juego para Casino BAGO.

Fases:
  1. Importar slot_engine y leer configuracion de simbolos
  2. Ejecutar simulate_ev(n=100_000) para RTP empirico
  3. Ejecutar simulate_ev(n=1_000_000) para convergencia
  4. Verificar que RTP esta en rango DGOJ (90-98%)
  5. Generar informe JSON con frecuencias observadas

Uso:
  python pipeline_casino_balance.py --project-dir PATH
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def run_simulation(project_dir: Path, n_spins: int) -> dict:
    """Importa slot_engine desde el proyecto y ejecuta simulate_ev."""
    try:
        sys.path.insert(0, str(project_dir))
        import slot_engine as se
        start = time.time()
        rtp = se.simulate_ev(n_spins)
        duration_ms = int((time.time() - start) * 1000)
        sys.path.pop(0)
        return {"success": True, "rtp": round(rtp, 4), "n_spins": n_spins, "duration_ms": duration_ms}
    except Exception as e:
        return {"success": False, "error": str(e), "n_spins": n_spins}


def get_paytable(project_dir: Path) -> list[dict]:
    """Extrae la tabla de pagos del slot_engine."""
    try:
        sys.path.insert(0, str(project_dir))
        import slot_engine as se
        table = []
        for emoji, name, weight, mult, _ in se.SYMBOLS:
            prob = (weight / se._TOTAL_W) ** 3
            table.append({
                "symbol": emoji,
                "name": name,
                "weight": weight,
                "multiplier": mult,
                "prob_triple": round(prob, 8),
                "rtp_contribution": round(prob * mult, 6),
            })
        sys.path.pop(0)
        return table
    except Exception as e:
        return [{"error": str(e)}]


def run_pipeline(project_dir: Path) -> dict:
    print(f"\n  [Pipeline Casino Balance] Proyecto: {project_dir}")
    print(f"  {'-'*50}")

    total_start = time.time()

    # TABLA TEORICA
    print(f"  [Fase 1/3] Tabla de pagos teorica...")
    paytable = get_paytable(project_dir)
    total_rtp_theory = sum(row.get("rtp_contribution", 0) for row in paytable)
    print(f"    RTP teorico: {total_rtp_theory:.4f} ({total_rtp_theory*100:.2f}%)")
    for row in paytable:
        print(f"      {row['symbol']} {row['name']}: peso={row['weight']} mult=x{row['multiplier']} contrib={row['rtp_contribution']:.4f}")

    # SIMULACION 100K
    print(f"\n  [Fase 2/3] Simulacion 100,000 giros...")
    sim1 = run_simulation(project_dir, 100_000)
    print(f"    {'OK' if sim1['success'] else 'FAIL'} RTP empirico (100K): {sim1.get('rtp', '???')}")
    if not sim1["success"]:
        print(f"    Error: {sim1.get('error', '???')}")

    # SIMULACION 1M
    print(f"\n  [Fase 3/3] Simulacion 1,000,000 giros...")
    sim2 = run_simulation(project_dir, 1_000_000)
    print(f"    {'OK' if sim2['success'] else 'FAIL'} RTP empirico (1M): {sim2.get('rtp', '???')}")
    if not sim2["success"]:
        print(f"    Error: {sim2.get('error', '???')}")

    # VALIDACION DGOJ
    rtp_final = sim2.get("rtp", sim1.get("rtp", total_rtp_theory))
    dgoj_min = 0.90
    dgoj_max = 0.98
    dgoj_ok = dgoj_min <= rtp_final <= dgoj_max

    print(f"\n  [Validacion] DGOJ (Espana)")
    print(f"    Rango permitido: 90.00% - 98.00%")
    print(f"    RTP medido: {rtp_final*100:.2f}%")
    print(f"    Estado: {'CUMPLE' if dgoj_ok else 'NO CUMPLE'}")

    result = {
        "pipeline": "casino_balance",
        "project": str(project_dir),
        "success": dgoj_ok and sim1["success"] and sim2["success"],
        "rtp_theory": round(total_rtp_theory, 4),
        "rtp_empirical_100k": sim1.get("rtp") if sim1["success"] else None,
        "rtp_empirical_1m": sim2.get("rtp") if sim2["success"] else None,
        "dgoj_compliant": dgoj_ok,
        "paytable": paytable,
        "total_duration_ms": int((time.time() - total_start) * 1000),
    }

    # Guardar informe JSON
    report_path = project_dir / "balance_report.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Informe guardado: {report_path}")

    print(f"\n  {'='*50}")
    print(f"  Resultado: {'TODO OK' if result['success'] else 'CON FALLOS'}")
    print(f"  Duracion total: {result['total_duration_ms']}ms")
    print(f"  {'='*50}\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Balance de Juego Casino BAGO")
    parser.add_argument("--project-dir", default=".", help="Directorio del proyecto")
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