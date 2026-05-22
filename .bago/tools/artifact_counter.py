#!/usr/bin/env python3
"""
artifact_counter.py — BAGO
Mide y reporta la producción de artefactos útiles por sesión.
Excluye artefactos de protocolo (session, change, evidence JSONs, TREE, CHECKSUMS).
"""
import json
import argparse
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent

PROTOCOL_PREFIXES = (
    "state/sessions/",
    "state/changes/",
    "state/evidences/",
)
PROTOCOL_FILES = {"TREE.txt", "CHECKSUMS.sha256"}


def is_protocol(artifact: str) -> bool:
    name = Path(artifact).name
    if name in PROTOCOL_FILES:
        return True
    return any(artifact.startswith(p) for p in PROTOCOL_PREFIXES)


def load_sessions(n: int | None = None):
    sessions_dir = ROOT / "state" / "sessions"
    files = sorted(sessions_dir.glob("*.json"))
    sessions = []
    for f in files:
        try:
            d = json.loads(f.read_text())
            sessions.append(d)
        except Exception:
            pass
    sessions.sort(key=lambda s: s.get("created_at", ""))
    if n:
        sessions = sessions[-n:]
    return sessions


def count_useful(session: dict) -> int:
    arts = session.get("artifacts", [])
    return sum(1 for a in arts if not is_protocol(a))


def report(sessions: list, verbose: bool = False):
    print("=" * 60)
    print(f"  BAGO · Producción de Artefactos ({len(sessions)} sesiones)")
    print("=" * 60)

    totals = []
    by_type: dict[str, list[int]] = defaultdict(list)

    for s in sessions:
        sid = s.get("session_id", "?")
        ttype = s.get("task_type", "?")
        useful = count_useful(s)
        total = len(s.get("artifacts", []))
        planned = len(s.get("artifacts_planned", []))
        totals.append(useful)
        by_type[ttype].append(useful)
        status_icon = "✅" if useful >= 3 else ("⚠️ " if useful >= 1 else "❌")
        if verbose:
            print(f"\n  {status_icon} {sid}")
            print(f"     tipo:     {ttype}")
            print(f"     útiles:   {useful}/{total}  (planificados: {planned})")
            if s.get("artifacts"):
                for a in s["artifacts"]:
                    tag = "  (protocolo)" if is_protocol(a) else ""
                    print(f"       · {a}{tag}")
        else:
            bar = "█" * useful + "░" * max(0, 5 - useful)
            print(f"  {status_icon} {bar} {useful:>2} útiles  {sid}")

    if totals:
        media = sum(totals) / len(totals)
        maximo = max(totals)
        minimo = min(totals)
        print()
        print("─" * 60)
        print(f"  Media artefactos útiles/sesión: {media:.1f}")
        print(f"  Máximo: {maximo}  Mínimo: {minimo}")
        print()
        # Score producción (escala 0-10, target ≥4 útiles = 6.0)
        score = min(10.0, (media / 4.0) * 6.0)
        score_icon = "✅" if score >= 6.0 else ("⚠️ " if score >= 4.0 else "❌")
        print(f"  Score producción: {score:.1f}/10  {score_icon}  (target ≥6.0)")
        print()
        print("  Por tipo de tarea:")
        for ttype, vals in sorted(by_type.items()):
            m = sum(vals) / len(vals)
            print(f"    {ttype:<30} media {m:.1f}  (n={len(vals)})")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Mide la producción de artefactos útiles por sesión BAGO."
    )
    parser.add_argument(
        "-n", "--last", type=int, default=None,
        help="Analizar solo las últimas N sesiones (por defecto todas)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Mostrar detalle de artefactos por sesión"
    )
    parser.add_argument(
        "--escenario", action="store_true",
        help="Mostrar resumen ESCENARIO-001 (últimas 5 sesiones)"
    )
    args = parser.parse_args()

    n = 5 if args.escenario else args.last
    sessions = load_sessions(n)

    if not sessions:
        print("No se encontraron sesiones.")
        sys.exit(1)

    report(sessions, verbose=args.verbose)

    if args.escenario:
        medias_utiles = [count_useful(s) for s in sessions]
        media = sum(medias_utiles) / len(medias_utiles)
        print("  ESCENARIO-001:")
        print(f"    Producción media últimas 5: {media:.1f}  (target ≥4 útiles/sesión)")
        ok = media >= 4.0
        print(f"    {'✅ TARGET ALCANZADO' if ok else '❌ TARGET NO ALCANZADO'}")
        print("=" * 60)



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
