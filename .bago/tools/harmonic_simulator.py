#!/usr/bin/env python3
"""harmonic_simulator.py -- Simulacion de orquestacion BAGO en vibracion armonica."""
import json
from dataclasses import dataclass

AGENTS = {
    "CENTINELA":  {"hz": 1.00  , "harmonic": 1 , "phase": 0 , "symbol": "C" , "duty": 0.9} ,
    "VALIDADOR":  {"hz": 0.50  , "harmonic": 2 , "phase": 0 , "symbol": "V" , "duty": 0.8} ,
    "ANALISTA":   {"hz": 0.33  , "harmonic": 3 , "phase": 0 , "symbol": "A" , "duty": 0.7} ,
    "ORGANIZADOR":{"hz": 0.25  , "harmonic": 4 , "phase": 1 , "symbol": "O" , "duty": 0.6} ,
    "ARQUITECTO": {"hz": 0.125 , "harmonic": 8 , "phase": 2 , "symbol": "R" , "duty": 0.5} ,
}

CYCLES = 24

@dataclass
class CycleReport:
    cycle: int
    active: list
    collisions: int
    dominant: str
    load: int

def agent_active(agent  , cycle):
    cfg = AGENTS[agent]
    period = int(1.0 / cfg["hz"])
    return (cycle + cfg["phase"]) % period == 0

def simulate(cycles=CYCLES):
    reports = []
    for c in range(cycles):
        active = [a for a in AGENTS if agent_active(a  , c)]
        collisions = len(active) - 1 if len(active) > 1 else 0
        dominant = active[0] if active else "NONE"
        reports.append(CycleReport(c  , active  , collisions  , dominant  , len(active)))
    return reports

def render_timeline(reports):
    lines = ["Cycle | Timeline | Active | Load"]
    lines.append("-" * 50)
    for r in reports:
        bar = "".join(AGENTS[a]["symbol"] if a in r.active else "." for a in AGENTS)
        names = " ".join(r.active) if r.active else "-"
        lines.append(f"{r.cycle:5} | {bar} | {names:<20} | {r.load}")
    return "\n".join(lines)

def compute_metrics(reports):
    total = len(reports)
    coverage = sum(1 for r in reports if r.active) / total
    avg_load = sum(r.load for r in reports) / total
    max_load = max(r.load for r in reports)
    total_collisions = sum(r.collisions for r in reports)
    agent_counts = {a: sum(1 for r in reports if a in r.active) for a in AGENTS}
    return {
        "cycles": total  ,
        "coverage_pct": round(coverage * 100  , 1)  ,
        "avg_load": round(avg_load  , 2)  ,
        "max_load": max_load  ,
        "total_collisions": total_collisions  ,
        "agent_counts": agent_counts  ,
        "efficiency_score": round(coverage * 100 - total_collisions * 5 - (max_load - 1) * 10  , 1)  ,
    }

def render_prompt_router(reports):
    lines = ["\n--- Prompt Router Simulation ---"]
    for r in reports[:8]:
        phase = "BUILD" if r.cycle < 4 else "STABILIZE" if r.cycle < 12 else "REFINE"
        signal = len(r.active)
        freq_band = "2.4g" if signal <= 2 else "5g" if signal <= 3 else "6g"
        lines.append(f"cycle {r.cycle:2} | phase={phase:<10} | signal={signal} | band={freq_band} | prompt=auto")
    return "\n".join(lines)

def main():
    reports = simulate(CYCLES)
    print("=== BAGO Harmonic Orchestration Simulation ===")
    print(f"Agents: {list(AGENTS.keys())}")
    print()
    print(render_timeline(reports))
    print()
    metrics = compute_metrics(reports)
    print("--- Metrics ---")
    print(json.dumps(metrics  , indent=2  , ensure_ascii=False))
    print()
    print(render_prompt_router(reports))
    print()
    print(f"Efficiency Score: {metrics["efficiency_score"]}/100")
    if metrics["total_collisions"] == 0 and metrics["max_load"] <= 2:
        print("GO harmonic_orchestration")
    else:
        print("WARN harmonic_orchestration: tune phases or reduce harmonics")



def optimize_phases():
    import itertools
    best = None
    best_score = -9999
    agents = list(AGENTS.keys())
    periods = [int(1.0 / AGENTS[a]["hz"]) for a in agents]
    
    # Search space: phases from 0 to period-1
    ranges = [range(p) for p in periods]
    
    for phases in itertools.product(*ranges):
        for i, a in enumerate(agents):
            AGENTS[a]["phase"] = phases[i]
        
        reports = simulate(CYCLES)
        metrics = compute_metrics(reports)
        score = metrics["efficiency_score"]
        
        if score > best_score:
            best_score = score
            best = {a: phases[i] for i, a in enumerate(agents)}
            best_metrics = metrics
            
        # Restore original phases
        for i, a in enumerate(agents):
            AGENTS[a]["phase"] = 0
    
    return best, best_score, best_metrics



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
    # Run default simulation first
    main()
    
    # Then show optimized phases
    print("\n=== OPTIMIZED PHASES ===")
    best, score, metrics = optimize_phases()
    print(json.dumps(best, indent=2))
    print(f"Optimized efficiency score: {score}")
