#!/usr/bin/env python3
"""bago_field.py — Escáner del campo magnético BAGO.

Detecta proveedores/modelos disponibles, genera la matriz de campo
con scores de coste/privacidad/uso recomendado, y muestra el estado
del polo local (bago-local).

Uso:
  bago field              → muestra matriz actual
  bago field scan         → re-escanea disponibilidad de todos los nodos
  bago field pull bago-local → descarga modelo bago-local si no existe
  bago field calibrate <model> → test rápido de capacidad del modelo
  bago field status       → resumen compacto del campo
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import subprocess
import sys
from pathlib import Path

from bago.ollama_runtime import default_ollama_base_url

BAGO_ROOT  = Path(__file__).resolve().parents[2]
FIELD_FILE = BAGO_ROOT / ".bago" / "state" / "field" / "model_field_matrix.json"
PROVIDERS_FILE = BAGO_ROOT / ".bago" / "state" / "model_providers.json"

BAGO_LOCAL_WIRE = "marcvallssanvictor/BAGO"
BAGO_LOCAL_ALIAS = "bago-local"

# ── helpers ──────────────────────────────────────────────────────────────────

def _load_field() -> dict:
    try:
        return json.loads(FIELD_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

def _save_field(data: dict):
    FIELD_FILE.parent.mkdir(parents=True, exist_ok=True)
    FIELD_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _ollama_list() -> list[str]:
    """Devuelve lista de modelos Ollama instalados (wire names)."""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return []
        lines = r.stdout.strip().split("\n")[1:]
        return [l.split()[0] for l in lines if l.strip()]
    except Exception:
        return []

def _gh_token_present() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))

def _codex_authed() -> bool:
    codex_auth = Path.home() / ".codex" / "auth.json"
    if not codex_auth.exists():
        return False
    try:
        d = json.loads(codex_auth.read_text())
        return bool((d.get("tokens") or {}).get("access_token") or os.environ.get("OPENAI_API_KEY"))
    except Exception:
        return False

def _bar(score: float, width: int = 8) -> str:
    filled = int(round(score * width))
    return "█" * filled + "░" * (width - filled)

# ── scan ─────────────────────────────────────────────────────────────────────

def cmd_scan(verbose: bool = True) -> dict:
    """Escanea disponibilidad real de todos los nodos del campo."""
    import datetime
    field = _load_field()
    nodes = field.get("nodes", {})
    ollama_models = _ollama_list()
    ollama_wires = [m.split(":")[0] if ":" not in m else m for m in ollama_models]

    results = {}

    for node_name, node in nodes.items():
        provider = node.get("provider", "")
        wire = node.get("wire_name", node_name)
        available = False
        note = ""

        if provider in ("ollama-local", "ollama-cloud"):
            # Comprobar si el wire_name (sin tag) está en la lista
            wire_base = wire.split(":")[0]
            match = any(
                m == wire or m.startswith(wire_base) or m == wire_base
                for m in ollama_models
            )
            if match:
                available = True
                note = "instalado"
            else:
                available = False
                note = f"no instalado — ollama pull {wire}"
        elif provider == "copilot":
            available = _gh_token_present()
            note = "token OK" if available else "sin GITHUB_TOKEN"
        elif provider in ("codex", "openai"):
            available = _codex_authed()
            note = "autenticado" if available else "sin credenciales"
        else:
            available = False
            note = "provider desconocido"

        node["available"] = available
        node["_note"] = note
        results[node_name] = available

    field["nodes"] = nodes
    field["_meta"]["last_scan"] = datetime.datetime.now().isoformat()
    field["_meta"]["scan_by"] = "bago field scan"
    _save_field(field)

    if verbose:
        _print_field(field)

    return results

# ── print ─────────────────────────────────────────────────────────────────────

def _print_field(field: dict):
    nodes = field.get("nodes", {})
    meta = field.get("_meta", {})
    print("\n  ◈ CAMPO BAGO — MODEL FIELD MATRIX")
    print(f"  Último scan: {meta.get('last_scan', 'nunca')}\n")
    print(f"  {'Nodo':<18} {'Prv':<14} {'Disp':<6} {'Local':<8} {'Priv':<8} {'Code':<8} {'Razon':<8}  Nota")
    print("  " + "─" * 90)
    for name, node in nodes.items():
        avail = "✓" if node.get("available") else "✗"
        local = _bar(node.get("locality", 0))
        priv  = _bar(node.get("privacy_score", 0))
        code  = _bar(node.get("code_score", 0))
        reas  = _bar(node.get("reasoning_score", 0))
        note  = node.get("_note", "")
        tag = " ← BAGO LOCAL" if name == BAGO_LOCAL_ALIAS else ""
        print(f"  {name:<18} {node.get('provider',''):<14} {avail:<6} {local:<8} {priv:<8} {code:<8} {reas:<8}  {note}{tag}")
    print()
    # Polo local
    poles = field.get("poles", {})
    lp = poles.get("local_pole", {})
    print(f"  Polo local     → {lp.get('primary', '?')} (fallback: {lp.get('fallback', '?')})")
    cp = poles.get("coding_pole", {})
    print(f"  Polo código    → {cp.get('primary', '?')}")
    rp = poles.get("reasoning_pole", {})
    print(f"  Polo razon.    → {rp.get('primary', '?')}")
    print()

# ── pull ──────────────────────────────────────────────────────────────────────

def cmd_pull(model_alias: str):
    """Descarga un modelo Ollama por alias."""
    field = _load_field()
    nodes = field.get("nodes", {})
    node = nodes.get(model_alias)
    if not node:
        print(f"  ✗ Nodo '{model_alias}' no encontrado en la matriz.")
        sys.exit(1)
    wire = node.get("wire_name", model_alias)
    print(f"  Descargando: ollama pull {wire}")
    result = subprocess.run(["ollama", "pull", wire])
    if result.returncode == 0:
        print(f"  ✓ {model_alias} ({wire}) descargado.")
        cmd_scan(verbose=False)
    else:
        print(f"  ✗ Error al descargar {wire}.")

# ── calibrate ─────────────────────────────────────────────────────────────────

def cmd_calibrate(model_alias: str):
    """Test rápido de capacidad del modelo."""
    field = _load_field()
    node = field.get("nodes", {}).get(model_alias)
    if not node:
        print(f"  ✗ Nodo '{model_alias}' no encontrado.")
        sys.exit(1)
    if not node.get("available"):
        print(f"  ✗ '{model_alias}' no disponible. Prueba: bago field pull {model_alias}")
        sys.exit(1)

    wire = node.get("wire_name", model_alias)
    print(f"\n  ◈ Calibrando: {model_alias} ({wire})\n")

    tests = [
        ("json_discipline",   "Responde SOLO con JSON válido: {\"ok\": true}"),
        ("project_grounding", "Dime el nombre del archivo README.md de cualquier proyecto. Si no sabes, responde: no_se"),
        ("summary_quality",   "Resume en máximo 2 frases: BAGO es un framework de IA local y cloud con routing inteligente."),
        ("bago_style",        "¿Qué es un safeguard en el contexto de un reactor de IA autónoma? Respuesta corta."),
    ]

    scores = {}
    try:
        import litellm
        for test_id, prompt in tests:
            try:
                r = litellm.completion(
                    model=f"ollama/{wire}",
                    messages=[{"role": "user", "content": prompt}],
                api_base=default_ollama_base_url(),
                    max_tokens=120,
                    timeout=30,
                )
                text = r.choices[0].message.content.strip()
                # Score heurístico simple
                if test_id == "json_discipline":
                    try:
                        json.loads(text)
                        score = 1.0
                    except Exception:
                        score = 0.2 if "ok" in text else 0.0
                elif test_id == "project_grounding":
                    score = 1.0 if "no_se" in text.lower() or "no sé" in text.lower() else 0.4
                else:
                    score = min(1.0, len(text.split()) / 40)

                scores[test_id] = round(score, 2)
                status = "✓" if score >= 0.6 else "~" if score >= 0.3 else "✗"
                print(f"  {status} {test_id:<22} → {score:.2f}  [{text[:60].replace(chr(10),' ')}...]")
            except Exception as e:
                scores[test_id] = 0.0
                print(f"  ✗ {test_id:<22} → ERROR: {str(e)[:60]}")
    except ImportError:
        print("  ✗ litellm no instalado. pip3 install litellm")
        return

    # Guardar calibración
    import datetime
    node["calibration"] = {
        "timestamp": datetime.datetime.now().isoformat(),
        **scores,
        "recommended_use": [
            k for k, v in scores.items() if v >= 0.6
        ]
    }
    field["nodes"][model_alias] = node
    _save_field(field)
    print(f"\n  Calibración guardada en {FIELD_FILE.name}")

# ── status ────────────────────────────────────────────────────────────────────

def cmd_status():
    field = _load_field()
    if not field.get("_meta", {}).get("last_scan"):
        print("  Campo no escaneado. Ejecuta: bago field scan")
        return
    nodes = field.get("nodes", {})
    available = [n for n, d in nodes.items() if d.get("available")]
    missing = [n for n, d in nodes.items() if not d.get("available")]
    print(f"\n  Campo BAGO: {len(available)}/{len(nodes)} nodos activos")
    for n in available:
        print(f"    ✓ {n}")
    for n in missing:
        note = nodes[n].get("_note", "")
        print(f"    ✗ {n}  [{note}]")
    bago_local = nodes.get(BAGO_LOCAL_ALIAS, {})
    if bago_local.get("available"):
        print(f"\n  ◈ bago-local ACTIVO — polo local del campo")
    else:
        print(f"\n  ⚠  bago-local NO instalado. Instalar con: bago field pull bago-local")
    print()

# ── main ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    import sys
    args = (argv or sys.argv[1:])
    sub = args[0] if args else "status"

    if sub in ("scan",):
        cmd_scan()
    elif sub in ("status", ""):
        if not _load_field().get("_meta", {}).get("last_scan"):
            cmd_scan()
        else:
            cmd_status()
    elif sub == "pull":
        model = args[1] if len(args) > 1 else BAGO_LOCAL_ALIAS
        cmd_pull(model)
    elif sub == "calibrate":
        model = args[1] if len(args) > 1 else BAGO_LOCAL_ALIAS
        cmd_calibrate(model)
    elif sub in ("-h", "--help", "help"):
        print(__doc__)
    else:
        print(f"  Subcomando desconocido: {sub}")
        print("  Uso: bago field [scan|status|pull <model>|calibrate <model>]")
        sys.exit(1)



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
    main()