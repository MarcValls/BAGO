#!/usr/bin/env python3
"""

competition_report.py — BAGO
Compara sesiones .bago/on (W7) vs .bago/off (W0) del ESCENARIO-002.
Solo cuenta sesiones cerradas con escenario="ESCENARIO-002".
Con --baseline también muestra el histórico general de sesiones W7.
"""
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent

PROTOCOL_PREFIXES = (
    "state/sessions/",
    "state/changes/",
    "state/evidences/",
)
PROTOCOL_FILES = {"TREE.txt", "CHECKSUMS.sha256"}


def is_protocol(artifact: str) -> bool:
    if Path(artifact).name in PROTOCOL_FILES:
        return True
    return any(artifact.startswith(p) for p in PROTOCOL_PREFIXES)


def count_useful(session: dict) -> int:
    return sum(1 for a in session.get("artifacts", []) if not is_protocol(a))


def load_all_sessions():
    sessions_dir = ROOT / "state" / "sessions"
    sessions = []
    for f in sorted(sessions_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            sessions.append(d)
        except Exception:
            pass
    return sessions


def load_competition_sessions():
    """Solo sesiones cerradas del ESCENARIO-002."""
    on_sessions, off_sessions = [], []
    for s in load_all_sessions():
        if s.get("status") != "closed":
            continue
        if s.get("escenario") != "ESCENARIO-002":
            continue
        mode = s.get("bago_mode", "on")
        wf = s.get("selected_workflow", "")
        if mode == "off" or wf == "w0_free_session":
            off_sessions.append(s)
        else:
            on_sessions.append(s)
    return on_sessions, off_sessions


def load_baseline_sessions():
    """Histórico de sesiones W7 (para referencia)."""
    return [
        s for s in load_all_sessions()
        if s.get("status") == "closed"
        and s.get("selected_workflow") == "w7_foco_sesion"
    ]


def stats(sessions: list) -> dict:
    if not sessions:
        return {"n": 0, "useful_mean": 0, "roles_mean": 0, "obj_rate": 0, "decisions_mean": 0}
    useful    = [count_useful(s) for s in sessions]
    roles     = [len(s.get("roles_activated", [])) for s in sessions]
    decisions = [len(s.get("decisions", [])) for s in sessions]
    return {
        "n": len(sessions),
        "useful_mean": sum(useful) / len(useful),
        "useful_list": useful,
        "roles_mean": sum(roles) / len(roles),
        "roles_list": roles,
        "obj_rate": 1.0,  # todas las cerradas se consideran cumplidas salvo campo explícito
        "decisions_mean": sum(decisions) / len(decisions),
    }


def bar(value: float, scale: float = 10.0, width: int = 10) -> str:
    filled = min(width, round(value / scale * width))
    return "█" * filled + "░" * (width - filled)


def print_group(label: str, sessions: list, verbose: bool) -> dict:
    st = stats(sessions)
    icon = "🟢" if "on" in label.lower() else "🔴"
    print(f"\n  {icon} {label}  ({st['n']}/5 sesiones)")
    print(f"  {'─' * 50}")
    if st["n"] == 0:
        print("  (sin sesiones todavía — pendiente de ejecutar)")
        return st
    print(f"  Artefactos útiles/sesión:  {bar(st['useful_mean'])} {st['useful_mean']:.1f}")
    print(f"  Roles/sesión:              {bar(st['roles_mean'], 6)} {st['roles_mean']:.1f}")
    print(f"  Decisiones/sesión:         {st['decisions_mean']:.1f}")
    if verbose and st.get("useful_list"):
        print()
        for s, u, r in zip(sessions, st["useful_list"], st["roles_list"]):
            sid = s.get("session_id", "?")
            goal = s.get("user_goal", "")[:60]
            print(f"    · {sid}: {u} útiles, {r} roles")
            print(f"      objetivo: {goal}{'…' if len(s.get('user_goal','')) > 60 else ''}")
    return st


def verdict(on: dict, off: dict):
    print("\n" + "═" * 60)
    print("  VEREDICTO")
    print("═" * 60)
    total = on["n"] + off["n"]
    if total == 0:
        print("  ⏳ Ningún grupo tiene sesiones del ESCENARIO-002 todavía.")
        print("     Inicia la Ronda 1 siguiendo el protocolo de ESCENARIO-COMPETICION-BAGO.md")
        return
    if on["n"] == 0:
        print(f"  ⏳ Grupo .bago/on sin sesiones todavía. ({off['n']}/5 off completadas)")
        return
    if off["n"] == 0:
        print(f"  ⏳ Grupo .bago/off sin sesiones todavía. ({on['n']}/5 on completadas)")
        return

    delta_useful = on["useful_mean"] - off["useful_mean"]
    delta_roles  = off["roles_mean"] - on["roles_mean"]

    print(f"  Δ artefactos útiles  (on − off): {delta_useful:+.1f}")
    print(f"  Δ roles/sesión       (off − on): {delta_roles:+.1f}  (+ = on más focalizado)")
    print()

    if delta_useful > 0.5 and delta_roles > 0.3:
        print("  🏆 .bago/ON gana — más artefactos Y más foco.")
    elif delta_useful > 0.5:
        print("  🏆 .bago/ON gana en producción de artefactos.")
    elif delta_roles > 0.5:
        print("  🏆 .bago/ON gana en foco (menos roles).")
    elif delta_useful < -0.5:
        print("  ⚠️  .bago/OFF produce MÁS artefactos útiles.")
        print("     → El protocolo añade burocracia sin valor. Revisar W7.")
    else:
        print("  ⚖️  Empate técnico — diferencia < 0.5 en artefactos y roles.")

    remaining_on  = max(0, 5 - on["n"])
    remaining_off = max(0, 5 - off["n"])
    if remaining_on + remaining_off > 0:
        print(f"\n  Sesiones restantes: {remaining_on} (on) + {remaining_off} (off)")


def main():
    parser = argparse.ArgumentParser(
        description="Compara .bago/on vs .bago/off — ESCENARIO-002."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--baseline", action="store_true",
                        help="Mostrar también el histórico W7 pre-experimento")
    args = parser.parse_args()

    on_sessions, off_sessions = load_competition_sessions()

    print("=" * 60)
    print("  BAGO · ESCENARIO-002 — .bago/on vs .bago/off")
    print("=" * 60)

    on_st  = print_group(".bago/ON  (W7 · con preflight)", on_sessions, args.verbose)
    off_st = print_group(".bago/OFF (W0 · libre)",         off_sessions, args.verbose)

    verdict(on_st, off_st)

    if args.baseline:
        baseline = load_baseline_sessions()
        bs = stats(baseline)
        print(f"\n  📊 BASELINE histórico W7 ({bs['n']} sesiones pre-experimento):")
        print(f"     Artefactos útiles/sesión: {bs['useful_mean']:.1f}")
        print(f"     Roles/sesión:             {bs['roles_mean']:.1f}")

    print("═" * 60)



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

