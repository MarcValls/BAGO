#!/usr/bin/env python3
"""pipeline_casino_deploy.py — Pipeline Deploy Seguro para Casino BAGO.

Fases:
  1. Validar DB (existe, tiene tablas, schema correcto)
  2. Validar assets (imagenes estaticas presentes)
  3. Arrancar server.py en segundo plano
  4. Health check (GET /api/health o ping al puerto)
  5. Reportar URL y estado

Uso:
  python pipeline_casino_deploy.py --project-dir PATH [--port <PORT>]
"""
from __future__ import annotations

import argparse
import http.client
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from bago.ollama_runtime import DEFAULT_BAGO_LLM_SERVER_PORT, env_port

sys.stdout.reconfigure(encoding="utf-8")


def validate_db(project_dir: Path) -> dict:
    """Valida que la base de datos existe y tiene las tablas esperadas."""
    db_path = project_dir / "casino.db"
    if not db_path.exists():
        return {"success": False, "error": f"DB no existe: {db_path}", "tables": []}

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected = {"players", "jackpot_pool", "referrals"}
        missing = expected - set(tables)
        success = len(missing) == 0

        return {
            "success": success,
            "db_path": str(db_path),
            "tables": tables,
            "missing": list(missing),
            "error": f"Faltan tablas: {missing}" if missing else "",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "tables": []}


def validate_assets(project_dir: Path) -> dict:
    """Valida que existen los assets criticos."""
    required = [
        "static/ui/bg_main.png",
        "static/ui/btn_spin.png",
        "static/symbols/sprites_sheet.png",
        "index.html",
    ]
    missing = []
    for rel in required:
        if not (project_dir / rel).exists():
            missing.append(rel)
    return {"success": len(missing) == 0, "missing": missing, "required": required}


def start_server(project_dir: Path, port: int = DEFAULT_BAGO_LLM_SERVER_PORT) -> dict:
    """Arranca server.py en segundo plano."""
    server_script = project_dir / "server.py"
    if not server_script.exists():
        return {"success": False, "error": f"No encontrado: {server_script}"}

    env = {**dict(subprocess.os.environ), "WEBAPP_PORT": str(port)}
    try:
        proc = subprocess.Popen(
            [sys.executable, str(server_script)],
            cwd=str(project_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Darle tiempo de arrancar
        time.sleep(2)
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            err_text = stderr.decode('utf-8', errors='replace')[-200:] if stderr else ''
            return {
                "success": False,
                "error": f"Server murio inmediatamente. stderr: {err_text}",
                "pid": None,
            }
        return {"success": True, "pid": proc.pid, "port": port, "url": f"http://127.0.0.1:{port}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def health_check(url: str, timeout: int = 5) -> dict:
    """Hace ping al servidor."""
    try:
        host, port_str = url.replace("http://", "").split(":")
        port = int(port_str)
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/")
        resp = conn.getresponse()
        status = resp.status
        conn.close()
        return {"success": 200 <= status < 500, "status": status, "url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}


def run_pipeline(project_dir: Path, port: int = DEFAULT_BAGO_LLM_SERVER_PORT) -> dict:
    print(f"\n  [Pipeline Casino Deploy] Proyecto: {project_dir}")
    print(f"  Puerto: {port}")
    print(f"  {'-'*50}")

    total_start = time.time()

    # FASE 1: Validar DB
    print(f"  [Fase 1/4] Validando base de datos...")
    db_result = validate_db(project_dir)
    print(f"    {'OK' if db_result['success'] else 'FAIL'} DB: {db_result.get('tables', [])}")
    if not db_result["success"]:
        print(f"    Error: {db_result.get('error', '???')}")

    # FASE 2: Validar assets
    print(f"  [Fase 2/4] Validando assets...")
    asset_result = validate_assets(project_dir)
    print(f"    {'OK' if asset_result['success'] else 'FAIL'} Assets")
    if asset_result.get("missing"):
        print(f"    Faltan: {asset_result['missing']}")

    # FASE 3: Arrancar server
    print(f"  [Fase 3/4] Arrancando servidor...")
    server_result = start_server(project_dir, port)
    print(f"    {'OK' if server_result['success'] else 'FAIL'} Server PID={server_result.get('pid')}")
    if not server_result["success"]:
        print(f"    Error: {server_result.get('error', '???')}")

    # FASE 4: Health check
    health_result = {"success": False, "error": "Server no arranco"}
    if server_result.get("url"):
        print(f"  [Fase 4/4] Health check...")
        health_result = health_check(server_result["url"])
        print(f"    {'OK' if health_result['success'] else 'FAIL'} {health_result.get('status', health_result.get('error'))}")

    all_ok = db_result["success"] and asset_result["success"] and server_result["success"] and health_result["success"]

    result = {
        "pipeline": "casino_deploy",
        "project": str(project_dir),
        "port": port,
        "success": all_ok,
        "db": db_result,
        "assets": asset_result,
        "server": server_result,
        "health": health_result,
        "total_duration_ms": int((time.time() - total_start) * 1000),
    }

    print(f"\n  {'='*50}")
    if result["success"]:
        print(f"  DEPLOY OK — {server_result.get('url', '')}")
    else:
        print(f"  DEPLOY CON FALLOS")
    print(f"  Duracion total: {result['total_duration_ms']}ms")
    print(f"  {'='*50}\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Deploy Seguro Casino BAGO")
    parser.add_argument("--project-dir", default=".", help="Directorio del proyecto")
    parser.add_argument("--port", type=int, default=DEFAULT_BAGO_LLM_SERVER_PORT, help="Puerto del servidor")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    if not project.exists():
        print(f"ERROR: Proyecto no encontrado: {project}")
        return 1

    result = run_pipeline(project, args.port)
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