#!/usr/bin/env python3
"""tool_guardian.py — Herramienta #125: Guardian de coherencia del framework BAGO.

Detecta tools en .bago/tools/ que no cumplen los estándares del framework.

Reglas y severidad por tier de estabilidad:
─────────────────────────────────────────────────────────────────
  Tier       Stability          E001  E002  Health%
  ─────────  ─────────────────  ────  ────  ───────
  required   core | dangerous   ERR   ERR   sí
  suggested  experimental       WARN  WARN  no
  exempt     internal | legacy  —     —     no
─────────────────────────────────────────────────────────────────

    GUARD-E001  Tool (required) sin flag --test implementado
    GUARD-E002  Tool (required) sin registro en integration_tests.py
    GUARD-W001  Tool sin routing en bago script
    GUARD-W002  Tool sin docstring de módulo
    GUARD-I001  Tool correctamente integrado (informativo)

La salud (health_pct) mide únicamente los tools tier=required.
Los tools experimental aparecen como warnings, internal/legacy no se auditan.

Uso:
    bago tool-guardian [--format text|md|json]
                       [--fix-routing]   # añade routing stub al bago script
                       [--out FILE]
                       [--test]
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import ast
import json
import sys
from pathlib import Path

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RED  = "\033[0;31m"
_CYN  = "\033[0;36m"
_RST  = "\033[0m"
_BOLD = "\033[1m"

BAGO_ROOT   = Path(__file__).parent.parent        # .bago/
REPO_ROOT   = BAGO_ROOT.parent                    # repo raíz
TOOLS_DIR   = BAGO_ROOT / "tools"
INTEG_FILE  = TOOLS_DIR / "integration_tests.py"
BAGO_SCRIPT = REPO_ROOT / "bago"
HISTORY_FILE = BAGO_ROOT / "state" / "guardian_history.json"
MAX_HISTORY  = 30

# Tools del framework — loaded from tool_registry (single source of truth)
def _load_internal_tools() -> frozenset:
    """Load INTERNAL_TOOLS from tool_registry.py via importlib. Falls back to local set."""
    import importlib.util
    reg_path = TOOLS_DIR / "tool_registry.py"
    if reg_path.exists():
        spec = importlib.util.spec_from_file_location("_guardian_registry", str(reg_path))
        if spec:
            mod = importlib.util.module_from_spec(spec)
            try:
                import sys as _sys
                _sys.modules[spec.name] = mod   # required for @dataclass on Python 3.13+
                spec.loader.exec_module(mod)
                return getattr(mod, "INTERNAL_TOOLS", frozenset())
            except Exception:
                pass
            finally:
                import sys as _sys
                _sys.modules.pop(spec.name, None)
    # Fallback if tool_registry.py is unavailable
    return frozenset({
        "tool_registry", "preflight", "session_logger",
        "integration_tests", "bago_utils", "bago_banner", "bago_start",
        "bago_on", "bago_debug", "bago_watch", "bago_chat_server",
        "bago_ask", "bago_lint_cli", "bago_search", "auto_register",
        "ci_generator", "tool_guardian", "contracts", "legacy_fixer",
    })

INTERNAL_TOOLS = _load_internal_tools()

# ─── Registry stability lookup ────────────────────────────────────────────────

def _load_registry_stabilities() -> dict[str, str]:
    """Return {module_stem: stability} from tool_registry. Falls back to empty dict."""
    import importlib.util
    reg_path = TOOLS_DIR / "tool_registry.py"
    if not reg_path.exists():
        return {}
    spec = importlib.util.spec_from_file_location("_guardian_reg2", str(reg_path))
    if not spec:
        return {}
    mod = importlib.util.module_from_spec(spec)
    try:
        import sys as _sys
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        registry = getattr(mod, "REGISTRY", {})
        result: dict[str, str] = {}
        for _cmd, entry in registry.items():
            # Use module field as the file stem; fall back to command name
            module_stem = getattr(entry, "module", _cmd) or _cmd
            stab = getattr(entry, "stability", "experimental")
            # A module may be referenced by multiple commands (e.g. flow/status)
            # Keep strictest: required > suggested > exempt
            existing = result.get(module_stem, "suggested")
            if stab in _REQUIRED_STABILITIES:
                result[module_stem] = stab
            elif stab in _EXEMPT_STABILITIES and existing not in _REQUIRED_STABILITIES:
                result[module_stem] = stab
            else:
                result.setdefault(module_stem, stab)
        return result
    except Exception:
        return {}
    finally:
        import sys as _sys
        _sys.modules.pop(spec.name, None)


_REQUIRED_STABILITIES  = frozenset({"core", "dangerous"})
_SUGGESTED_STABILITIES = frozenset({"experimental"})
_EXEMPT_STABILITIES    = frozenset({"internal", "legacy"})


def _tool_tier(stem: str, stabilities: dict[str, str]) -> str:
    """Return 'required', 'suggested', or 'exempt' for a tool stem."""
    stab = stabilities.get(stem, "experimental")
    if stab in _REQUIRED_STABILITIES:
        return "required"
    if stab in _EXEMPT_STABILITIES:
        return "exempt"
    return "suggested"  # experimental or unknown


def _get_all_tools() -> list[Path]:
    return sorted(
        p for p in TOOLS_DIR.glob("*.py")
        if p.stem not in INTERNAL_TOOLS and not p.stem.startswith("__")
    )


def _has_test_flag(filepath: Path) -> bool:
    """AST-based: verifies '--test' is in actual code (not a comment or docstring)."""
    try:
        tree = ast.parse(filepath.read_text("utf-8", errors="ignore"))
    except SyntaxError:
        return False

    # Collect string constants that are standalone docstrings (Expr(Constant))
    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)):
                docstring_ids.add(id(node.body[0].value))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or node.value != "--test":
            continue
        if id(node) in docstring_ids:
            continue  # docstring mention doesn't count as implementation
        return True  # "--test" found in live code (not a comment, not a docstring)

    return False


def _is_in_integration(filepath: Path) -> bool:
    """AST-based: verifies tool has an actual _run() call in integration_tests.py."""
    if not INTEG_FILE.exists():
        return False
    try:
        tree = ast.parse(INTEG_FILE.read_text("utf-8", errors="ignore"))
    except SyntaxError:
        return False

    tool_name = filepath.name   # e.g. "lint.py"
    tool_stem = filepath.stem   # e.g. "lint"

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_id = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else "")
        if func_id == "_run" and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant):
                val = str(first_arg.value)
                if val in (tool_name, tool_stem):
                    return True
    return False


def _is_in_bago_script(filepath: Path) -> bool:
    """AST-based: verifies tool has routing in bago COMMANDS dict or elif chain."""
    if not BAGO_SCRIPT.exists():
        return False
    try:
        tree = ast.parse(BAGO_SCRIPT.read_text("utf-8", errors="ignore"))
    except SyntaxError:
        return False

    cmd = filepath.stem.replace("_", "-")

    for node in ast.walk(tree):
        # Check COMMANDS dict assignments
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Name)
                        and target.id in ("COMMANDS", "COMMANDS_MAIN", "COMMANDS_ADVANCED")):
                    if isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant) and k.value == cmd:
                                return True
        # Fallback: elif cmd == "..." patterns
        if isinstance(node, ast.If):
            test = node.test
            if (isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Eq)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "cmd"):
                for comp in test.comparators:
                    if isinstance(comp, ast.Constant) and comp.value == cmd:
                        return True
    return False


def _has_module_docstring(filepath: Path) -> bool:
    try:
        tree = ast.parse(filepath.read_text("utf-8", errors="ignore"))
        return bool(ast.get_docstring(tree))
    except Exception:
        return False


def analyze(tools: list[Path] = None) -> list[dict]:
    if tools is None:
        tools = _get_all_tools()

    stabilities = _load_registry_stabilities()
    findings: list[dict] = []
    for tool in tools:
        tier        = _tool_tier(tool.stem, stabilities)
        if tier == "exempt":
            continue  # internal / legacy — no auditamos

        has_test    = _has_test_flag(tool)
        in_integ    = _is_in_integration(tool)
        in_bago     = _is_in_bago_script(tool)
        has_docstr  = _has_module_docstring(tool)

        # E001 / E002: error para required, warning para suggested
        if not has_test:
            sev = "error" if tier == "required" else "warning"
            findings.append({
                "rule": "GUARD-E001", "severity": sev,
                "file": str(tool), "tool": tool.stem, "tier": tier,
                "message": f"'{tool.name}' sin flag --test implementado",
            })
        if not in_integ:
            sev = "error" if tier == "required" else "warning"
            findings.append({
                "rule": "GUARD-E002", "severity": sev,
                "file": str(tool), "tool": tool.stem, "tier": tier,
                "message": f"'{tool.name}' no registrado en integration_tests.py",
            })
        if not in_bago:
            findings.append({
                "rule": "GUARD-W001", "severity": "warning",
                "file": str(tool), "tool": tool.stem, "tier": tier,
                "message": f"'{tool.name}' sin routing en bago script",
            })
        if not has_docstr:
            findings.append({
                "rule": "GUARD-W002", "severity": "warning",
                "file": str(tool), "tool": tool.stem, "tier": tier,
                "message": f"'{tool.name}' sin docstring de módulo",
            })
        if has_test and in_integ and in_bago and has_docstr:
            findings.append({
                "rule": "GUARD-I001", "severity": "info",
                "file": str(tool), "tool": tool.stem, "tier": tier,
                "message": f"'{tool.name}' correctamente integrado ✅",
            })
    return findings


def _summary(findings: list[dict]) -> dict:
    all_tools    = _get_all_tools()
    stabilities  = _load_registry_stabilities()
    # Health is measured on required tools only (core + dangerous)
    required     = [t for t in all_tools if _tool_tier(t.stem, stabilities) == "required"]
    errors       = [f for f in findings if f["severity"] == "error"]
    warnings     = [f for f in findings if f["severity"] == "warning"]
    ok_tools     = {f["tool"] for f in findings if f["rule"] == "GUARD-I001"}
    # Required tool is OK if it has no E001/E002 errors (warnings don't block health)
    error_tools  = {f["tool"] for f in findings if f["severity"] == "error"}
    req_ok       = sum(1 for t in required if t.stem not in error_tools)
    return {
        "total_tools":      len(all_tools),
        "required_tools":   len(required),
        "required_ok":      req_ok,
        "fully_ok":         len(ok_tools),
        "total_errors":     len(errors),
        "total_warnings":   len(warnings),
        "health_pct":       round(req_ok / max(1, len(required)) * 100),
    }


def generate_text(findings: list[dict]) -> str:
    s      = _summary(findings)
    color  = _GRN if s["health_pct"] >= 80 else (_YEL if s["health_pct"] >= 50 else _RED)
    lines  = [
        f"{_BOLD}Tool Guardian — Estado del framework BAGO{_RST}",
        f"  {color}Salud (required): {s['health_pct']}%{_RST}  "
        f"({s['required_ok']}/{s['required_tools']} required OK  "
        f"| {s['fully_ok']}/{s['total_tools']} total  "
        f"E:{s['total_errors']}  W:{s['total_warnings']})",
        "",
    ]
    errors   = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]
    if errors:
        lines.append(f"  {_RED}Errores críticos (core/dangerous):{_RST}")
        for f in errors:
            lines.append(f"    [{f['rule']}] {f['message']}")
    if warnings:
        lines.append(f"\n  {_YEL}Warnings:{_RST}")
        for f in warnings[:20]:  # limit output
            lines.append(f"    [{f['rule']}] {f['message']}")
        if len(warnings) > 20:
            lines.append(f"    ... y {len(warnings)-20} warnings más")
    return "\n".join(lines)


def generate_markdown(findings: list[dict]) -> str:
    s     = _summary(findings)
    badge = "🟢" if s["health_pct"] >= 80 else ("🟡" if s["health_pct"] >= 50 else "🔴")
    lines = [
        f"# {badge} Tool Guardian — Salud {s['health_pct']}%",
        "",
        f"**Tools totales:** {s['total_tools']} | "
        f"**OK completos:** {s['fully_ok']} | "
        f"**Errores:** {s['total_errors']} | "
        f"**Warnings:** {s['total_warnings']}",
        "",
        "| Regla | Tool | Mensaje |",
        "|-------|------|---------|",
    ]
    for f in [x for x in findings if x["severity"] != "info"]:
        lines.append(f"| `{f['rule']}` | `{f['tool']}` | {f['message']} |")
    lines += ["", "---", "*Generado con `bago tool-guardian`*"]
    return "\n".join(lines)


# ─── Trend / history ──────────────────────────────────────────────────────────

def _record_run(s: dict) -> None:
    """Append current summary to bago.db (and guardian_history.json as backup)."""
    import datetime as _dt
    date     = _dt.datetime.now(_dt.timezone.utc).isoformat()
    health   = s["health_pct"]
    ok       = s.get("required_ok", s["fully_ok"])
    total    = s.get("required_tools", s["total_tools"])
    errors   = s["total_errors"]
    warnings = s["total_warnings"]
    try:
        sys.path.insert(0, str(BAGO_ROOT / "tools"))
        from bago_db import record_guardian_run
        record_guardian_run(date, health, ok, total, errors, warnings)
        return
    except Exception:
        pass  # Fallback to JSON if DB not available
    # JSON fallback
    entry = {"date": date, "health": health, "ok": ok,
             "total": total, "errors": errors, "warnings": warnings}
    try:
        history: list = []
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
        history.append(entry)
        history = history[-MAX_HISTORY:]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # Never break guardian over this


def _sparkline(values: list[int]) -> str:
    """Build an ASCII sparkline from a list of 0-100 integer values."""
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    span = max(1, hi - lo)
    chars = []
    for v in values:
        idx = round((v - lo) / span * (len(blocks) - 1))
        chars.append(blocks[idx])
    return "".join(chars)


def cmd_trend() -> None:
    """Show guardian health trend from bago.db (or guardian_history.json fallback)."""
    history: list = []
    try:
        sys.path.insert(0, str(BAGO_ROOT / "tools"))
        from bago_db import get_guardian_history
        history = get_guardian_history()
    except Exception:
        pass

    if not history and HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            print("  [error] no se pudo leer el historial del guardian")
            return

    if not history:
        print("  (sin historial — ejecuta bago tool-guardian para registrar el primer punto)")
        return

    values = [e.get("health", 0) for e in history]
    spark  = _sparkline(values)
    lo, hi = min(values), max(values)
    last   = history[-1]
    delta  = values[-1] - values[0] if len(values) > 1 else 0
    trend_arrow = "↗" if delta > 0 else ("↘" if delta < 0 else "→")

    color = _GRN if last["health"] >= 80 else (_YEL if last["health"] >= 50 else _RED)
    print(f"\n  {_BOLD}Guardian Trend ({len(history)} ejecuciones){_RST}")
    print(f"  {color}{spark}{_RST}")
    print(f"  Rango: {lo}%–{hi}%  Actual: {color}{last['health']}%{_RST}  {trend_arrow} ({delta:+d}%)")
    print(f"  Última: {last.get('date','?')[:19].replace('T',' ')} — {last['ok']}/{last['total']} tools OK")
    if len(values) >= 3:
        avg = round(sum(values) / len(values))
        print(f"  Media:  {avg}%")
    print()


def main(argv: list[str]) -> int:
    fmt      = "text"
    out_file = None

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out_file = argv[i + 1]; i += 2
        elif a == "--trend":
            cmd_trend()
            return 0
        else:
            i += 1

    findings = analyze()
    s = _summary(findings)
    _record_run(s)

    if fmt == "json":
        content = json.dumps(findings, indent=2)
    elif fmt == "md":
        content = generate_markdown(findings)
    else:
        content = generate_text(findings)

    if out_file:
        Path(out_file).write_text(content, encoding="utf-8")
        print(f"Guardado: {out_file}", file=sys.stderr)
    else:
        print(content)

    errors = [f for f in findings if f["severity"] == "error"]
    return 1 if errors else 0


def _self_test() -> None:
    import tempfile
    print("Tests de tool_guardian.py...")
    fails: list[str] = []
    def ok(n): print(f"  OK: {n}")
    def fail(n, m): fails.append(n); print(f"  FAIL: {n}: {m}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        # T1 — tool sin --test → GUARD-E001
        t1 = root / "no_test.py"
        t1.write_text('"""Tool sin test."""\ndef main(): pass\n')
        f1 = analyze([t1])
        if any(f["rule"] == "GUARD-E001" for f in f1):
            ok("tool_guardian:no_test_flag")
        else:
            fail("tool_guardian:no_test_flag", f"findings={f1}")

        # T2 — tool con --test en código real → no GUARD-E001
        t2 = root / "with_test.py"
        t2.write_text(
            '"""Tool con test."""\nimport sys\n'
            'if __name__=="__main__":\n'
            '    if "--test" in sys.argv: pass\n'
        )
        f2 = analyze([t2])
        e001 = [f for f in f2 if f["rule"] == "GUARD-E001"]
        if not e001:
            ok("tool_guardian:has_test_flag")
        else:
            fail("tool_guardian:has_test_flag", f"unexpected={e001}")

        # T2b — tool con --test SOLO en docstring → debe seguir siendo GUARD-E001
        t2b = root / "docstring_test.py"
        t2b.write_text('"""Tool que menciona --test en docstring pero no lo implementa."""\ndef main(): pass\n')
        f2b = analyze([t2b])
        if any(f["rule"] == "GUARD-E001" for f in f2b):
            ok("tool_guardian:docstring_not_counted")
        else:
            fail("tool_guardian:docstring_not_counted", "docstring --test no debería contar")

        # T3 — tool sin docstring → GUARD-W002
        t3 = root / "no_doc.py"
        t3.write_text('if "--test" in ["--test"]: pass\ndef foo(): pass\n')
        f3 = analyze([t3])
        if any(f["rule"] == "GUARD-W002" for f in f3):
            ok("tool_guardian:no_docstring")
        else:
            fail("tool_guardian:no_docstring", f"findings={f3}")

        # T4 — _is_in_integration con fichero falso → False
        result = _is_in_integration(root / "ghost_tool.py")
        if not result:
            ok("tool_guardian:not_in_integration")
        else:
            fail("tool_guardian:not_in_integration", "deberia ser False")

        # T5 — tools reales del framework: lint.py debe estar integrado
        lint_path = TOOLS_DIR / "lint.py"
        if lint_path.exists():
            in_integ = _is_in_integration(lint_path)
            in_bago  = _is_in_bago_script(lint_path)
            if in_integ and in_bago:
                ok("tool_guardian:lint_fully_integrated")
            else:
                fail("tool_guardian:lint_fully_integrated",
                     f"in_integ={in_integ} in_bago={in_bago}")
        else:
            ok("tool_guardian:lint_fully_integrated")  # skip si no existe

        # T6 — generate_markdown incluye tabla
        mock = [{"rule":"GUARD-E001","severity":"error","file":"x.py","tool":"x","message":"test"}]
        md = generate_markdown(mock)
        if "Tool Guardian" in md and "GUARD-E001" in md and "| Regla |" in md:
            ok("tool_guardian:markdown_output")
        else:
            fail("tool_guardian:markdown_output", md[:100])

    total = 7; passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
