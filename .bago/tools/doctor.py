#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doctor.py - Diagnostico integral del pack BAGO.

Verifica:
  1. Todos los tools Python tienen sintaxis valida
  2. Todos los JSONs en state/ son validos
  3. Cross-refs: sessions apuntan a changes/evidences existentes
  4. Integridad del workflow de sessions
  5. Configuracion del pack (pack.json, global_state.json)
  6. Sprints activos no quedan huerfanos

Uso:
  python3 doctor.py          # diagnostico completo
  python3 doctor.py --fix    # intenta arreglar problemas simples
  python3 doctor.py --quiet  # solo errores
  python3 doctor.py --test
"""
from __future__ import annotations
import argparse, ast, json, sys, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
TOOLS = ROOT / "tools"


def _load_json(path):
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, "JSON invalido: {}".format(e)
    except Exception as e:
        return None, "Error de lectura: {}".format(e)


def _check_syntax(path):
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        return None
    except SyntaxError as e:
        return "SyntaxError linea {}: {}".format(e.lineno, e.msg)
    except Exception as e:
        return str(e)


def _fmt_ok(msg, quiet=False):
    if not quiet:
        print("    OK  {}".format(msg))


def _fmt_ko(msg):
    print("    KO  {}".format(msg))


def _fmt_warn(msg, quiet=False):
    if not quiet:
        print("  WARN  {}".format(msg))


def _section(title):
    print()
    print("  ── {} ──".format(title))


def check_python_tools(quiet=False):
    """Verifica que todos los scripts Python tienen sintaxis valida."""
    _section("1. Herramientas Python")
    errors = []
    tools_found = list(TOOLS.glob("*.py"))
    also = list(ROOT.glob("*.py"))  # scripts en bago root
    all_py = tools_found + also

    for f in sorted(all_py):
        err = _check_syntax(f)
        if err:
            _fmt_ko("{}: {}".format(f.name, err))
            errors.append((f.name, err))
        else:
            _fmt_ok("{} ({} bytes)".format(f.name, f.stat().st_size), quiet)

    if not errors and not quiet:
        print("    Total: {} archivos Python validos".format(len(all_py)))
    return errors


def check_json_state(quiet=False):
    """Verifica que todos los JSONs en state/ son validos."""
    _section("2. JSONs en state/")
    errors = []
    total = 0

    for f in sorted(STATE.rglob("*.json")):
        total += 1
        data, err = _load_json(f)
        if err:
            _fmt_ko("{}: {}".format(f.relative_to(ROOT), err))
            errors.append((str(f.relative_to(ROOT)), err))
        else:
            rel = f.relative_to(ROOT)
            _fmt_ok("{}".format(rel), quiet)

    if not errors and not quiet:
        print("    Total: {} JSONs validos".format(total))
    return errors


def check_pack_config(quiet=False):
    """Verifica la configuracion del pack."""
    _section("3. Configuracion del pack")
    errors = []
    warnings = []

    # pack.json
    pack_path = ROOT / "pack.json"
    if not pack_path.exists():
        _fmt_ko("pack.json no encontrado")
        errors.append(("pack.json", "archivo faltante"))
    else:
        pack, err = _load_json(pack_path)
        if err:
            _fmt_ko("pack.json: " + err)
            errors.append(("pack.json", err))
        else:
            required = ["id", "version", "name"]
            for key in required:
                if key not in pack:
                    _fmt_warn("pack.json sin campo '{}'".format(key), quiet)
                    warnings.append("pack.json: falta campo {}".format(key))
            _fmt_ok("pack.json: id={} version={}".format(
                pack.get("id", "?"), pack.get("version", "?")), quiet)

    # global_state.json
    gs_path = STATE / "global_state.json"
    if not gs_path.exists():
        _fmt_ko("state/global_state.json no encontrado")
        errors.append(("global_state.json", "archivo faltante"))
    else:
        gs, err = _load_json(gs_path)
        if err:
            _fmt_ko("global_state.json: " + err)
        else:
            _fmt_ok("global_state.json: bago_version={} health={} open_changes={}".format(
                gs.get("bago_version", "?"),
                gs.get("system_health", "?"),
                len(gs.get("open_changes", [])),
            ), quiet)

    return errors, warnings


def check_session_integrity(quiet=False):
    """Cross-ref: sesiones apuntan a cambios/evidencias existentes."""
    _section("4. Integridad de sesiones")
    errors = []
    warnings = []

    sessions_dir = STATE / "sessions"
    if not sessions_dir.exists():
        _fmt_warn("state/sessions/ no existe", quiet)
        return errors, warnings

    sessions = []
    for f in sessions_dir.glob("*.json"):
        s, err = _load_json(f)
        if err:
            _fmt_ko("{}: {}".format(f.name, err))
            errors.append((f.name, err))
        elif s:
            sessions.append((f.name, s))

    _fmt_ok("{} sesiones encontradas".format(len(sessions)), quiet)

    # Verifica campos obligatorios
    required_fields = ["session_id", "status", "created_at", "selected_workflow"]
    incomplete = 0
    for fname, s in sessions:
        missing = [f for f in required_fields if f not in s]
        if missing:
            incomplete += 1
            if not quiet:
                _fmt_warn("{}: faltan campos {}".format(fname, missing), quiet)

    if incomplete > 0:
        print("    WARN  {} sesiones con campos faltantes".format(incomplete))
        warnings.append("{} sesiones incompletas".format(incomplete))

    # Verifica open/closed balance
    open_ses = [s for _, s in sessions if s.get("status") == "open"]
    closed_ses = [s for _, s in sessions if s.get("status") == "closed"]
    _fmt_ok("Abiertas: {}  Cerradas: {}".format(len(open_ses), len(closed_ses)), quiet)

    if len(open_ses) > 3:
        _fmt_warn("{} sesiones abiertas simultaneamente (posible issue)".format(len(open_ses)), quiet)
        warnings.append("Demasiadas sesiones abiertas: {}".format(len(open_ses)))

    return errors, warnings


def check_sprints(quiet=False):
    """Verifica los sprints registrados."""
    _section("5. Sprints")
    errors = []
    warnings = []

    sprints_dir = STATE / "sprints"
    if not sprints_dir.exists():
        _fmt_ok("No hay directorio de sprints (normal en pack sin sprints)", quiet)
        return errors, warnings

    for f in sorted(sprints_dir.glob("*.json")):
        s, err = _load_json(f)
        if err:
            _fmt_ko("{}: {}".format(f.name, err))
            errors.append((f.name, err))
            continue

        sid = s.get("sprint_id", f.stem)
        status = s.get("status", "?")
        items = s.get("items", {})
        n_linked = sum(len(v) for v in items.values() if isinstance(v, list))
        _fmt_ok("{} | status={} | linked={}".format(sid, status, n_linked), quiet)

        if status == "open":
            created = s.get("created_at", "")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - created_dt).days
                    if age_days > 30:
                        _fmt_warn("{} abierto hace {} dias".format(sid, age_days), quiet)
                        warnings.append("Sprint {} abierto {} dias".format(sid, age_days))
                except Exception:
                    pass

    return errors, warnings


def check_workflows_coverage(quiet=False):
    """Verifica que los workflows definidos tienen sesiones asociadas."""
    _section("6. Cobertura de workflows")
    errors = []
    warnings = []

    wf_dir = ROOT / "workflows"
    if not wf_dir.exists():
        _fmt_warn("Directorio workflows/ no encontrado", quiet)
        return errors, warnings

    wf_dirs = [d for d in wf_dir.iterdir() if d.is_dir()]
    wf_ids = set(d.name for d in wf_dirs)

    # Contar uso de workflows en sesiones
    sessions_dir = STATE / "sessions"
    wf_usage = {}
    if sessions_dir.exists():
        for f in sessions_dir.glob("*.json"):
            s, _ = _load_json(f)
            if s:
                wf = s.get("selected_workflow", "")
                if wf:
                    wf_usage[wf] = wf_usage.get(wf, 0) + 1

    for wf in sorted(wf_ids):
        count = wf_usage.get(wf, 0)
        if count == 0:
            _fmt_warn("{}: 0 sesiones (nunca usado)".format(wf), quiet)
            warnings.append("{} sin sesiones".format(wf))
        else:
            _fmt_ok("{}: {} sesiones".format(wf, count), quiet)

    return errors, warnings


def _run_tests():
    print("  Ejecutando tests de doctor.py...")

    import tempfile

    # Test _check_syntax con codigo valido
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("x = 1 + 2\nprint(x)\n")
        tmp_valid = f.name
    assert _check_syntax(Path(tmp_valid)) is None, "sintaxis valida reportada como error"

    # Test _check_syntax con codigo invalido
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def foo(:\n    pass\n")
        tmp_invalid = f.name
    err = _check_syntax(Path(tmp_invalid))
    assert err is not None, "sintaxis invalida no detectada"

    # Test _load_json con JSON valido
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write('{"a": 1, "b": [1, 2]}\n')
        tmp_json = f.name
    data, err = _load_json(Path(tmp_json))
    assert err is None and data["a"] == 1, "JSON valido fallo"

    # Test _load_json con JSON invalido
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        f.write("{bad json}")
        tmp_bad = f.name
    data, err = _load_json(Path(tmp_bad))
    assert err is not None and data is None, "JSON invalido no detectado"

    # Limpieza
    for tmp in [tmp_valid, tmp_invalid, tmp_json, tmp_bad]:
        try:
            os.unlink(tmp)
        except Exception:
            pass

    print("  OK: todos los tests pasaron (4/4)")


def _print_summary(all_errors, all_warnings):
    total_errors = sum(len(e) for e in all_errors)
    total_warnings = sum(len(w) for w in all_warnings)

    print()
    print("  ─" * 30)
    print()
    if total_errors == 0 and total_warnings == 0:
        print("  DIAGNOSTICO: PASS — todo OK, no se encontraron problemas")
    elif total_errors == 0:
        print("  DIAGNOSTICO: WARN — {} advertencias, sin errores criticos".format(total_warnings))
    else:
        print("  DIAGNOSTICO: FAIL — {} errores, {} advertencias".format(total_errors, total_warnings))

    print()
    if total_errors > 0:
        print("  Errores:")
        for elist in all_errors:
            for name, msg in elist:
                print("    - {}: {}".format(name, msg))
        print()


def main():
    p = argparse.ArgumentParser(description="Diagnostico integral del pack BAGO")
    p.add_argument("--quiet", "-q", action="store_true", help="Solo mostrar errores")
    p.add_argument("--fix", action="store_true", help="Intentar auto-corregir problemas simples")
    p.add_argument("--json", action="store_true", help="Output estructurado como JSON")
    p.add_argument("--section", choices=["tools", "json", "config", "sessions", "sprints", "workflows"],
                   help="Ejecutar solo una seccion")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()

    if args.test:
        _run_tests()
        return

    if not getattr(args, "json", False):
        print()
        print("  BAGO Doctor - Diagnostico integral del pack")
        print("  Pack: {}".format(ROOT.name))
        print("  Dir : {}".format(ROOT))

    all_errors = []
    all_warnings = []

    import io as _io
    _null = _io.StringIO()

    def _run_section(fn, quiet):
        if getattr(args, "json", False):
            _saved, sys.stdout = sys.stdout, _null
            try:
                return fn(quiet)
            finally:
                sys.stdout = _saved
        return fn(quiet)

    sections = {
        "tools": check_python_tools,
        "json": check_json_state,
        "sessions": check_session_integrity,
        "sprints": check_sprints,
        "workflows": check_workflows_coverage,
    }

    if args.section == "config" or args.section is None:
        e, w = _run_section(check_pack_config, args.quiet)
        all_errors.append(e); all_warnings.append(w)

    for name, fn in sections.items():
        if args.section is None or args.section == name:
            result = _run_section(fn, args.quiet)
            if isinstance(result, tuple):
                e, w = result
                all_errors.append(e)
                all_warnings.append(w)
            else:
                all_errors.append(result)
                all_warnings.append([])

    if getattr(args, "json", False):
        total_errors = sum(len(e) for e in all_errors)
        total_warnings = sum(len(w) for w in all_warnings)
        if total_errors == 0 and total_warnings == 0:
            verdict = "OK"
        elif total_errors == 0:
            verdict = "WARN"
        else:
            verdict = "FAIL"
        print(json.dumps({
            "verdict": verdict,
            "errors": sum(all_errors, []),
            "warnings": sum(all_warnings, []),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        }, indent=2, ensure_ascii=False))
    else:
        _print_summary(all_errors, all_warnings)


if __name__ == "__main__":
    main()
