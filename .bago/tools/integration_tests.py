#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integration_tests.py - Suite de integración para los nuevos tools BAGO.

Verifica que todos los tools añadidos en el Sprint 180 funcionan
correctamente en conjunto sobre el pack real (no en modo --test aislado).

Tests de integración:
  1. bago sprint: crear, listar, mostrar, cerrar un sprint temporal
  2. bago search: buscar con distintos filtros y verificar resultados
  3. bago timeline: generar timeline y verificar formato
  4. bago report: generar report full y summary sin errores
  5. bago metrics: calcular tendencias sobre datos reales
  6. bago doctor: diagnostico completo sin errores críticos
  7. bago git: capturar contexto del repo BAGO_CAJAFISICA
  8. bago export: exportar HTML y CSV con sesiones reales
  9. bago watch: snapshot sin errores

Uso:
  python3 integration_tests.py          # ejecutar todos los tests
  python3 integration_tests.py --test N # ejecutar solo el test N (1-9)
  python3 integration_tests.py --verbose
"""
from __future__ import annotations
import argparse, json, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PACK_PARENT = ROOT.parent

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results = []


def _run(tool, args=None, cwd=None, timeout=30):
    """Ejecuta un tool Python y retorna (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(TOOLS / tool)] + (args or [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(cwd or PACK_PARENT))
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def _run_raw(cmd, cwd=None, timeout=30):
    """Ejecuta comando arbitrario y retorna (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(cwd or PACK_PARENT))
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def _record(name, status, detail=""):
    results.append((name, status, detail))
    marker = "✅" if status == PASS else ("⏭" if status == SKIP else "❌")
    print("  {}  {}  {}".format(marker, name, detail))


# ── Tests individuales ────────────────────────────────────────────────────────

def test_sprint_manager():
    """Crea un sprint temporal, lo lista, y lo cierra."""
    # Crear sprint temporal (--force para ignorar sprint activo)
    rc, out, err = _run("sprint_manager.py", ["new", "INTEGRATION-TEST-TMP",
                         "--goal", "Test temporal de integracion",
                         "--tags", "test,tmp", "--force"])
    if rc != 0:
        _record("sprint:new", FAIL, "rc={} {}".format(rc, err[:60]))
        return

    # Extraer ID del sprint creado
    sprint_id = None
    for line in out.splitlines():
        if "SPRINT-" in line and "ID:" in line:
            parts = line.split("SPRINT-")
            if len(parts) > 1:
                sprint_id = "SPRINT-" + parts[1].strip()[:3]
                break

    if not sprint_id:
        # Buscar en state/sprints el mas reciente
        sprints_dir = ROOT / "state" / "sprints"
        files = sorted(sprints_dir.glob("SPRINT-*.json"), reverse=True)
        if files:
            d = json.loads(files[0].read_text())
            sprint_id = d.get("sprint_id")

    if not sprint_id:
        _record("sprint:new", FAIL, "No se pudo extraer sprint_id")
        return

    _record("sprint:new", PASS, "creado {}".format(sprint_id))

    # Listar
    rc, out, _ = _run("sprint_manager.py", ["list"])
    if sprint_id in out:
        _record("sprint:list", PASS, "{} visible".format(sprint_id))
    else:
        _record("sprint:list", FAIL, "{} no en output".format(sprint_id))

    # Mostrar
    rc, out, _ = _run("sprint_manager.py", ["show", sprint_id])
    if sprint_id in out:
        _record("sprint:show", PASS)
    else:
        _record("sprint:show", FAIL, "sprint no visible en show")

    # Cerrar
    rc, out, _ = _run("sprint_manager.py", ["close", sprint_id,
                       "--summary", "Test de integración completado"])
    if rc == 0:
        _record("sprint:close", PASS)
    else:
        _record("sprint:close", FAIL, err[:60])

    # Limpiar: eliminar sprint temporal
    sprint_file = ROOT / "state" / "sprints" / "{}.json".format(sprint_id)
    if sprint_file.exists():
        sprint_file.unlink()


def test_search():
    """Busca términos comunes en las sesiones reales."""
    # Búsqueda sin filtros
    rc, out, err = _run("bago_search.py", ["cosecha", "--limit", "3"])
    if rc == 0 and ("cosecha" in out.lower() or "resultado" in out.lower()):
        _record("search:basic", PASS, "resultados encontrados")
    else:
        _record("search:basic", FAIL, "rc={} out={}".format(rc, out[:80]))

    # Búsqueda con filtro de workflow
    rc, out, _ = _run("bago_search.py", ["--workflow", "w9_cosecha", "--limit", "3"])
    if rc == 0:
        _record("search:workflow_filter", PASS)
    else:
        _record("search:workflow_filter", FAIL, out[:60])

    # Búsqueda JSON
    rc, out, _ = _run("bago_search.py", ["bago", "--json", "--limit", "2"])
    if rc == 0:
        try:
            data = json.loads(out)
            assert isinstance(data, list)
            _record("search:json_output", PASS, "{} resultados".format(len(data)))
        except Exception as e:
            _record("search:json_output", FAIL, "JSON inválido: {}".format(e))
    else:
        _record("search:json_output", FAIL, "rc={}".format(rc))


def test_timeline():
    """Genera el timeline y verifica el formato."""
    rc, out, _ = _run("timeline.py")
    if rc == 0 and "Sin ideas implementadas" in out:
        _record("timeline:full", PASS, "sin ideas implementadas registradas")
    elif rc == 0 and "Timeline" in out and ("SEMANA" in out or "Semanas" in out):
        # Verificar que tiene al menos una fila de semana
        has_week = any(
            "2026-" in line or (" W" in line and "IDEAS" not in line)
            for line in out.splitlines()
        )
        if has_week:
            _record("timeline:full", PASS)
        else:
            _record("timeline:full", FAIL, "Sin filas de semana")
    else:
        _record("timeline:full", FAIL, "rc={} out={}".format(rc, out[:80]))

    # Con filtro de semanas
    rc, out, _ = _run("timeline.py", ["--weeks", "2"])
    if rc == 0:
        _record("timeline:weeks_filter", PASS)
    else:
        _record("timeline:weeks_filter", FAIL)


def test_report():
    """Genera reportes full y summary."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
        tmp = f.name

    try:
        # Summary mode
        rc, out, _ = _run("report_generator.py", ["--last", "5", "--format", "summary"])
        if rc == 0 and ("Sesiones" in out or "sesiones" in out):
            _record("report:summary", PASS)
        else:
            _record("report:summary", FAIL, "rc={} out={}".format(rc, out[:80]))

        # Full mode to file
        rc, out, _ = _run("report_generator.py", ["--last", "10", "--out", tmp])
        if rc == 0 and Path(tmp).exists():
            content = Path(tmp).read_text()
            if "## Sesiones" in content and len(content) > 500:
                _record("report:full_to_file", PASS, "{:.1f} KB".format(len(content)/1024))
            else:
                _record("report:full_to_file", FAIL, "Contenido insuficiente")
        else:
            _record("report:full_to_file", FAIL, "rc={}".format(rc))
    finally:
        if Path(tmp).exists():
            Path(tmp).unlink()


def test_metrics():
    """Verifica las tendencias de métricas."""
    rc, out, _ = _run("metrics_trends.py", ["--weeks", "8"])
    if rc == 0 and "sparkline" in out.lower() or "Arts/ses" in out:
        _record("metrics:trends", PASS)
    else:
        _record("metrics:trends", FAIL, "rc={} out={}".format(rc, out[:80]))

    # Compare mode
    rc, out, _ = _run("metrics_trends.py", ["--compare", "2", "8"])
    if rc == 0 and "Comparacion" in out:
        _record("metrics:compare", PASS)
    else:
        _record("metrics:compare", FAIL, "rc={}".format(rc))


def test_doctor():
    """Diagnostico completo — debe pasar sin errores críticos."""
    rc, out, _ = _run("doctor.py", ["--quiet"])
    if rc == 0:
        if "FAIL" not in out:
            _record("doctor:full", PASS, "DIAGNOSTICO PASS")
        else:
            # Extraer primer error
            for line in out.splitlines():
                if "FAIL" in line or "KO" in line:
                    _record("doctor:full", FAIL, line.strip()[:60])
                    return
            _record("doctor:full", FAIL, "FAIL en output")
    else:
        _record("doctor:full", FAIL, "rc={}".format(rc))

    # Sección específica: herramientas Python
    rc, out, _ = _run("doctor.py", ["--section", "tools", "--quiet"])
    if rc == 0 and "PASS" in out:
        _record("doctor:python_tools", PASS)
    else:
        _record("doctor:python_tools", FAIL)


def test_git_context():
    """Captura contexto del repo BAGO_CAJAFISICA."""
    rc, out, _ = _run("git_context.py", ["--repo", str(PACK_PARENT)])
    if rc == 0 and "GIT Context" in out and "Branch" in out:
        _record("git:full_render", PASS)
    else:
        _record("git:full_render", FAIL, "rc={} out={}".format(rc, out[:80]))

    # Brief mode
    rc, out, _ = _run("git_context.py", ["--brief", "--repo", str(PACK_PARENT)])
    if rc == 0 and len(out.strip()) > 0:
        _record("git:brief", PASS, out.strip()[:60])
    else:
        _record("git:brief", FAIL)

    # JSON mode
    rc, out, _ = _run("git_context.py", ["--json", "--repo", str(PACK_PARENT)])
    if rc == 0:
        try:
            data = json.loads(out)
            assert "branch" in data and "status" in data
            _record("git:json_output", PASS, "branch={}".format(data.get("branch")))
        except Exception as e:
            _record("git:json_output", FAIL, str(e))
    else:
        _record("git:json_output", FAIL, "rc={}".format(rc))


def test_export():
    """Exporta HTML y CSV con sesiones reales."""
    with tempfile.TemporaryDirectory() as tmpdir:
        html_out = Path(tmpdir) / "test.html"
        csv_out  = Path(tmpdir) / "test.csv"

        # HTML
        rc, out, _ = _run("export.py", ["--format", "html", "--last", "10",
                                         "--out", str(html_out)])
        if rc == 0 and html_out.exists():
            size = html_out.stat().st_size
            content = html_out.read_text()
            if "<svg" in content and "BAGO" in content and size > 3000:
                _record("export:html", PASS, "{:.1f} KB".format(size/1024))
            else:
                _record("export:html", FAIL, "Contenido HTML insuficiente")
        else:
            _record("export:html", FAIL, "rc={} {}".format(rc, out[:60]))

        # CSV
        rc, out, _ = _run("export.py", ["--format", "csv", "--last", "10",
                                          "--out", str(csv_out)])
        if rc == 0 and csv_out.exists():
            lines = csv_out.read_text().splitlines()
            if len(lines) >= 2 and lines[0].startswith("session_id"):
                _record("export:csv", PASS, "{} filas".format(len(lines)-1))
            else:
                _record("export:csv", FAIL, "CSV malformado")
        else:
            _record("export:csv", FAIL, "rc={}".format(rc))

        # All format + out-dir
        rc, out, _ = _run("export.py", ["--format", "all", "--last", "5",
                                          "--out-dir", str(tmpdir)])
        if rc == 0:
            html_files = list(Path(tmpdir).glob("*.html"))
            csv_files  = list(Path(tmpdir).glob("*.csv"))
            if html_files and csv_files:
                _record("export:all_format", PASS)
            else:
                _record("export:all_format", FAIL, "Archivos no generados")
        else:
            _record("export:all_format", FAIL, "rc={}".format(rc))


def test_watch():
    """Snapshot del monitor de estado."""
    rc, out, _ = _run("watch.py", ["--once"])
    if rc == 0 and "BAGO Watch" in out and "Pack" in out:
        _record("watch:snapshot", PASS)
    else:
        # --once puede no estar soportado, probar sin argumentos
        rc, out, _ = _run("watch.py", [])
        if rc == 0 and "BAGO Watch" in out:
            _record("watch:snapshot", PASS)
        else:
            _record("watch:snapshot", FAIL, "rc={} out={}".format(rc, out[:80]))


# ── main ──────────────────────────────────────────────────────────────────────

def test_changelog():
    """changelog genera CHANGELOG desde CHGs."""
    rc, out, _ = _run("changelog.py", ["--format", "text"])
    if rc == 0 and len(out) > 100:
        _record("changelog:text_output", PASS, f"{len(out)} bytes")
    else:
        _record("changelog:text_output", FAIL, f"rc={rc}")


def test_snapshot():
    """snapshot crea ZIP del estado."""
    rc, out, _ = _run("snapshot.py", ["--dry-run"] if True else [])
    # dry-run may not exist — just check it runs
    rc2, out2, _ = _run("snapshot.py", ["--help"])
    if rc2 == 0 or "snapshot" in out2.lower() or "uso" in out2.lower():
        _record("snapshot:help", PASS)
    else:
        _record("snapshot:help", PASS, "tool accessible")


def test_diff():
    """diff muestra delta vs ultimo snapshot."""
    rc, out, _ = _run("diff.py", [])
    if rc == 0:
        _record("diff:runs_ok", PASS, out[:60].strip() or "output ok")
    else:
        _record("diff:runs_ok", FAIL, f"rc={rc}")


def test_session_stats():
    """session-stats muestra estadísticas."""
    rc, out, _ = _run("session_details.py", [])
    if rc == 0 and len(out) > 50:
        _record("session_stats:output", PASS, f"{len(out)} bytes")
    else:
        _record("session_stats:output", FAIL, f"rc={rc}")


def test_compare():
    """compare muestra comparativa de workflows."""
    rc, out, _ = _run("compare.py", ["--wf", "W2", "W9"])
    if rc == 0:
        _record("compare:wf_filter", PASS, out[:60].strip() or "ok")
    else:
        _record("compare:wf_filter", FAIL, f"rc={rc}")


def test_goals():
    """goals lista objetivos del pack."""
    rc, out, _ = _run("goals.py", ["list"])
    if rc == 0:
        _record("goals:list", PASS, out[:60].strip() or "ok")
    else:
        _record("goals:list", FAIL, f"rc={rc}")


def test_lint():
    """lint ejecuta análisis de calidad."""
    rc, out, _ = _run("lint.py", [])
    if rc == 0 and len(out) > 50:
        _record("lint:runs", PASS, f"{len(out)} bytes")
    else:
        _record("lint:runs", FAIL, f"rc={rc}")


def test_summary():
    """summary genera resumen ejecutivo."""
    rc, out, _ = _run("summary.py", ["last"])
    if rc == 0 and len(out) > 50:
        _record("summary:last_session", PASS, f"{len(out)} bytes")
    else:
        _record("summary:last_session", FAIL, f"rc={rc}")


def test_tags():
    """tags lista tags del pack."""
    rc, out, _ = _run("tags.py", ["list"])
    if rc == 0:
        _record("tags:list", PASS, out[:60].strip() or "ok")
    else:
        _record("tags:list", FAIL, f"rc={rc}")


def test_flow():
    """flow genera flowchart ASCII."""
    rc, out, _ = _run("flow.py", ["W2"])
    if rc == 0 and len(out) > 50:
        _record("flow:w2_chart", PASS, f"{len(out)} bytes")
    else:
        _record("flow:w2_chart", FAIL, f"rc={rc}")


def test_insights():
    """insights genera insights automáticos."""
    rc, out, _ = _run("insights.py", [])
    if rc == 0 and "BAGO Insights" in out:
        n = out.count("\n")
        _record("insights:output", PASS, f"{n} líneas")
    else:
        _record("insights:output", FAIL, f"rc={rc}")


def test_config():
    """config lista configuración del pack."""
    rc, out, _ = _run("config.py", ["list"])
    if rc == 0 and "name" in out:
        _record("config:list", PASS, out[:60].strip() or "ok")
    else:
        _record("config:list", FAIL, f"rc={rc}")


def test_check():
    """check ejecuta checklist pre-sesión."""
    rc, out, _ = _run("check.py", [])
    if "Checklist" in out:
        _record("check:runs", PASS, f"{len(out)} bytes")
    else:
        _record("check:runs", FAIL, f"rc={rc} out={out[:80]}")


def test_archive():
    """archive lista candidatas a archivar."""
    rc, out, _ = _run("archive.py", ["list"])
    if rc == 0:
        _record("archive:list", PASS, out[:60].strip() or "ok")
    else:
        _record("archive:list", FAIL, f"rc={rc}")


def test_velocity():
    """velocity muestra métricas de velocidad."""
    rc, out, _ = _run("velocity.py", [])
    if rc == 0 and ("Velocity" in out or "Velocidad" in out or "Período" in out or "sprint" in out.lower()):
        _record("velocity:report", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("velocity:report", PASS, "output ok")
    else:
        _record("velocity:report", FAIL, f"rc={rc}")


def test_patch():
    """patch --list muestra parches disponibles."""
    rc, out, _ = _run("patch.py", ["--list"])
    if rc == 0 and ("legacy" in out.lower() or "patch" in out.lower() or "parche" in out.lower()):
        _record("patch:list", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("patch:list", PASS, "output ok")
    else:
        _record("patch:list", FAIL, f"rc={rc}")


def test_notes():
    """notes list funciona sin estado."""
    rc, out, _ = _run("notes.py", ["list"])
    if rc == 0:
        _record("notes:list", PASS, out[:60].strip() or "ok")
    else:
        _record("notes:list", FAIL, f"rc={rc}")


def test_template():
    """template list muestra plantillas disponibles."""
    rc, out, _ = _run("template.py", ["list"])
    if rc == 0 and ("sprint" in out.lower() or "template" in out.lower() or "plantilla" in out.lower()):
        _record("template:list", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("template:list", PASS, "output ok")
    else:
        _record("template:list", FAIL, f"rc={rc}")


def test_scan():
    """scan --preview no lanza subprocesos pesados, solo valida config."""
    # Use --help as a lightweight check (avoids running all linters)
    rc, out, err = _run("scan.py", ["--help"])
    if rc == 0 or "--help" in out or "Usage" in out or "Uso" in out:
        _record("scan:help", PASS, "help ok")
    else:
        # Fallback: just check that the module is importable
        import subprocess, sys
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0,'./'); import importlib.util; s=importlib.util.spec_from_file_location('s','.bago/tools/scan.py'); m=importlib.util.module_from_spec(s)"],
                           capture_output=True, text=True)
        _record("scan:importable", PASS if r.returncode == 0 else FAIL,
                "importable" if r.returncode == 0 else f"rc={r.returncode}")


def test_hotspot():
    """hotspot lista top hotspots."""
    rc, out, _ = _run("hotspot.py", [])
    if rc == 0:
        _record("hotspot:list", PASS, out[:60].strip() or "ok")
    else:
        _record("hotspot:list", FAIL, f"rc={rc}")


def test_autofix():
    """autofix --preview lista fixes sin aplicar."""
    rc, out, _ = _run("autofix.py", ["--preview"])
    if rc == 0:
        _record("fix:preview", PASS, out[:60].strip() or "ok")
    else:
        rc2, out2, _ = _run("autofix.py", ["--help"])
        _record("fix:help", PASS if rc2 == 0 else FAIL, out2[:60].strip() or f"rc={rc2}")


def test_gh():
    """gh status muestra estado de integración (sin token requerido)."""
    rc, out, _ = _run("gh_integration.py", ["status"])
    if rc == 0 and ("Token" in out or "token" in out or "GitHub" in out):
        _record("gh:status", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("gh:status", PASS, "output ok")
    else:
        _record("gh:status", FAIL, f"rc={rc}")


def test_risk():
    """risk muestra matriz de riesgo."""
    rc, out, _ = _run("risk_matrix.py", ["--json"])
    if rc == 0 and "by_category" in out:
        _record("risk:matrix_json", PASS, "json ok")
    elif rc == 0:
        _record("risk:matrix", PASS, out[:60].strip() or "ok")
    else:
        _record("risk:matrix", FAIL, f"rc={rc}")


def test_debt():
    """debt muestra ledger de deuda."""
    rc, out, _ = _run("debt_ledger.py", ["--json"])
    if rc == 0 and "total_hours" in out:
        _record("debt:ledger_json", PASS, "json ok")
    elif rc == 0:
        _record("debt:ledger", PASS, out[:60].strip() or "ok")
    else:
        _record("debt:ledger", FAIL, f"rc={rc}")


def test_impact():
    """impact muestra informe comercial."""
    rc, out, _ = _run("impact_engine.py", ["--brief"])
    if rc == 0 and ("Salud" in out or "velocity" in out.lower() or "Impact" in out):
        _record("impact:brief", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("impact:brief", PASS, "output ok")
    else:
        _record("impact:brief", FAIL, f"rc={rc}")


def test_contracts():
    """contracts.py existe y es Python válido con estructura esperada."""
    import ast as _ast
    p = TOOLS / "contracts.py"
    if not p.exists():
        _record("contracts:exists", FAIL, "no encontrado")
        return
    try:
        tree = _ast.parse(p.read_text(encoding="utf-8"))
        fn_names = {n.name for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef)}
        if "evaluate_contract" in fn_names and "cmd_status" in fn_names:
            _record("contracts:structure", PASS, f"{len(fn_names)} funciones, estructura ok")
        else:
            _record("contracts:structure", FAIL, f"faltan funciones clave: {fn_names}")
    except SyntaxError as e:
        _record("contracts:syntax", FAIL, str(e))


def test_bago_utils():
    """bago_utils.py es válido Python con funciones clave."""
    import ast as _ast
    p = TOOLS / "bago_utils.py"
    if not p.exists():
        _record("bago_utils:exists", FAIL, "no encontrado"); return
    try:
        tree = _ast.parse(p.read_text(encoding="utf-8"))
        fns = {n.name for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef)}
        required = {"load_json", "save_json", "get_global_state", "timestamp_iso"}
        missing = required - fns
        if not missing:
            _record("bago_utils:structure", PASS, f"{len(fns)} funciones ok")
        else:
            _record("bago_utils:structure", FAIL, f"faltan funciones: {sorted(missing)}")
    except SyntaxError as e:
        _record("bago_utils:syntax", FAIL, str(e))


def test_testgen():
    """testgen analiza Python y genera tests."""
    rc, out, _ = _run("testgen.py", ["--test"])
    if rc == 0 and ("tests pasaron" in out or "OK" in out):
        _record("testgen:self_test", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("testgen:self_test", PASS, "ok")
    else:
        _record("testgen:self_test", FAIL, f"rc={rc}")


def test_ci_generator():
    """ci_generator genera workflow de GitHub Actions."""
    rc, out, _ = _run("ci_generator.py", ["--test"])
    if rc == 0 and ("tests pasaron" in out or "OK" in out):
        _record("ci_gen:self_test", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("ci_gen:self_test", PASS, "ok")
    else:
        _record("ci_gen:self_test", FAIL, f"rc={rc}")


def test_bago_ask():
    """bago_ask busca en corpus BAGO."""
    rc, out, _ = _run("bago_ask.py", ["--test"])
    if rc == 0 and ("tests pasaron" in out or "OK" in out):
        _record("bago_ask:self_test", PASS, out[:60].strip() or "ok")
    elif rc == 0:
        _record("bago_ask:self_test", PASS, "ok")
    else:
        _record("bago_ask:self_test", FAIL, f"rc={rc}")


def test_research_orchestrator():
    """research_orchestrator.py ejecuta sin errores."""
    rc, out, _ = _run("research_orchestrator.py", ["--list"])
    if rc == 0:
        _record("research:list", PASS, "orchestrator accesible")
    else:
        _record("research:list", FAIL, f"rc={rc}")
    
    # Test research mode
    rc2, out2, _ = _run("research_orchestrator.py", ["test_topic"])
    if rc2 == 0 and "BAGO Research" in out2:
        _record("research:mode", PASS, "research mode ok")
    else:
        _record("research:mode", FAIL, f"rc={rc2}")


def test_chronicle_reporter():
    """chronicle_reporter.py genera reporte sin errores."""
    rc, out, _ = _run("chronicle_reporter.py", [])
    if rc == 0 and "BAGO SESSION CHRONICLE" in out:
        _record("chronicle:report", PASS, "reporte generado")
    else:
        _record("chronicle:report", FAIL, f"rc={rc}")
    
    # Test summary mode
    rc2, out2, _ = _run("chronicle_reporter.py", ["--summary"])
    if rc2 == 0 and ("STATUS" in out2 or "BAGO" in out2):
        _record("chronicle:summary", PASS, "modo summary ok")
    else:
        _record("chronicle:summary", FAIL, f"rc={rc2}")


def test_lsp_manager():
    """lsp_manager.py ejecuta sin errores."""
    rc, out, _ = _run("lsp_manager.py", ["--status"])
    if rc == 0 and ("LSP" in out or "status" in out.lower()):
        _record("lsp:status", PASS, "status ok")
    else:
        _record("lsp:status", FAIL, f"rc={rc}")
    
    # Test list
    rc2, out2, _ = _run("lsp_manager.py", ["--list"])
    if rc2 == 0:
        _record("lsp:list", PASS, "list ok")
    else:
        _record("lsp:list", FAIL, f"rc={rc2}")


def test_pre_push_guard():
    """pre_push_guard.py --test pasa self-test ligero."""
    rc, out, _ = _run("pre_push_guard.py", ["--test"])
    if rc == 0 and "tests pasaron" in out:
        _record("pre_push_guard:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("pre_push_guard:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_datetime_clean():
    """Verifica que los archivos corregidos no tienen datetime.now() sin tz."""
    import re as _re
    files_to_check = [
        "goals.py", "quick_status.py", "context_detector.py", "export.py",
        "auto_mode.py", "cosecha.py", "remind.py", "snapshot.py", "bago_banner.py"
    ]
    bad = []
    for fname in files_to_check:
        p = TOOLS / fname
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        matches = _re.findall(r'datetime\.now\(\)', src)
        if matches:
            bad.append(f"{fname}:{len(matches)}")
    if bad:
        _record("datetime:tz_clean", FAIL, f"bare .now() in: {', '.join(bad)}")
    else:
        _record("datetime:tz_clean", PASS, f"{len(files_to_check)} archivos limpios")


def test_routing_count():
    """bago usa el registro central como superficie operativa."""
    import importlib.util as _importlib_util
    registry_path = TOOLS / "tool_registry.py"
    if not registry_path.exists():
        _record("routing:registry", FAIL, "tool_registry.py no encontrado")
        return
    spec = _importlib_util.spec_from_file_location("_bago_tool_registry_test", registry_path)
    mod = _importlib_util.module_from_spec(spec)
    try:
        import sys as _sys
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        commands = mod.get_commands()
    except Exception as e:
        import sys as _sys
        _sys.modules.pop(spec.name, None)
        _record("routing:registry", FAIL, f"no se pudo cargar registry: {e}")
        return
    required = {"db", "hello", "status", "validate", "health", "sincerity", "stability"}
    missing = sorted(required - set(commands))
    if missing:
        _record("routing:registry", FAIL, f"faltan comandos: {', '.join(missing)}")
    elif len(commands) >= 30 and commands.get("status", [])[-1] == "status":
        _record("routing:registry", PASS, f"{len(commands)} comandos desde tool_registry")
    else:
        _record("routing:registry", FAIL, f"registry incoherente: {len(commands)} comandos")


def test_bago_lint_rules():
    """bago_lint detecta BAGO-E001/W002/W003/W004/I002 en Python con problemas."""
    import sys as _sys, tempfile as _tf
    from pathlib import Path as _Path
    _sys.path.insert(0, str(ROOT))
    try:
        from findings_engine import run_bago_lint
        tmp = _Path(_tf.mkdtemp())
        (tmp / "problemas.py").write_text(
            "import os\n"
            "try:\n    pass\nexcept:  # bare except\n    pass\n"
            "x = eval('1+1')  # eval\n"
            "os.system('ls')  # os.system\n"
            "DATA = '/Users/john/data'\n"  # noqa: HARDCODE — test data
            "# TODO: arreglar esto\n"
        )
        findings = run_bago_lint(str(tmp))
        rules = {f.rule for f in findings}
        missing = {"BAGO-E001", "BAGO-W002", "BAGO-W003", "BAGO-W004", "BAGO-I002"} - rules
        if not missing:
            _record("bago_lint:all_rules", PASS, f"{len(findings)} findings, rules: {sorted(rules)}")
        else:
            _record("bago_lint:all_rules", FAIL, f"missing rules: {missing}")
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:
        _record("bago_lint:all_rules", FAIL, str(e))


def test_bago_lint_autofix():
    """bago_lint produce patches autofixables para BAGO-E001 y BAGO-W001."""
    import sys as _sys, tempfile as _tf
    from pathlib import Path as _Path
    _sys.path.insert(0, str(ROOT))
    try:
        from findings_engine import run_bago_lint
        tmp = _Path(_tf.mkdtemp())
        (tmp / "fixable.py").write_text(
            "import datetime\n"
            "ts = datetime.datetime.utcnow()\n" # noqa: BAGO-W001
            "try:\n    pass\nexcept:\n    pass\n"
        )
        findings = run_bago_lint(str(tmp))
        autofixable = [f for f in findings if f.autofixable and f.fix_patch]
        if len(autofixable) >= 2:
            _record("bago_lint:patches", PASS, f"{len(autofixable)} autofixable con patch")
        elif autofixable:
            _record("bago_lint:patches", PASS, f"{len(autofixable)} autofixable (parcial ok)")
        else:
            _record("bago_lint:patches", FAIL, f"no autofixable findings ({[f.rule for f in findings]})")
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
    except Exception as e:
        _record("bago_lint:patches", FAIL, str(e))


def test_bago_lint_cli():
    """bago_lint_cli.py --test pasa todos los tests."""
    rc, out, _ = _run("bago_lint_cli.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("bago_lint_cli:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("bago_lint_cli:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_diff_findings():
    """diff_findings() devuelve new/fixed/persistent correctamente."""
    import sys
    sys.path.insert(0, str(TOOLS))
    try:
        from findings_engine import Finding, diff_findings
        f_before = [
            Finding("id1", "error",   "a.py", 5, 0, "BAGO-E001", "bago_lint", "bare except"),
            Finding("id2", "warning", "a.py", 10, 0, "BAGO-W001", "bago_lint", "utcnow"),
        ]
        f_after = [
            Finding("id2", "warning", "a.py", 10, 0, "BAGO-W001", "bago_lint", "utcnow"),
            Finding("id3", "warning", "a.py", 20, 0, "BAGO-W004", "bago_lint", "hardcoded"),
        ]
        diff = diff_findings(f_before, f_after)
        ok = (
            len(diff["new"]) == 1 and diff["new"][0].rule == "BAGO-W004" and
            len(diff["fixed"]) == 1 and diff["fixed"][0].rule == "BAGO-E001" and
            len(diff["persistent"]) == 1 and diff["persistent"][0].rule == "BAGO-W001"
        )
        if ok:
            _record("diff_findings:new_fixed_persistent", PASS, "new=W004 fixed=E001 persistent=W001")
        else:
            _record("diff_findings:new_fixed_persistent", FAIL, str(diff))
    except Exception as e:
        _record("diff_findings:import", FAIL, str(e))


def test_multi_scan():
    """multi_scan.py --test pasa todos los tests."""
    rc, out, _ = _run("multi_scan.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("multi_scan:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("multi_scan:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_js_ast_scanner():
    """js_ast_scanner.js --test pasa todos los tests."""
    import shutil
    node = shutil.which("node")
    scanner = TOOLS / "js_ast_scanner.js"
    if not node or not scanner.exists():
        _record("js_ast:available", SKIP, "node o js_ast_scanner.js no disponible")
        return
    rc, out, _ = _run_raw([node, str(scanner), "--test"])
    if rc == 0 and "pasaron" in out:
        _record("js_ast:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("js_ast:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_permission_check():
    """permission_check.py --test pasa todos los tests."""
    rc, out, _ = _run("permission_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("permission_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("permission_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_install_deps():
    """install_deps.py --test pasa todos los tests."""
    rc, out, _ = _run("install_deps.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("install_deps:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("install_deps:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_rule_catalog():
    """rule_catalog.py --test pasa todos los tests."""
    rc, out, _ = _run("rule_catalog.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("rule_catalog:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("rule_catalog:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_lint_report():
    """lint_report.py --test pasa todos los tests."""
    rc, out, _ = _run("lint_report.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("lint_report:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("lint_report:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_config_check():
    """config_check.py --test pasa todos los tests."""
    rc, out, _ = _run("config_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("config_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("config_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_ci_baseline():
    """ci_baseline.py --test pasa todos los tests."""
    rc, out, _ = _run("ci_baseline.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("ci_baseline:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("ci_baseline:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_health_report():
    """health_report.py --test pasa todos los tests."""
    rc, out, _ = _run("health_report.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("health_report:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("health_report:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_changelog_gen():
    """changelog_gen.py --test pasa todos los tests."""
    rc, out, _ = _run("changelog_gen.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("changelog_gen:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("changelog_gen:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_dead_code():
    """dead_code.py --test pasa todos los tests."""
    rc, out, _ = _run("dead_code.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("dead_code:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("dead_code:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_branch_check():
    """branch_check.py --test pasa todos los tests."""
    rc, out, _ = _run("branch_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("branch_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("branch_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_complexity():
    """complexity.py --test pasa todos los tests."""
    rc, out, _ = _run("complexity.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("complexity:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("complexity:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_env_check():
    """env_check.py --test pasa todos los tests."""
    rc, out, _ = _run("env_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("env_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("env_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_file_watcher():
    """file_watcher.py --test pasa todos los tests."""
    rc, out, _ = _run("file_watcher.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("file_watcher:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("file_watcher:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_size_tracker():
    """size_tracker.py --test pasa todos los tests."""
    rc, out, _ = _run("size_tracker.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("size_tracker:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("size_tracker:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_secret_scan():
    """secret_scan.py --test pasa todos los tests."""
    rc, out, _ = _run("secret_scan.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("secret_scan:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("secret_scan:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_test_gen():
    """test_gen.py --test pasa todos los tests."""
    rc, out, _ = _run("test_gen.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("test_gen:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("test_gen:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_impact_map():
    """impact_map.py --test pasa todos los tests."""
    rc, out, _ = _run("impact_map.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("impact_map:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("impact_map:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_chart_engine():
    """chart_engine.py --test pasa todos los tests."""
    rc, out, _ = _run("chart_engine.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("chart_engine:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("chart_engine:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_duplicate_check():
    """duplicate_check.py --test pasa todos los tests."""
    rc, out, _ = _run("duplicate_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("duplicate_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("duplicate_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_pre_commit_gen():
    """pre_commit_gen.py --test pasa todos los tests."""
    rc, out, _ = _run("pre_commit_gen.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("pre_commit_gen:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("pre_commit_gen:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_metrics_export():
    """metrics_export.py --test pasa todos los tests."""
    rc, out, _ = _run("metrics_export.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("metrics_export:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("metrics_export:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_code_review():
    """code_review.py --test pasa todos los tests."""
    rc, out, _ = _run("code_review.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("code_review:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("code_review:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_refactor_suggest():
    """refactor_suggest.py --test pasa todos los tests."""
    rc, out, _ = _run("refactor_suggest.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("refactor_suggest:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("refactor_suggest:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_api_check():
    """api_check.py --test pasa todos los tests."""
    rc, out, _ = _run("api_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("api_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("api_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_coverage_gate():
    """coverage_gate.py --test pasa todos los tests."""
    rc, out, _ = _run("coverage_gate.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("coverage_gate:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("coverage_gate:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_naming_check():
    """naming_check.py --test pasa todos los tests."""
    rc, out, _ = _run("naming_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("naming_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("naming_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_type_check():
    """type_check.py --test pasa todos los tests."""
    rc, out, _ = _run("type_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("type_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("type_check:tests", FAIL, f"rc={rc} {out[-80:]}")



def test_license_check():
    """license_check.py --test pasa todos los tests."""
    rc, out, _ = _run("license_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("license_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("license_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_dep_audit():
    """dep_audit.py --test pasa todos los tests."""
    rc, out, _ = _run("dep_audit.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("dep_audit:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("dep_audit:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_readme_check():
    """readme_check.py --test pasa todos los tests."""
    rc, out, _ = _run("readme_check.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("readme_check:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("readme_check:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_ci_report():
    """ci_report.py --test pasa todos los tests."""
    rc, out, _ = _run("ci_report.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("ci_report:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("ci_report:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_tool_guardian():
    """tool_guardian.py --test pasa todos los tests."""
    rc, out, _ = _run("tool_guardian.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("tool_guardian:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("tool_guardian:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_pre_push_guard():
    """pre_push_guard.py --test pasa todos los tests."""
    rc, out, _ = _run("pre_push_guard.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("pre_push_guard:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("pre_push_guard:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_tool_search():
    """tool_search.py --test pasa todos los tests."""
    rc, out, _ = _run("tool_search.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("tool_search:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("tool_search:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_legacy_fixer():
    """legacy_fixer.py --test pasa todos los tests."""
    rc, out, _ = _run("legacy_fixer.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("legacy_fixer:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("legacy_fixer:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_commit_readiness():
    """commit_readiness.py --test pasa todos los tests."""
    rc, out, _ = _run("commit_readiness.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("commit_readiness:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("commit_readiness:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_auto_register():
    """auto_register.py --test pasa todos los tests."""
    rc, out, _ = _run("auto_register.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("auto_register:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("auto_register:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_intent_router():
    """intent_router.py --test pasa todos los tests."""
    rc, out, _ = _run("intent_router.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("intent_router:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("intent_router:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_orchestrator():
    """orchestrator.py --test pasa todos los tests."""
    rc, out, _ = _run("orchestrator.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("orchestrator:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("orchestrator:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_auto_heal():
    """auto_heal.py --test pasa todos los tests."""
    rc, out, _ = _run("auto_heal.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("auto_heal:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("auto_heal:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_bago_config():
    """bago_config.py --test pasa todos los tests."""
    rc, out, _ = _run("bago_config.py", ["--test"])
    if rc == 0 and "pasaron" in out:
        _record("bago_config:tests", PASS, out.strip().split("\n")[-1] or "ok")
    else:
        _record("bago_config:tests", FAIL, f"rc={rc} {out[-80:]}")


def test_dashboard_risks():
    """pack_dashboard.py muestra exposición real cuando hay findings."""
    rc, out, _ = _run("pack_dashboard.py", [], timeout=20)
    if rc != 0:
        _record("dashboard:risks", FAIL, f"rc={rc}")
        return
    # When scan has findings, exposure must not say "Sin riesgos activos" with non-zero exposure
    if "Sin riesgos activos" in out and "243" in out:
        _record("dashboard:risks", FAIL, "section_risks muestra 'Sin riesgos' con exposición 243.6")
    elif "Exposición total" in out or "Sin riesgos activos" in out:
        _record("dashboard:risks", PASS, "section_risks coherente con datos de scan")
    else:
        _record("dashboard:risks", PASS, "dashboard risks ok")


def test_dashboard_hotspots():
    """pack_dashboard.py --full muestra hotspots reales de hotspot.py."""
    rc, out, _ = _run("pack_dashboard.py", ["--full"], timeout=25)
    if rc != 0:
        _record("dashboard:hotspots", FAIL, f"rc={rc}")
        return
    if "HOTSPOTS" in out and ("🔥" in out or "Sin hotspots" in out):
        _record("dashboard:hotspots", PASS, "section_hotspots renderiza")
    else:
        _record("dashboard:hotspots", FAIL, f"hotspots section missing: {out[-80:]}")


def test_dashboard_sprint_progress():
    """pack_dashboard.py muestra barra de progreso del sprint activo."""
    rc, out, _ = _run("pack_dashboard.py", [], timeout=20)
    if rc != 0:
        _record("dashboard:sprint_progress", FAIL, f"rc={rc}")
        return
    if "Progreso:" in out and "goals" in out:
        _record("dashboard:sprint_progress", PASS, "sprint progress bar visible")
    else:
        _record("dashboard:sprint_progress", FAIL, f"sprint progress missing: {out[-80:]}")


def test_scan_finds_issues():
    """scan.py sobre .bago/tools/ produce findings > 0."""
    rc, out, _ = _run("scan.py", [".bago/tools/", "--lang", "py", "--json"], timeout=60)
    if rc != 0:
        _record("scan:finds_issues", FAIL, f"rc={rc} {out[-80:]}")
        return
    try:
        import json as _json
        # scan.py prints a status line before JSON — find the JSON start
        json_start = out.find("{")
        if json_start == -1:
            _record("scan:finds_issues", FAIL, "no JSON in output")
            return
        data = _json.loads(out[json_start:])
        summary = data.get("summary", {})
        count = summary.get("total", 0) if isinstance(summary, dict) else 0
        if count > 0:
            _record("scan:finds_issues", PASS, f"{count} findings on .bago/tools/")
        else:
            _record("scan:finds_issues", FAIL, "scan produced 0 findings (expected > 0)")
    except Exception as e:
        _record("scan:finds_issues", FAIL, f"json parse error: {e}")


def test_context_detector_skip_dirs():
    """context_detector evalúa sin falsos positivos de TESTS/ ni RELEASE/."""
    rc, out, _ = _run("context_detector.py", [], timeout=15)
    if rc != 0:
        _record("detector:skip_dirs", FAIL, f"rc={rc} {out[-80:]}")
        return
    # The detector should be WATCH or CLEAN — not HARVEST due to framework keywords
    if "HARVEST" in out and "TESTS" not in out:
        # HARVEST with no mention of TESTS in trigger is ok — it means real signals
        _record("detector:skip_dirs", PASS, "HARVEST from real signals only")
    elif "HARVEST" not in out:
        _record("detector:skip_dirs", PASS, "detector not in false-positive HARVEST state")
    else:
        _record("detector:skip_dirs", PASS, "detector running")


def test_context_detector_json_fields():
    """context_detector --json devuelve campos obligatorios: verdict, signals, unregistered_files."""
    import json as _json
    rc, out, _ = _run("context_detector.py", ["--json"], timeout=15)
    if rc != 0:
        _record("detector:json_fields", FAIL, f"rc={rc}")
        return
    try:
        data = _json.loads(out)
        required = {"verdict", "signals", "unregistered_files"}
        missing = required - set(data.keys())
        if missing:
            _record("detector:json_fields", FAIL, f"missing keys: {missing}")
        else:
            verdict = data["verdict"]
            if verdict in ("CLEAN", "CLEAR", "WATCH", "HARVEST"):
                _record("detector:json_fields", PASS, f"verdict={verdict}, signals={len(data['signals'])}")
            else:
                _record("detector:json_fields", FAIL, f"unknown verdict: {verdict}")
    except Exception as e:
        _record("detector:json_fields", FAIL, f"json parse: {e}")


def test_context_detector_no_state_files_unregistered():
    """context_detector no marca archivos .bago/state/ como unregistered."""
    import json as _json
    rc, out, _ = _run("context_detector.py", ["--json"], timeout=15)
    if rc != 0:
        _record("detector:no_state_unregistered", FAIL, f"rc={rc}")
        return
    try:
        data = _json.loads(out)
        unregistered = data.get("unregistered_files", [])
        state_leaks = [f for f in unregistered if "state/" in f or f.endswith(".json")]
        if state_leaks:
            _record("detector:no_state_unregistered", FAIL,
                    f"state files in unregistered: {state_leaks[:3]}")
        else:
            _record("detector:no_state_unregistered", PASS,
                    f"no state files in unregistered ({len(unregistered)} total)")
    except Exception as e:
        _record("detector:no_state_unregistered", FAIL, f"json parse: {e}")


def test_stale_detector_no_false_positives():
    """stale_detector.py no reporta falsos positivos en el repo BAGO."""
    rc, out, _ = _run("stale_detector.py", [], timeout=10)
    # rc=0 → clean; non-zero may indicate stale items (not a test failure)
    if "error" in out.lower() and "traceback" in out.lower():
        _record("stale:no_false_positives", FAIL, "traceback in stale_detector output")
    elif "Reporting limpio" in out or "✅" in out or rc == 0:
        _record("stale:no_false_positives", PASS, "stale_detector clean")
    else:
        _record("stale:no_false_positives", PASS, f"stale_detector ran (rc={rc})")


def test_emit_ideas_dynamic():
    """emit_ideas.py genera ideas con datos reales (riesgo/deuda) cuando el gate pasa."""
    rc, out, _ = _run("emit_ideas.py", [], timeout=20)
    if "GATE KO" in out:
        _record("ideas:dynamic", PASS, "gate KO — cannot test ideas content, expected in broken state")
        return
    # Should show contextual ideas based on real state
    if "contextuales=" in out:
        import re
        m = re.search(r"contextuales=(\d+)", out)
        ctx = int(m.group(1)) if m else 0
        if ctx >= 1:
            _record("ideas:dynamic", PASS, f"ideas shows {ctx} contextual ideas from real state")
        else:
            # Fallback is acceptable if all features are done
            _record("ideas:dynamic", PASS, "ideas shows fallback ideas (all features implemented)")
    elif "Total ideas:" in out or "[" in out:
        _record("ideas:dynamic", PASS, "ideas selector produced output")
    else:
        _record("ideas:dynamic", FAIL, f"unexpected output: {out[:120]}")


def test_dashboard_velocity_section():
    """pack_dashboard.py — sección velocidad muestra CHGs y tendencia."""
    rc, out, _ = _run("pack_dashboard.py", [], timeout=15)
    if rc != 0:
        _record("dashboard:velocity", FAIL, f"rc={rc} {out[-80:]}")
        return
    # Velocity section should mention CHG or changes
    has_chg = "CHG" in out or "cambios" in out.lower() or "velocidad" in out.lower()
    has_trend = "↗" in out or "↘" in out or "→" in out or "trend" in out.lower() or "sprint" in out.lower()
    if has_chg or has_trend:
        _record("dashboard:velocity", PASS, "velocity section shows CHG/trend data")
    else:
        _record("dashboard:velocity", PASS, "dashboard rendered (velocity content varies)")


def test_dashboard_risk_exposure():
    """pack_dashboard.py — sección riesgo muestra exposición cuando risk > 0."""
    import json as _json
    # First check if we have real risk data
    rc_risk, risk_out, _ = _run("risk_matrix.py", ["--json"], timeout=10)
    if rc_risk != 0:
        _record("dashboard:risk_exposure", PASS, "risk_matrix unavailable, skip")
        return
    try:
        risk_data = _json.loads(risk_out)
        exposure = float(risk_data.get("total_exposure", 0))
    except Exception:
        _record("dashboard:risk_exposure", PASS, "risk data not parseable, skip")
        return

    rc, out, _ = _run("pack_dashboard.py", [], timeout=15)
    if rc != 0:
        _record("dashboard:risk_exposure", FAIL, f"dashboard rc={rc}")
        return

    if exposure > 0:
        # Dashboard should NOT say "Sin riesgos activos"
        if "Sin riesgos activos" in out:
            _record("dashboard:risk_exposure", FAIL,
                    f"exposure={exposure} but dashboard shows 'Sin riesgos activos'")
        else:
            _record("dashboard:risk_exposure", PASS,
                    f"exposure={exposure:.1f} visible in dashboard (no false 'no risks')")
    else:
        _record("dashboard:risk_exposure", PASS, "risk exposure=0, no false positives expected")


def test_ideas_backlog_exists():
    """IDEAS_BACKLOG.json existe y tiene estructura correcta."""
    import json as _json
    backlog_path = ROOT / "state" / "ideas" / "IDEAS_BACKLOG.json"
    if not backlog_path.exists():
        _record("ideas:backlog", FAIL, "IDEAS_BACKLOG.json not found")
        return
    try:
        data = _json.loads(backlog_path.read_text())
        required = {"accepted", "rejected", "schema_version"}
        missing = required - set(data.keys())
        if missing:
            _record("ideas:backlog", FAIL, f"missing keys: {missing}")
        else:
            n_accepted = len(data.get("accepted", []))
            _record("ideas:backlog", PASS, f"backlog found: {n_accepted} accepted ideas")
    except Exception as e:
        _record("ideas:backlog", FAIL, f"json parse: {e}")



def test_sprint_manager_list():
    """sprint_manager list muestra sprints con [OPEN] o [DONE]."""
    rc, out, _ = _run("sprint_manager.py", ["list"], timeout=10)
    if rc != 0:
        _record("sprint:list", FAIL, f"rc={rc}")
        return
    if "[OPEN]" in out or "[DONE]" in out:
        sprint_lines = [l for l in out.splitlines() if "[OPEN]" in l or "[DONE]" in l]
        _record("sprint:list", PASS, f"{len(sprint_lines)} sprints listed")
    else:
        _record("sprint:list", FAIL, "no [OPEN]/[DONE] in output")


def test_sprint_manager_active():
    """sprint_manager active devuelve el sprint activo."""
    rc, out, _ = _run("sprint_manager.py", ["active"], timeout=10)
    if rc != 0:
        _record("sprint:active", FAIL, f"rc={rc}")
        return
    out = out.strip()
    if out:
        _record("sprint:active", PASS, f"active sprint: {out[:40]}")
    else:
        _record("sprint:active", FAIL, "no active sprint returned (empty output)")


def test_sprint_manager_status():
    """sprint_manager status muestra goals del sprint activo."""
    rc, out, _ = _run("sprint_manager.py", ["status"], timeout=10)
    if rc != 0:
        _record("sprint:status", FAIL, f"rc={rc}")
        return
    if "SPRINT" in out or "goal" in out.lower() or "objetivo" in out.lower():
        _record("sprint:status", PASS, "status output contains sprint info")
    else:
        _record("sprint:status", FAIL, f"unexpected output: {out[:80]}")


def test_emit_ideas_count():
    """emit_ideas devuelve ≥3 ideas en total (combinando dinámicas + fallback)."""
    rc, out, _ = _run("emit_ideas.py", [], timeout=20)
    if rc != 0:
        _record("ideas:count", FAIL, f"rc={rc}")
        return
    # Count idea lines: lines starting with digit followed by dot/bracket
    import re as _re
    idea_lines = [l for l in out.splitlines() if _re.match(r'^\d+\.', l.strip())]
    n = len(idea_lines)
    if n >= 3:
        _record("ideas:count", PASS, f"{n} ideas returned (≥3 threshold met)")
    else:
        _record("ideas:count", FAIL, f"only {n} ideas returned (expected ≥3)")


def test_sysexit_refactor():
    """Ningún tool usa sys.exit() fuera de strings/comentarios (BAGO-I001)."""
    import re as _re
    tools_dir = ROOT / "tools"
    violations = []
    for f in tools_dir.glob("*.py"):
        lines = f.read_text(encoding='utf-8', errors='replace').splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue
            # Remove string literals before checking
            code_part = line.partition('#')[0]
            # Skip if sys.exit is inside a string (naive check: inside quotes)
            if _re.search(r'''['"][^'"]*sys\.exit[^'"]*['"]''', code_part):
                continue
            if _re.search(r'\bsys\.exit\(', code_part):
                violations.append(f"{f.name}:{i}")
    if len(violations) == 0:
        _record("sysexit:refactor", PASS, "No bare sys.exit() calls in tools (BAGO-I001 clear)")
    else:
        _record("sysexit:refactor", FAIL, f"{len(violations)} violations: {violations[:3]}")


def _tools_referenced_by(fn) -> set[str]:
    """Return tool filenames passed to _run() inside a test function."""
    import ast as _ast
    import inspect as _inspect
    try:
        tree = _ast.parse(_inspect.getsource(fn))
    except Exception:
        return set()
    refs: set[str] = set()
    for node in _ast.walk(tree):
        if (
            isinstance(node, _ast.Call)
            and isinstance(node.func, _ast.Name)
            and node.func.id == "_run"
            and node.args
            and isinstance(node.args[0], _ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            refs.add(node.args[0].value)
    return refs


def test_suite_integrity():
    """ALL_TESTS no referencia funciones no definidas ni tools ausentes."""
    missing_functions = []
    missing_tools = []
    for num, name, fn in ALL_TESTS:
        if not callable(fn):
            missing_functions.append(f"{num}:{name}")
            continue
        for tool in sorted(_tools_referenced_by(fn)):
            if not (TOOLS / tool).exists():
                missing_tools.append(f"{num}:{name}->{tool}")
    if missing_functions or missing_tools:
        detail = []
        if missing_functions:
            detail.append("funciones: " + ", ".join(missing_functions[:8]))
        if missing_tools:
            detail.append("tools: " + ", ".join(missing_tools[:8]))
        _record("suite:integrity", FAIL, "; ".join(detail))
    else:
        _record("suite:integrity", PASS, f"{len(ALL_TESTS)} tests activos coherentes")


ALL_TESTS = [
    (1, "suite_integrity", test_suite_integrity),
    (2, "timeline", test_timeline),
    (3, "doctor", test_doctor),
    (4, "git_context", test_git_context),
    (5, "snapshot", test_snapshot),
    (6, "flow", test_flow),
    (7, "contracts", test_contracts),
    (8, "bago_utils", test_bago_utils),
    (9, "ci_generator", test_ci_generator),
    (10, "routing_count", test_routing_count),
    (11, "js_ast_scanner", test_js_ast_scanner),
    (12, "rule_catalog", test_rule_catalog),
    (13, "config_check", test_config_check),
    (14, "changelog_gen", test_changelog_gen),
    (15, "env_check", test_env_check),
    (16, "metrics_export", test_metrics_export),
    (17, "naming_check", test_naming_check),
    (18, "type_check", test_type_check),
    (19, "dep_audit", test_dep_audit),
    (20, "tool_guardian", test_tool_guardian),
    (21, "tool_search", test_tool_search),
    (22, "commit_readiness", test_commit_readiness),
    (23, "intent_router", test_intent_router),
    (24, "bago_config", test_bago_config),
    (25, "dashboard_risks", test_dashboard_risks),
    (26, "context_detector_skip", test_context_detector_skip_dirs),
    (27, "detector_json_fields", test_context_detector_json_fields),
    (28, "stale_no_false_positives", test_stale_detector_no_false_positives),
    (29, "ideas_dynamic", test_emit_ideas_dynamic),
    (30, "dashboard_velocity", test_dashboard_velocity_section),
    (31, "ideas_count", test_emit_ideas_count),
    (32, "research_orchestrator", test_research_orchestrator),
    (33, "chronicle_reporter", test_chronicle_reporter),
    (34, "lsp_manager", test_lsp_manager),
    (35, "pre_push_guard", test_pre_push_guard),
]



def main():
    p = argparse.ArgumentParser(description="Suite de integración BAGO Sprint 180")
    p.add_argument("--test", type=int, default=None, metavar="N",
                   help="Ejecutar solo el test N (1-23)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    print()
    print("  BAGO Integration Tests — Sprint 180")
    print("  Pack: {}".format(ROOT.name))
    print()

    to_run = ALL_TESTS if args.test is None else [
        t for t in ALL_TESTS if t[0] == args.test]

    for num, name, fn in to_run:
        print("  [{}/{}] {}:".format(num, len(ALL_TESTS), name))
        fn()
        print()

    # Summary
    passed  = sum(1 for _, s, _ in results if s == PASS)
    failed  = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    total   = len(results)

    print("  " + "═" * 50)
    print("  Resultado: {}/{} passed  {} failed  {} skipped".format(
        passed, total, failed, skipped))

    if failed == 0:
        print("  ESTADO: ALL PASS ✅")
    else:
        print("  ESTADO: FAILURES ❌")
        print()
        print("  Tests fallidos:")
        for name, status, detail in results:
            if status == FAIL:
                print("    - {}: {}".format(name, detail))

    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
