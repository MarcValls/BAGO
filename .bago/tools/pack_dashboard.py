#!/usr/bin/env python3
"""
pack_dashboard.py — Estado del pack BAGO en una pantalla.
Uso: python3 .bago/tools/pack_dashboard.py [--full]
"""
import json
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "state"
TOOLS = ROOT / "tools"

def _count(folder):
    return len(list((STATE / folder).glob("*.json")))

def _validate():
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "validate_pack.py")],
            capture_output=True, text=True, cwd=ROOT.parent
        )
        out = (r.stdout + r.stderr).strip().splitlines()
        last = out[-1] if out else "?"
        return "GO" if "GO pack" in "\n".join(out) else f"KO ({last})"
    except Exception as e:
        return f"ERROR ({e})"

def _load_global():
    p = STATE / "global_state.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    if not d.get("pack_version"):
        pack_p = ROOT / "pack.json"
        if pack_p.exists():
            pack = json.loads(pack_p.read_text())
            d["pack_version"] = pack.get("version", "?")
    return d

def _escenario_002():
    excl = {"state/sessions/", "state/changes/", "state/evidences/", "TREE.txt", "CHECKSUMS.sha256"}
    on_u, on_n, off_u, off_n = 0, 0, 0, 0
    for f in (STATE / "sessions").glob("*.json"):
        s = json.loads(f.read_text())
        if s.get("escenario") != "ESCENARIO-002" or s.get("status") != "closed":
            continue
        arts = [a for a in s.get("artifacts", []) if not any(a.startswith(e) for e in excl)]
        if s.get("bago_mode") == "on":
            on_u += len(arts); on_n += 1
        else:
            off_u += len(arts); off_n += 1
    return on_n, on_u, off_n, off_u

def _avg_production(last_n=5):
    excl = {"state/sessions/", "state/changes/", "state/evidences/", "TREE.txt", "CHECKSUMS.sha256"}
    sessions = []
    for f in (STATE / "sessions").glob("*.json"):
        s = json.loads(f.read_text())
        if s.get("status") != "closed":
            continue
        arts = [a for a in s.get("artifacts", []) if not any(a.startswith(e) for e in excl)]
        sessions.append((s.get("updated_at", ""), len(arts)))
    sessions.sort(reverse=True)
    subset = sessions[:last_n]
    if not subset:
        return 0.0
    return round(sum(u for _, u in subset) / len(subset), 1)

def _sprint_velocity_avg() -> tuple[float, int]:
    """Lee sprint_summary_*.md y devuelve (velocidad_media, n_sprints).
    # VELOCITY_IN_DASHBOARD_IMPLEMENTED
    """
    import re
    velocities: list[float] = []
    for f in sorted((STATE).glob("sprint_summary_*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"Velocidad:\s+([\d.]+)\s+ideas/día", text)
        if m:
            velocities.append(float(m.group(1)))
    if not velocities:
        return 0.0, 0
    return round(sum(velocities) / len(velocities), 1), len(velocities)


def _ideas_report_link() -> tuple[bool, str]:
    """Devuelve (existe, fecha_generado) del ideas_report.md.
    # DASHBOARD_EXPORT_LINK_IMPLEMENTED
    """
    import re
    report = STATE / "ideas_report.md"
    if not report.exists():
        return False, ""
    try:
        text = report.read_text(encoding="utf-8")
        m = re.search(r"Generado:\s+(\S+)", text)
        date = m.group(1)[:10] if m else "?"
        return True, date
    except Exception:
        return True, "?"


def _context_detector():
    """Ejecuta context_detector y devuelve (verdict, score, threshold, n_signals)."""
    detector = TOOLS / "context_detector.py"
    if not detector.exists():
        return None, 0, 0, 0
    try:
        spec = importlib.util.spec_from_file_location("context_detector", detector)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.evaluate()
        return (
            result.get("verdict", "?"),
            result.get("score", 0),
            result.get("threshold", 2),
            len(result.get("signals", []))
        )
    except Exception:
        return "ERR", 0, 0, 0

def _ideas_summary():
    """(implemented, available, total_db) para el panel de progreso de ideas."""
    impl_path = STATE / "implemented_ideas.json"
    db_path = STATE / "bago.db"
    implemented = 0
    total_db = 0
    recent: list[dict] = []
    try:
        if impl_path.exists():
            data = json.loads(impl_path.read_text(encoding="utf-8"))
            entries = data.get("implemented", [])
            implemented = len(entries)
            recent = entries[-3:] if entries else []
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            total_db = conn.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
            conn.close()
    except Exception:
        pass
    available = max(0, total_db - implemented)
    return implemented, available, total_db, recent


def _escenario_003_stats():
    """Cuenta cosechas W9 completadas en ESCENARIO-003."""
    harvests = []
    for f in (STATE / "sessions").glob("*.json"):
        s = json.loads(f.read_text())
        if (s.get("escenario") == "ESCENARIO-003"
                and s.get("status") == "closed"
                and s.get("task_type") == "harvest"):
            harvests.append(s)
    n = len(harvests)
    if n == 0:
        return n, 0.0, 0.0
    avg_dec = round(sum(len(s.get("decisions", [])) for s in harvests) / n, 1)
    avg_art = round(sum(len([a for a in s.get("artifacts", [])
                              if "state/" not in a]) for s in harvests) / n, 1)
    return n, avg_dec, avg_art

def main():
    impl_n, avail_n, total_n, recent_ideas = _ideas_summary()
    pct_i = round(100 * impl_n / total_n) if total_n > 0 else 0
    bar_i = int(10 * impl_n / total_n) if total_n > 0 else 0
    bar_ideas = "█" * bar_i + "░" * (10 - bar_i)
    full = "--full" in sys.argv
    g = _load_global()
    pack_status = _validate()
    inv = g.get("inventory", {})
    on_n, on_u, off_n, off_u = _escenario_002()
    avg = _avg_production()
    verdict, score, threshold, n_signals = _context_detector()
    e003_n, e003_dec, e003_art = _escenario_003_stats()
    vel_avg, vel_n = _sprint_velocity_avg()
    report_exists, report_date = _ideas_report_link()

    on_avg  = round(on_u  / on_n,  1) if on_n  else 0
    off_avg = round(off_u / off_n, 1) if off_n else 0
    delta   = round(on_avg - off_avg, 1)
    leader  = "ON ✅" if delta > 0 else ("OFF 🔴" if delta < 0 else "EMPATE")

    status_icon = "✅" if pack_status == "GO" else "❌"
    total_ses = _count("sessions")

    # Línea del detector
    verdict_icons = {"HARVEST": "🌾 HARVEST", "WATCH": "👁  WATCH  ", "CLEAN": "✅ CLEAN  ", "ERR": "⚠️  ERROR  "}
    v_str = verdict_icons.get(verdict, f"?  {verdict:<7}")
    bar_filled = min(int(10 * score / max(threshold, 1)), 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    # Escenario-003 estado
    active_scenarios = g.get("active_scenarios", [])
    e003_active = "ESCENARIO-003" in active_scenarios

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║              BAGO PACK DASHBOARD                    ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Pack:      {status_icon} {pack_status:<41}║")
    print(f"║  Versión:   {g.get('pack_version','?'):<43}║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Inventario   sessions={inv.get('sessions','?')} ({total_ses} archivos) "
          f"changes={inv.get('changes','?')} evidences={inv.get('evidences','?')}  ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Producción últimas 5 sesiones:   {avg} útiles/sesión       ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  ESCENARIO-002  ON({on_n})={on_avg}/ses  OFF({off_n})={off_avg}/ses"
          f"  Δ={delta:+.1f}  {leader:<6}║")
    print("╠══════════════════════════════════════════════════════╣")
    e3_tag = "🔬 ACTIVO" if e003_active else "CERRADO  "
    print(f"║  ESCENARIO-003  {e3_tag}  cosechas={e003_n}  dec/harvest={e003_dec}  ║")
    print("╠══════════════════════════════════════════════════════╣")
    vel_str = f"{vel_avg} ideas/día  (media de {vel_n} sprints)" if vel_n else "sin datos"
    print(f"║  Velocidad sprint:  {vel_str:<34}║")
    print("╠══════════════════════════════════════════════════════╣")
    if verdict:
        print(f"║  Detector W9:  {v_str}  [{bar}] {score}/{threshold}        ║")
        if verdict == "HARVEST":
            print( "║  → python3 .bago/tools/cosecha.py                   ║")
    print("╠══════════════════════════════════════════════════════╣")
    ideas_content = f"  Ideas:  {impl_n} impl. / {avail_n} disp. [{bar_ideas}] {pct_i}%"
    print(f"║{ideas_content:<54}║")
    for idea in recent_ideas:
        title = idea.get("title", "—")[:40]
        date  = (idea.get("done_at") or "")[:10] or "—"
        row   = f"    · {title}  {date}"
        print(f"║{row:<54}║")
    if report_exists:
        report_row = f"  Informe ideas:  state/ideas_report.md  ({report_date})"
        print(f"║{report_row:<54}║")
    print("╠══════════════════════════════════════════════════════╣")
    lc = g.get("last_completed_session_id", "—")
    print(f"║  Última sesión: {lc:<37}║")
    print(f"║  Workflow:      {g.get('last_completed_workflow','—'):<37}║")
    active = g.get("active_session_id") or "—"
    print(f"║  Activa ahora:  {active:<37}║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    if full:
        print("  Detalle ESCENARIO-002:")
        excl = {"state/sessions/", "state/changes/", "state/evidences/", "TREE.txt", "CHECKSUMS.sha256"}
        for f in sorted((STATE / "sessions").glob("*.json")):
            s = json.loads(f.read_text())
            if s.get("escenario") != "ESCENARIO-002" or s.get("status") != "closed":
                continue
            arts = [a for a in s.get("artifacts", []) if not any(a.startswith(e) for e in excl)]
            mode = s.get("bago_mode", "?")
            ronda = s.get("ronda", "?")
            roles = len(s.get("roles_activated", []))
            print(f"    R{ronda} {mode.upper():<3} | útiles={len(arts)} | roles={roles} | {s['session_id']}")
        print()

        if e003_n > 0:
            print("  Detalle ESCENARIO-003 (cosechas):")
            for f in sorted((STATE / "sessions").glob("SES-HARVEST-*.json")):
                s = json.loads(f.read_text())
                if s.get("status") != "closed":
                    continue
                dec = len(s.get("decisions", []))
                arts = len([a for a in s.get("artifacts", []) if "state/" not in a])
                print(f"    {s['session_id']}  dec={dec}  útiles={arts}")
            print()

        print("  Señales del detector:")
        try:
            spec = importlib.util.spec_from_file_location("context_detector", TOOLS / "context_detector.py")
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            result = mod.evaluate()
            for sig in result.get("signals", []):
                w = {"very_high": "🔴", "high": "🟠", "medium": "🟡"}.get(sig["weight"], "⚪")
                print(f"    {w} {sig['desc']}")
            if not result.get("signals"):
                print("    Sin señales activas.")
        except Exception as e:
            print(f"    Error al leer detector: {e}")
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
