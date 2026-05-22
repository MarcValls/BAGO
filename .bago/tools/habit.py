#!/usr/bin/env python3
"""
bago habit — detector de habitos de trabajo desde patrones de sesiones.

Analiza los datos de sesiones y roles para identificar:
- Hábitos positivos: decisiones consistentes, artefactos documentados
- Hábitos a mejorar: sesiones sin objetivos, workflows ignorados
- Patrones: día/hora de mayor actividad, duración media de sesiones

Uso:
    bago habit              → análisis completo de hábitos
    bago habit --positive   → solo hábitos positivos
    bago habit --improve    → solo áreas de mejora
    bago habit --pattern    → solo patrones de actividad
    bago habit --json       → output JSON
    bago habit --test       → tests integrados
"""

import argparse
import json
import sys
import datetime
from pathlib import Path
from collections import defaultdict, Counter

BAGO_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = BAGO_ROOT / "state" / "sessions"


class Habit:
    def __init__(self, kind: str, score: int, title: str, detail: str, evidence: str = None):
        self.kind = kind        # positive | improve | pattern
        self.score = score      # 0-100
        self.title = title
        self.detail = detail
        self.evidence = evidence  # stat or example

    def to_dict(self):
        return {
            "kind": self.kind,
            "score": self.score,
            "title": self.title,
            "detail": self.detail,
            "evidence": self.evidence,
        }


def _load_sessions() -> list:
    out = []
    for f in sorted(SESSIONS_DIR.glob("SES-*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            pass
    return out


def detect_positive(sessions: list) -> list:
    habits = []
    if not sessions:
        return habits

    # Decision capture rate
    with_decs = sum(1 for s in sessions if len(s.get("decisions", [])) > 0)
    rate = with_decs / len(sessions)
    if rate >= 0.7:
        habits.append(Habit(
            "positive", int(rate * 100),
            "Alta captura de decisiones",
            f"{int(rate*100)}% de las sesiones incluye al menos una decisión.",
            f"{with_decs}/{len(sessions)} sesiones con decisiones"
        ))

    # Artifact documentation rate
    with_arts = sum(1 for s in sessions if len(s.get("artifacts", [])) > 0)
    art_rate = with_arts / len(sessions)
    if art_rate >= 0.6:
        habits.append(Habit(
            "positive", int(art_rate * 100),
            "Documentación de artefactos consistente",
            f"{int(art_rate*100)}% de sesiones registra los archivos producidos.",
            f"{with_arts}/{len(sessions)} sesiones con artefactos"
        ))

    # Workflow discipline
    with_wf = sum(1 for s in sessions if s.get("selected_workflow"))
    wf_rate = with_wf / len(sessions)
    if wf_rate >= 0.8:
        habits.append(Habit(
            "positive", int(wf_rate * 100),
            "Disciplina de workflow",
            f"{int(wf_rate*100)}% de sesiones tiene workflow asignado.",
            f"{with_wf}/{len(sessions)} sesiones con workflow"
        ))

    # Multi-role usage
    multi_role = sum(1 for s in sessions if len(s.get("roles_activated", [])) > 1)
    if multi_role > 5:
        habits.append(Habit(
            "positive", 70,
            "Uso de múltiples roles",
            f"{multi_role} sesiones activan más de un rol, indicando trabajo multidimensional.",
            f"{multi_role} sesiones multi-rol"
        ))

    return habits


def detect_improve(sessions: list) -> list:
    habits = []
    if not sessions:
        return habits

    # Sessions without user_goal
    no_goal = [s for s in sessions if not s.get("user_goal", "").strip()]
    if len(no_goal) > len(sessions) * 0.3:
        habits.append(Habit(
            "improve", 40,
            "Sesiones sin objetivo definido",
            f"{len(no_goal)} sesiones ({int(len(no_goal)/len(sessions)*100)}%) no tienen 'user_goal' definido.",
            "Define el objetivo al abrir cada sesión"
        ))

    # Sessions without summary
    no_summary = [s for s in sessions if not s.get("summary", "").strip()]
    if len(no_summary) > len(sessions) * 0.4:
        habits.append(Habit(
            "improve", 35,
            "Sesiones sin resumen de cierre",
            f"{len(no_summary)} sesiones sin campo 'summary' completado.",
            "Documenta qué se logró al cerrar la sesión"
        ))

    # Closed sessions without decisions
    closed_no_decs = [s for s in sessions if s.get("status") == "closed" and not s.get("decisions")]
    if len(closed_no_decs) > 5:
        habits.append(Habit(
            "improve", 45,
            "Sesiones cerradas sin decisiones",
            f"{len(closed_no_decs)} sesiones cerradas sin captura de decisiones.",
            "Captura al menos 1 decisión por sesión antes de cerrarla"
        ))

    # Workflow variety
    wf_counter = Counter(s.get("selected_workflow", "?") for s in sessions)
    if len(wf_counter) < 3 and len(sessions) > 10:
        habits.append(Habit(
            "improve", 50,
            "Poca variedad de workflows",
            f"Solo {len(wf_counter)} workflow(s) distintos en {len(sessions)} sesiones.",
            "Explora otros workflows para distintos tipos de trabajo"
        ))

    return habits


def detect_patterns(sessions: list) -> list:
    habits = []
    if not sessions:
        return habits

    # Role frequency distribution
    role_counter = Counter()
    for s in sessions:
        for r in s.get("roles_activated", []):
            role_counter[r] += 1

    if role_counter:
        top3 = role_counter.most_common(3)
        top_roles_str = ", ".join(f"{r}({n})" for r, n in top3)
        habits.append(Habit(
            "pattern", 0,
            "Roles más utilizados",
            f"Los 3 roles más frecuentes: {top_roles_str}",
            None
        ))

    # Workflow distribution
    wf_counter = Counter(s.get("selected_workflow", "?") for s in sessions if s.get("selected_workflow"))
    if wf_counter:
        top_wf = wf_counter.most_common(1)[0]
        habits.append(Habit(
            "pattern", 0,
            f"Workflow dominante: {top_wf[0]}",
            f"Usado en {top_wf[1]}/{len(sessions)} sesiones ({int(top_wf[1]/len(sessions)*100)}%).",
            None
        ))

    # Task type distribution
    task_counter = Counter(s.get("task_type", "?") for s in sessions if s.get("task_type"))
    if task_counter:
        top3_tasks = task_counter.most_common(3)
        top_tasks_str = ", ".join(f"{t}({n})" for t, n in top3_tasks)
        habits.append(Habit(
            "pattern", 0,
            "Tipos de tarea más frecuentes",
            f"Top 3: {top_tasks_str}",
            None
        ))

    # Session mode distribution
    mode_counter = Counter(s.get("bago_mode", "?") for s in sessions if s.get("bago_mode"))
    if mode_counter:
        top_mode = mode_counter.most_common(1)[0]
        habits.append(Habit(
            "pattern", 0,
            f"Modo BAGO dominante: {top_mode[0]}",
            f"Usado en {top_mode[1]}/{len(sessions)} sesiones ({int(top_mode[1]/len(sessions)*100)}%).",
            None
        ))

    return habits


def render_habits(habits: list, as_json: bool):
    if as_json:
        print(json.dumps([h.to_dict() for h in habits], indent=2, ensure_ascii=False))
        return

    ICONS = {"positive": "✅", "improve": "⚠️ ", "pattern": "📊"}
    COLORS = {"positive": "\033[32m", "improve": "\033[33m", "pattern": "\033[36m"}
    RESET = "\033[0m"

    print(f"\n  BAGO Habit Detector ({len(habits)} observaciones)\n")

    current_kind = None
    for h in habits:
        if h.kind != current_kind:
            current_kind = h.kind
            labels = {"positive": "HÁBITOS POSITIVOS", "improve": "ÁREAS DE MEJORA", "pattern": "PATRONES"}
            color = COLORS.get(h.kind, "")
            print(f"  {color}── {labels.get(h.kind, h.kind)} ──{RESET}\n")

        icon = ICONS.get(h.kind, "•")
        score_str = f" [{h.score}/100]" if h.kind != "pattern" else ""
        print(f"  {icon} {h.title}{score_str}")
        print(f"     {h.detail}")
        if h.evidence:
            print(f"     📎 {h.evidence}")
        print()


def analyze(kind_filter: str = None) -> list:
    sessions = _load_sessions()
    all_habits = []
    all_habits.extend(detect_positive(sessions))
    all_habits.extend(detect_improve(sessions))
    all_habits.extend(detect_patterns(sessions))

    if kind_filter:
        all_habits = [h for h in all_habits if h.kind == kind_filter]

    # Sort: positive (score desc), improve (score asc), pattern
    def sort_key(h):
        order = {"positive": 0, "improve": 1, "pattern": 2}
        return (order.get(h.kind, 9), -h.score if h.kind == "positive" else h.score)

    return sorted(all_habits, key=sort_key)


def run_tests():
    print("Ejecutando tests de habit.py...")
    errors = 0

    def ok(name): print(f"  OK: {name}")
    def fail(name, msg):
        nonlocal errors
        errors += 1
        print(f"  FAIL: {name} — {msg}")

    fake_sessions = [
        {"decisions": ["d1","d2"], "artifacts": ["a"], "selected_workflow": "W2",
         "roles_activated": ["r1","r2"], "user_goal": "test", "summary": "done",
         "status": "closed", "task_type": "implementation", "bago_mode": "balanced"},
    ] * 10 + [
        {"decisions": [], "artifacts": [], "selected_workflow": "W2",
         "roles_activated": ["r1"], "user_goal": "", "summary": "",
         "status": "closed", "task_type": "review", "bago_mode": "balanced"},
    ] * 5

    # Test 1: detect_positive returns list
    pos = detect_positive(fake_sessions)
    if isinstance(pos, list):
        ok("habit:detect_positive_returns_list")
    else:
        fail("habit:detect_positive_returns_list", str(type(pos)))

    # Test 2: detect_improve detects no-goal sessions
    imp = detect_improve(fake_sessions)
    no_goal = [h for h in imp if "objetivo" in h.title.lower()]
    if no_goal:
        ok("habit:detect_improve_no_goal")
    else:
        fail("habit:detect_improve_no_goal", str([h.title for h in imp]))

    # Test 3: detect_patterns returns patterns
    pat = detect_patterns(fake_sessions)
    if isinstance(pat, list) and len(pat) > 0:
        ok("habit:detect_patterns_nonempty")
    else:
        fail("habit:detect_patterns_nonempty", str(len(pat)))

    # Test 4: analyze on real data returns list
    result = analyze()
    if isinstance(result, list):
        ok("habit:analyze_real_data")
    else:
        fail("habit:analyze_real_data", str(type(result)))

    # Test 5: kind filter
    pos_only = analyze(kind_filter="positive")
    if all(h.kind == "positive" for h in pos_only):
        ok("habit:kind_filter")
    else:
        wrong = [h.kind for h in pos_only if h.kind != "positive"]
        fail("habit:kind_filter", str(wrong))

    total = 5
    passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(prog="bago habit", add_help=False)
    parser.add_argument("--positive", action="store_true")
    parser.add_argument("--improve", action="store_true")
    parser.add_argument("--pattern", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    kind = None
    if args.positive:
        kind = "positive"
    elif args.improve:
        kind = "improve"
    elif args.pattern:
        kind = "pattern"

    habits = analyze(kind_filter=kind)
    render_habits(habits, as_json=args.json)


if __name__ == "__main__":
    main()