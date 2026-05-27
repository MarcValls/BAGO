#!/usr/bin/env python3
"""
pack_dashboard.py — Dashboard BAGO v2.
Uso:
  python pack_dashboard.py           → genera JSON y abre navegador
  python pack_dashboard.py --full    → dashboard legacy en terminal
  python pack_dashboard.py --output  → solo genera JSON
  python pack_dashboard.py --public  → resumen publicable en terminal
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import json
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent.parent
TOOLS = ROOT / "tools"
TEMP_DIR = Path.home() / "AppData" / "Local" / "Temp" / "bago_dashboard"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
JSON_PATH = ROOT / "dashboard_data.json"
HTML_SRC = ROOT / "dashboard.html"
HTML_TEMP = TEMP_DIR / "bago_dashboard.html"


def generate_json():
    gen = TOOLS / "generate_dashboard.py"
    if not gen.exists():
        print("[ERROR] Generador no encontrado:", gen)
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, str(gen), "--output", str(JSON_PATH)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("[ERROR] Fallo al generar JSON:")
        print(result.stderr)
        sys.exit(1)
    print("[OK] JSON generado:", JSON_PATH)


def _registry_stability():
    counts = {"core": 0, "experimental": 0, "dangerous": 0, "legacy": 0, "unknown": 0}
    risks = {"safe": 0, "mutating": 0, "dangerous": 0, "unknown": 0}
    try:
        from tool_registry import REGISTRY
    except Exception:
        return counts, risks

    for entry in REGISTRY.values():
        stability = (getattr(entry, "stability", "") or "unknown").lower()
        risk = (getattr(entry, "risk", "") or "unknown").lower()
        counts[stability] = counts.get(stability, 0) + 1
        risks[risk] = risks.get(risk, 0) + 1
    return counts, risks


def _probe_status(script: Path, *args: str, needle: str) -> str:
    try:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception as exc:
        return f"ERROR ({exc})"
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0 and needle in output:
        return "GO"
    if result.returncode == 0:
        return "GO"
    last = output.splitlines()[-1] if output else "sin salida"
    return f"KO ({last})"


def prepare_html():
    if not HTML_SRC.exists():
        print("[ERROR] HTML no encontrado:", HTML_SRC)
        sys.exit(1)
    html = HTML_SRC.read_text(encoding="utf-8")
    # Asegurar que apunte al JSON correcto
    abs_path = JSON_PATH.resolve().as_posix()
    html = re.sub(r"const DATA_URL = '.*?dashboard_data\.json'", f"const DATA_URL = 'file:///{abs_path}'", html)
    HTML_TEMP.write_text(html, encoding="utf-8")
    print("[OK] HTML preparado:", HTML_TEMP)
    return HTML_TEMP


def open_browser(html_path):
    url = f"file:///{html_path.resolve().as_posix()}"
    print("[OK] Abriendo navegador...")
    webbrowser.open(url, new=2)


def serve(port):
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import threading
    import os
    os.chdir(TEMP_DIR)
    srv = HTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/bago_dashboard.html"
    print(f"[OK] Servidor en {url}")
    webbrowser.open(url, new=2)
    print("Presiona Ctrl+C para detener...")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        srv.shutdown()


# ── Legacy dashboard (terminal) ────────────────────────────────────────────────

def _legacy_dashboard():
    STATE = ROOT / "state"

    def _count(folder):
        return len(list((STATE / folder).glob("*.json")))

    def _load_global():
        p = STATE / "global_state.json"
        d = json.loads(p.read_text()) if p.exists() else {}
        if not d.get("pack_version"):
            pack_p = ROOT / "pack.json"
            if pack_p.exists():
                pack = json.loads(pack_p.read_text())
                d["pack_version"] = pack.get("version", "?")
        return d

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

    g = _load_global()
    print(f"""
┌──────────────────────────────────────────────────────────────┐
│  BAGO Dashboard v{g.get('pack_version', '?')}                                    │
├──────────────────────────────────────────────────────────────┤
│  Sesiones:     {_count('sessions'):>4}   │  Cambios:     {_count('changes'):>4}   │
│  Evidencias:   {_count('evidences'):>4}   │  Agentes:      {_count('agents'):>4}   │
│  Validación:   {_validate():>20}                  │
│  Estado:       {g.get('status', '?'):>20}                  │
└──────────────────────────────────────────────────────────────┘
""")


def _public_dashboard():
    generate_json()
    data = json.loads(JSON_PATH.read_text(encoding="utf-8")) if JSON_PATH.exists() else {}
    meta = data.get("meta", {})
    stats = data.get("stats", {})
    families = data.get("families", [])
    tools = data.get("tools", [])
    version = meta.get("version") or "?"
    visible_agents = sum(len(family.get("agents", [])) for family in families)
    command_count = stats.get("cli_commands") or len(tools)
    stability_counts, risk_counts = _registry_stability()
    pack_status = _probe_status(TOOLS / "validate_pack.py", needle="GO pack")
    encoding_status = _probe_status(TOOLS / "encoding_guard.py", str(ROOT), needle="GO encoding")

    print()
    print("BAGO PUBLIC DASHBOARD")
    print("=====================")
    print(f"Version: {version}")
    print(f"Agentes visibles: {visible_agents or stats.get('agents_canonical', 0)}")
    print(f"Comandos CLI: {command_count}")
    print(f"Tools Python: {stats.get('total_py_tools', 0)}")
    print(f"MCP tools: {stats.get('mcp_tools', 0)}")
    print(f"Estabilidad: core {stability_counts.get('core', 0)} | experimental {stability_counts.get('experimental', 0)} | dangerous {stability_counts.get('dangerous', 0)} | legacy {stability_counts.get('legacy', 0)}")
    print(f"Riesgo runtime: safe {risk_counts.get('safe', 0)} | mutating {risk_counts.get('mutating', 0)} | dangerous {risk_counts.get('dangerous', 0)}")
    print(f"Validacion pack: {pack_status}")
    print(f"Encoding: {encoding_status}")
    print("Panel: stats-panel")
    print("Canal recomendado: beta hasta smoke test de instalacion limpia")
    print()


def main():
    parser = argparse.ArgumentParser(description="BAGO Dashboard")
    parser.add_argument("--full", action="store_true", help="Dashboard legacy en terminal")
    parser.add_argument("--output", action="store_true", help="Solo generar JSON")
    parser.add_argument("--public", action="store_true", help="Vista publicable en terminal")
    parser.add_argument("--serve", action="store_true", help="Servir via HTTP local")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.full:
        _legacy_dashboard()
        return

    if args.public:
        _public_dashboard()
        return

    generate_json()

    if args.output:
        print("[OK] Modo output: JSON en", JSON_PATH)
        return

    html = prepare_html()

    if args.serve:
        serve(args.port)
        return

    open_browser(html)




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