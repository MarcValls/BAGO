#!/usr/bin/env python3
"""harmonic_scenarios.py -- Multi-scenario harmonic orchestration simulation."""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any

SCENARIOS = {
    'framework_dev': {
        'desc': 'Framework development (current)',
        'agents': {
            'CENTINELA':  {'hz': 1.00,  'period': 1, 'phase': 0, 'symbol': 'C', 'priority': 1, 'duty': 0.9},
            'VALIDADOR':  {'hz': 0.50,  'period': 2, 'phase': 0, 'symbol': 'V', 'priority': 2, 'duty': 0.8},
            'ANALISTA':   {'hz': 0.33,  'period': 3, 'phase': 0, 'symbol': 'A', 'priority': 3, 'duty': 0.7},
            'ORGANIZADOR':{'hz': 0.25,  'period': 4, 'phase': 1, 'symbol': 'O', 'priority': 4, 'duty': 0.6},
            'ARQUITECTO': {'hz': 0.125, 'period': 8, 'phase': 3, 'symbol': 'R', 'priority': 5, 'duty': 0.5},
        }
    },
    'clean_install': {
        'desc': 'Clean install bootstrap',
        'agents': {
            'CENTINELA':  {'hz': 1.00,  'period': 1, 'phase': 0, 'symbol': 'C', 'priority': 1, 'duty': 1.0},
            'VALIDADOR':  {'hz': 0.50,  'period': 2, 'phase': 1, 'symbol': 'V', 'priority': 2, 'duty': 0.9},
            'ARQUITECTO': {'hz': 0.25,  'period': 4, 'phase': 0, 'symbol': 'R', 'priority': 3, 'duty': 0.8},
            'ANALISTA':   {'hz': 0.20,  'period': 5, 'phase': 2, 'symbol': 'A', 'priority': 4, 'duty': 0.6},
            'ORGANIZADOR':{'hz': 0.125, 'period': 8, 'phase': 4, 'symbol': 'O', 'priority': 5, 'duty': 0.4},
        }
    },
    'production_monitor': {
        'desc': 'Production stable monitoring',
        'agents': {
            'CENTINELA':  {'hz': 1.00,  'period': 1, 'phase': 0, 'symbol': 'C', 'priority': 1, 'duty': 0.95},
            'VALIDADOR':  {'hz': 0.33,  'period': 3, 'phase': 1, 'symbol': 'V', 'priority': 2, 'duty': 0.7},
            'ANALISTA':   {'hz': 0.20,  'period': 5, 'phase': 2, 'symbol': 'A', 'priority': 3, 'duty': 0.5},
            'ORGANIZADOR':{'hz': 0.125, 'period': 8, 'phase': 4, 'symbol': 'O', 'priority': 4, 'duty': 0.3},
            'ARQUITECTO': {'hz': 0.10,  'period': 10, 'phase': 5, 'symbol': 'R', 'priority': 5, 'duty': 0.2},
        }
    },
    'legacy_migration': {
        'desc': 'Legacy cleanup and migration',
        'agents': {
            'CENTINELA':  {'hz': 1.00,  'period': 1, 'phase': 0, 'symbol': 'C', 'priority': 1, 'duty': 0.9},
            'ANALISTA':   {'hz': 0.50,  'period': 2, 'phase': 0, 'symbol': 'A', 'priority': 2, 'duty': 0.8},
            'ORGANIZADOR':{'hz': 0.33,  'period': 3, 'phase': 1, 'symbol': 'O', 'priority': 3, 'duty': 0.7},
            'VALIDADOR':  {'hz': 0.25,  'period': 4, 'phase': 2, 'symbol': 'V', 'priority': 4, 'duty': 0.6},
            'ARQUITECTO': {'hz': 0.125, 'period': 8, 'phase': 3, 'symbol': 'R', 'priority': 5, 'duty': 0.4},
        }
    },
    'crisis_recovery': { # v2: guardia permanente + equipo a /3
        'desc': 'All-hands crisis recovery',
        'agents': {
            'CENTINELA':  {'hz': 1.00,  'period': 1, 'phase': 0, 'symbol': 'C', 'priority': 1, 'duty': 1.0},
            'VALIDADOR':  {'hz': 0.33,  'period': 3, 'phase': 1, 'symbol': 'V', 'priority': 2, 'duty': 1.0},
            'ANALISTA':   {'hz': 0.16,  'period': 6, 'phase': 0, 'symbol': 'A', 'priority': 3, 'duty': 0.9},
            'ORGANIZADOR':{'hz': 0.16,  'period': 6, 'phase': 1, 'symbol': 'O', 'priority': 4, 'duty': 0.9},
            'ARQUITECTO': {'hz': 0.11,  'period': 9, 'phase': 2, 'symbol': 'R', 'priority': 5, 'duty': 0.8},
        }
    },
    'rd_spiral': {
        'desc': 'R&D spiral exploration',
        'agents': {
            'ARQUITECTO': {'hz': 1.00,  'period': 1, 'phase': 0, 'symbol': 'R', 'priority': 1, 'duty': 1.0},
            'ANALISTA':   {'hz': 0.50,  'period': 2, 'phase': 1, 'symbol': 'A', 'priority': 2, 'duty': 0.8},
            'ORGANIZADOR':{'hz': 0.33,  'period': 3, 'phase': 2, 'symbol': 'O', 'priority': 3, 'duty': 0.6},
            'VALIDADOR':  {'hz': 0.25,  'period': 4, 'phase': 3, 'symbol': 'V', 'priority': 4, 'duty': 0.4},
            'CENTINELA':  {'hz': 0.20,  'period': 5, 'phase': 4, 'symbol': 'C', 'priority': 5, 'duty': 0.2},
        }
    },
}

CYCLES = 24

@dataclass
class Report:
    scenario: str
    desc: str
    cycles: int
    coverage_pct: float
    avg_load: float
    max_load: int
    total_collisions: int
    efficiency_score: float
    timeline: str
    dominant_pattern: str
    prompt_router_log: List[str] = field(default_factory=list)
    agent_counts: Dict[str, int] = field(default_factory=dict)


def simulate_scenario(name, cfg, cycles=CYCLES):
    agents = cfg["agents"]
    reports = []
    router_log = []
    for c in range(cycles):
        active = [a for a in agents if (c + agents[a]["phase"]) % agents[a]["period"] == 0]
        collisions = len(active) - 1 if len(active) > 1 else 0
        load = len(active)
        reports.append((c, active, collisions, load))

        phase = "BUILD" if c < 4 else "STABILIZE" if c < 12 else "REFINE"
        signal = load
        freq_band = "2.4g" if signal <= 2 else "5g" if signal <= 3 else "6g"
        depth = {"2.4g": "shallow", "5g": "medium", "6g": "deep"}[freq_band]
        router_log.append(f"c{c:02d} phase={phase:<10} signal={signal} band={freq_band} depth={depth}")

    total = len(reports)
    coverage = sum(1 for _, active, _, _ in reports if active) / total
    avg_load = sum(load for _, _, _, load in reports) / total
    max_load = max(load for _, _, _, load in reports)
    total_collisions = sum(coll for _, _, coll, _ in reports)

    lines = []
    for c, active, _, load in reports[:12]:
        bar = "".join(agents[a]["symbol"] if a in active else "." for a in agents)
        names = " ".join(active) if active else "-"
        lines.append(f"  {c:2} | {bar} | {load} | {names}")

    dominant = max(agents.keys(), key=lambda a: sum(1 for _, active, _, _ in reports if a in active))
    agent_counts = {a: sum(1 for _, active, _, _ in reports if a in active) for a in agents}

    score = coverage * 100 - total_collisions * 5 - (max_load - 1) * 10

    return Report(
        scenario=name,
        desc=cfg["desc"],
        cycles=cycles,
        coverage_pct=round(coverage * 100, 1),
        avg_load=round(avg_load, 2),
        max_load=max_load,
        total_collisions=total_collisions,
        efficiency_score=round(score, 1),
        timeline="\n".join(lines),
        dominant_pattern=dominant,
        prompt_router_log=router_log[:12],
        agent_counts=agent_counts,
    )


def main():
    print("=== BAGO Harmonic Orchestration (6 Scenarios) ===")
    print(f"Cycles: {CYCLES}")
    print()
    all_reports = []
    for name, cfg in SCENARIOS.items():
        r = simulate_scenario(name, cfg)
        all_reports.append(r)
        print(f"--- {name} ---")
        print(f"  Desc: {r.desc}")
        print(f"  Coverage: {r.coverage_pct}%  AvgLoad: {r.avg_load}  MaxLoad: {r.max_load}")
        print(f"  Collisions: {r.total_collisions}  Efficiency: {r.efficiency_score}")
        print(f"  Dominant: {r.dominant_pattern}")
        print("  Timeline (first 12 cycles):")
        print(r.timeline)
        print("  Prompt Router (first 12):")
        for line in r.prompt_router_log:
            print(f"    {line}")
        print()

    print("=== Comparison ===")
    hdr = f"{'Scenario':<20} {'Cov%':>6} {'AvgLoad':>7} {'MaxLoad':>7} {'Collisions':>10} {'Efficiency':>10} {'Dominant':>12}"
    print(hdr)
    for r in all_reports:
        print(f"{r.scenario:<20} {r.coverage_pct:>6.1f} {r.avg_load:>7.2f} {r.max_load:>7} {r.total_collisions:>10} {r.efficiency_score:>10.1f} {r.dominant_pattern:>12}")
    print()

    summary = [
        {
            "scenario": r.scenario,
            "desc": r.desc,
            "coverage_pct": r.coverage_pct,
            "avg_load": r.avg_load,
            "max_load": r.max_load,
            "total_collisions": r.total_collisions,
            "efficiency_score": r.efficiency_score,
            "dominant_pattern": r.dominant_pattern,
            "agent_counts": r.agent_counts,
        }
        for r in all_reports
    ]
    print("=== JSON Summary ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
