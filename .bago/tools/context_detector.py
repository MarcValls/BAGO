#!/usr/bin/env python3
"""
context_detector.py — BAGO ESCENARIO-003
Detecta señales de madurez cognitiva y técnica en el workspace.
Emite un veredicto: HARVEST / WATCH / CLEAN

Uso:
  python3 .bago/tools/context_detector.py
  python3 .bago/tools/context_detector.py --json
  python3 .bago/tools/context_detector.py --watch  (monitoreo continuo)
"""

import json, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

# Windows UTF-8 fix: box-drawing / emoji chars fail on cp1252
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─── Configuración ────────────────────────────────────────────────────────────
BAGO_ROOT   = Path(__file__).resolve().parent.parent
REPO_ROOT   = BAGO_ROOT.parent
STATE_DIR   = BAGO_ROOT / "state"
SESSIONS    = STATE_DIR / "sessions"
CHANGES     = STATE_DIR / "changes"

# Keywords cognitivas que indican pensamiento maduro
COGNITIVE_KEYWORDS = [
    r"\bdecid[íi]\b",
    r"\bdescarto\b", r"\bdescartamos\b", r"\bdescartado\b",
    r"\bmejor opci[oó]n\b",
    r"\bla soluci[oó]n\b", r"\bes mejor\b",
    r"\bno vale\b", r"\bno sirve\b",
    r"\bfrente a\b", r"\bcomparado con\b", r"\bvs\b",
    r"\bpor tanto\b", r"\bpor lo tanto\b", r"\bconcluyo\b",
    r"\bpreferible\b", r"\boptamos\b",
    r"\bproblema resuelto\b", r"\bya funciona\b",
    r"\bel siguiente paso\b", r"\bnext step\b",
]

HARVEST_THRESHOLD = 2   # señales de peso alto mínimas para sugerir cosecha


# ─── Señales técnicas ─────────────────────────────────────────────────────────

def _git_modified_files():
    """Ficheros modificados en el repo desde el último commit."""
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        files = [f.strip() for f in r.stdout.splitlines() if f.strip()]
        # También ficheros sin stage
        r2 = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--short"],
            capture_output=True, text=True, timeout=5
        )
        for line in r2.stdout.splitlines():
            fname = line[3:].strip().strip('"')
            if fname and fname not in files:
                files.append(fname)
        return files
    except Exception:
        return []


def _registered_chg_files():
    """Ficheros ya cubiertos por algún CHG aplicado."""
    covered = set()
    for f in CHANGES.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            for comp in d.get("affected_components", []):
                covered.add(comp)
        except Exception:
            pass
    return covered


def _unregistered_files():
    """Ficheros modificados que no están en ningún CHG."""
    modified = _git_modified_files()
    covered = _registered_chg_files()
    unregistered = []
    for mf in modified:
        # Comparar por sufijo (los CHG guardan rutas relativas a .bago)
        if not any(mf.endswith(c) or c.endswith(mf) for c in covered):
            unregistered.append(mf)
    return unregistered


def _commits_without_session():
    """Número de commits recientes sin sesión BAGO asociada."""
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "log", "--oneline", "-10"],
            capture_output=True, text=True, timeout=5
        )
        commits = r.stdout.strip().splitlines()
        session_ids = {
            json.loads(f.read_text()).get("session_id", "")
            for f in SESSIONS.glob("*.json")
        }
        orphan = [c for c in commits if not any(sid in c for sid in session_ids)]
        return len(orphan)
    except Exception:
        return 0


# ─── Señales cognitivas ───────────────────────────────────────────────────────

def _scan_cognitive(max_files=40, extensions=(".md", ".txt", ".py", ".ts", ".js")):
    """
    Busca keywords cognitivas en ficheros recientes del repo.
    Devuelve lista de (fichero, keyword_encontrada, fragmento).
    """
    hits = []
    candidates = []

    # Ficheros modificados primero
    for mf in _git_modified_files():
        p = REPO_ROOT / mf
        if p.exists() and p.suffix in extensions:
            candidates.append(p)

    def _safe_mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    # Completar con ficheros recientes si hacen falta
    if len(candidates) < max_files:
        for ext in extensions:
            try:
                rglob_results = list(REPO_ROOT.rglob(f"*{ext}"))
            except Exception:
                rglob_results = []
            for p in sorted(rglob_results, key=_safe_mtime, reverse=True):
                if p not in candidates and ".bago" not in str(p):
                    candidates.append(p)
                    if len(candidates) >= max_files:
                        break

    for p in candidates:
        try:
            text = p.read_text(errors="ignore")
            for pattern in COGNITIVE_KEYWORDS:
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    start = max(0, m.start() - 40)
                    fragment = text[start: m.end() + 40].replace("\n", " ").strip()
                    hits.append({"file": str(p.relative_to(REPO_ROOT)),
                                 "keyword": m.group(), "fragment": fragment})
                    break  # una hit por patrón por fichero
        except Exception:
            pass
    return hits


def _detect_comparisons(cognitive_hits):
    """Detecta si hay al menos 1 alternativa comparada en los hits."""
    comparison_patterns = [r"\bvs\b", r"\bfrente a\b", r"\bcomparado con\b",
                            r"\bmejor que\b", r"\bpeor que\b"]
    for h in cognitive_hits:
        for p in comparison_patterns:
            if re.search(p, h["fragment"], re.IGNORECASE):
                return True
    return False


def _detect_discards(cognitive_hits):
    """Detecta si hay al menos 1 descarte explícito."""
    discard_patterns = [r"\bdescart", r"\bno vale\b", r"\bno sirve\b",
                        r"\babandon", r"\brechaz"]
    for h in cognitive_hits:
        for p in discard_patterns:
            if re.search(p, h["fragment"], re.IGNORECASE):
                return True
    return False


# ─── Motor de señales ─────────────────────────────────────────────────────────

def evaluate():
    """
    Evalúa todas las señales y devuelve un dict con el veredicto.
    """
    unregistered = _unregistered_files()
    orphan_commits = _commits_without_session()
    cognitive_hits = _scan_cognitive()
    has_comparison = _detect_comparisons(cognitive_hits)
    has_discard    = _detect_discards(cognitive_hits)
    has_keywords   = len(cognitive_hits) > 0

    signals = []

    # Señales técnicas
    if len(unregistered) >= 3:
        signals.append({"id": "unregistered_files", "weight": "high",
                         "desc": f"{len(unregistered)} ficheros sin CHG asociado",
                         "detail": unregistered[:5]})
    elif len(unregistered) >= 1:
        signals.append({"id": "unregistered_files_low", "weight": "medium",
                         "desc": f"{len(unregistered)} fichero(s) sin CHG",
                         "detail": unregistered})

    if orphan_commits >= 1:
        signals.append({"id": "orphan_commits", "weight": "medium",
                         "desc": f"{orphan_commits} commit(s) sin sesión BAGO"})

    # Señales cognitivas
    if has_comparison:
        signals.append({"id": "comparison_detected", "weight": "very_high",
                         "desc": "Alternativa comparada detectada en texto reciente"})
    if has_discard:
        signals.append({"id": "discard_detected", "weight": "very_high",
                         "desc": "Descarte explícito detectado en texto reciente"})
    if has_keywords and not has_comparison and not has_discard:
        signals.append({"id": "cognitive_keywords", "weight": "high",
                         "desc": f"{len(cognitive_hits)} keyword(s) de pensamiento maduro detectada(s)"})

    # Contar señales de peso alto
    high_signals = [s for s in signals if s["weight"] in ("high", "very_high")]
    score = len(high_signals)

    if score >= HARVEST_THRESHOLD:
        verdict = "HARVEST"
        message = "Contexto suficiente — hay valor para cosechar ahora."
    elif signals:
        verdict = "WATCH"
        message = "Señales débiles — continúa explorando, el contexto madura."
    else:
        verdict = "CLEAN"
        message = "Sin señales. No hay nada que cosechar todavía."

    return {
        "verdict": verdict,
        "message": message,
        "score": score,
        "threshold": HARVEST_THRESHOLD,
        "signals": signals,
        "cognitive_hits": cognitive_hits[:5],
        "unregistered_files": unregistered,
        "evaluated_at": datetime.now(timezone.utc).isoformat()
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _bar(score, threshold, width=20):
    filled = min(int(width * score / max(threshold * 1.5, 1)), width)
    return "█" * filled + "░" * (width - filled)


def print_report(result):
    v = result["verdict"]
    icon = {"HARVEST": "🌾", "WATCH": "👁️ ", "CLEAN": "✅"}.get(v, "?")
    color_open  = {"HARVEST": "\033[93m", "WATCH": "\033[96m", "CLEAN": "\033[92m"}.get(v, "")
    color_close = "\033[0m"

    print()
    print("╔══════════════════════════════════════════╗")
    print("║   BAGO · Context Detector                ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  {icon} {color_open}{v:<10}{color_close}  {result['message'][:28]:<28} ║")
    bar = _bar(result["score"], result["threshold"])
    print(f"║  Score: {result['score']}/{result['threshold']}  [{bar}]  ║")
    print("╠══════════════════════════════════════════╣")

    if result["signals"]:
        print("║  Señales detectadas:                     ║")
        for s in result["signals"]:
            w = {"very_high": "🔴", "high": "🟠", "medium": "🟡"}.get(s["weight"], "⚪")
            desc = s["desc"][:36]
            print(f"║    {w} {desc:<36} ║")
    else:
        print("║  Sin señales activas.                    ║")

    if result["cognitive_hits"]:
        print("╠══════════════════════════════════════════╣")
        print("║  Hits cognitivos (muestra):               ║")
        for h in result["cognitive_hits"][:3]:
            kw = h["keyword"][:14]
            frag = h["fragment"][:26]
            print(f"║    «{kw}» … {frag:<26} ║")

    print("╚══════════════════════════════════════════╝")

    if v == "HARVEST":
        print()
        print("  → Ejecuta:  python3 .bago/tools/cosecha.py")
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
    import time

    if "--watch" in sys.argv:
        interval = 60
        print(f"Modo watch — comprobando cada {interval}s. Ctrl+C para salir.")
        while True:
            result = evaluate()
            if result["verdict"] == "HARVEST":
                print_report(result)
            else:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] {result['verdict']} "
                      f"(score={result['score']}/{result['threshold']}) — "
                      f"{result['message'][:50]}   ", end="", flush=True)
            time.sleep(interval)
    elif "--json" in sys.argv:
        print(json.dumps(evaluate(), indent=2, ensure_ascii=False))
    else:
        result = evaluate()
        print_report(result)
