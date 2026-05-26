#!/usr/bin/env python3
"""auto_register.py — Registro automático de nuevos tools en el framework BAGO.

Cada tool nuevo requiere editar manualmente 3 archivos:
  1. integration_tests.py — añadir def test_X() + ALL_TESTS entry
  2. bago script — routing (v3.2-kernel+: via tool_registry, no injection needed)
  3. CHECKSUMS.sha256 — regen

Este tool automatiza los 3 pasos. Solo necesitas el nombre del tool.

Uso:
    python3 auto_register.py tool_name.py
    python3 auto_register.py tool_name.py --cmd "command-name" --desc "descripción"
    python3 auto_register.py --check tool_name.py     # verifica si ya está registrado
    python3 auto_register.py --check-all              # estado de todos los tools
    python3 auto_register.py --fix-all                # registra todos los tools sin registro
    python3 auto_register.py --fix-all --dry-run      # muestra qué registraría --fix-all
    python3 auto_register.py --dry-run tool_name.py   # muestra qué haría
    python3 auto_register.py --test                   # self-tests

Códigos:
  REG-I001  Registrado (routing inyectado — modo legacy pre-v3.2)
  REG-I002  Dispatch vía tool_registry (v3.2-kernel+); solo añadir a REGISTRY
  REG-W001  Ya registrado
  REG-E001  Error (no se pudo registrar)
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

import sys
import re
import json
import hashlib
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = Path(__file__).parent
BAGO_SCRIPT = BAGO_ROOT.parent / "bago"
INTEGRATION_TESTS = TOOLS_DIR / "integration_tests.py"
CHECKSUMS_FILE = BAGO_ROOT / "CHECKSUMS.sha256"
TREE_FILE = BAGO_ROOT / "TREE.txt"

def _load_internal_tools_auto() -> set:
    """Load INTERNAL_TOOLS from tool_registry (as .py filenames). Falls back to local set."""
    import importlib.util
    reg_path = TOOLS_DIR / "tool_registry.py"
    if reg_path.exists():
        spec = importlib.util.spec_from_file_location("_auto_registry", str(reg_path))
        if spec:
            mod = importlib.util.module_from_spec(spec)
            try:
                import sys as _sys
                _sys.modules[spec.name] = mod   # required for @dataclass on Python 3.13+
                spec.loader.exec_module(mod)
                stems = getattr(mod, "INTERNAL_TOOLS", frozenset())
                return {s + ".py" for s in stems} | {"__init__.py"}
            except Exception:
                pass
            finally:
                import sys as _sys
                _sys.modules.pop(spec.name, None)
    return {
        "bago_utils.py", "bago_banner.py", "integration_tests.py",
        "tool_registry.py", "__init__.py", "auto_register.py",
        "legacy_fixer.py", "preflight_engine.py", "session_logger.py",
        "ci_generator.py", "tool_guardian.py", "contracts.py",
        "bago_start.py", "bago_on.py", "bago_debug.py",
    }

INTERNAL_TOOLS = _load_internal_tools_auto()


def tool_file_to_cmd(tool_file: str) -> str:
    """Convierte 'my_tool.py' → 'my-tool'."""
    return Path(tool_file).stem.replace("_", "-")


def tool_file_to_func(tool_file: str) -> str:
    """Convierte 'my_tool.py' → 'test_my_tool'."""
    return "test_" + Path(tool_file).stem


def tool_file_to_stem(tool_file: str) -> str:
    return Path(tool_file).stem


def is_in_integration_tests(tool_file: str) -> bool:
    """AST-based: verifies tool has an actual _run() call in integration_tests.py."""
    import ast as _ast
    if not INTEGRATION_TESTS.exists():
        return False
    try:
        tree = _ast.parse(INTEGRATION_TESTS.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    stem = tool_file_to_stem(tool_file)
    tool_name = f"{stem}.py"
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        func = node.func
        func_id = func.id if isinstance(func, _ast.Name) else (
            func.attr if isinstance(func, _ast.Attribute) else "")
        if func_id == "_run" and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, _ast.Constant):
                val = str(first_arg.value)
                if val in (tool_name, stem):
                    return True
    return False


def is_in_bago_script(tool_file: str) -> bool:
    """Verifies tool has routing in bago COMMANDS dict, elif chain, or tool_registry (v3.2+).

    Since v3.2-kernel, bago uses registry-based dispatch (_build_commands from tool_registry).
    If the bago script references tool_registry, we check the REGISTRY directly.
    Falls back to AST inspection for legacy elif-chain routing.
    """
    import ast as _ast
    if not BAGO_SCRIPT.exists():
        return False

    cmd = tool_file_to_cmd(tool_file)

    # v3.2-kernel+: check tool_registry.REGISTRY (registry-based dispatch)
    try:
        src = BAGO_SCRIPT.read_text(encoding="utf-8")
        if "_build_commands" in src or "tool_registry" in src:
            import importlib.util as _ilu
            reg_path = TOOLS_DIR / "tool_registry.py"
            if reg_path.exists():
                _spec = _ilu.spec_from_file_location("_ibs_reg", str(reg_path))
                if _spec:
                    _mod = _ilu.module_from_spec(_spec)
                    import sys as _sys
                    _sys.modules[_spec.name] = _mod
                    _spec.loader.exec_module(_mod)
                    if cmd in getattr(_mod, "REGISTRY", {}):
                        return True
    except Exception:
        pass

    # Legacy path: AST inspection for COMMANDS dict or elif-chain routing
    try:
        tree = _ast.parse(BAGO_SCRIPT.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in _ast.walk(tree):
        # Check COMMANDS dict assignments (literal dicts only)
        if isinstance(node, _ast.Assign):
            for target in node.targets:
                if (isinstance(target, _ast.Name)
                        and target.id in ("COMMANDS", "COMMANDS_MAIN", "COMMANDS_ADVANCED")):
                    if isinstance(node.value, _ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, _ast.Constant) and k.value == cmd:
                                return True
        # Fallback: elif cmd == "..." patterns
        if isinstance(node, _ast.If):
            test = node.test
            if (isinstance(test, _ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], _ast.Eq)
                    and isinstance(test.left, _ast.Name)
                    and test.left.id == "cmd"):
                for comp in test.comparators:
                    if isinstance(comp, _ast.Constant) and comp.value == cmd:
                        return True
    return False


def get_next_test_number(src: str) -> int:
    """Determina el siguiente número de test en ALL_TESTS."""
    nums = re.findall(r'^\s*\((\d+),\s*"', src, re.MULTILINE)
    if not nums:
        return 1
    return max(int(n) for n in nums) + 1


def generate_test_function(tool_file: str) -> str:
    """Genera la función test para integration_tests.py con output JSON estructurado."""
    import hashlib as _hashlib
    stem = tool_file_to_stem(tool_file)
    func_name = tool_file_to_func(tool_file)
    tool_path = TOOLS_DIR / tool_file
    # Trap #12: embed SHA-256 of tool file so CI can detect stale tests
    if tool_path.exists():
        tool_hash = _hashlib.sha256(tool_path.read_bytes()).hexdigest()[:16]
    else:
        tool_hash = "0000000000000000"
    return f'''
# TOOL_HASH:{stem}:{tool_hash}
def {func_name}():
    """{stem}.py --test ejecuta assertions reales y emite JSON estructurado.

    TOOL_HASH:{tool_hash}  # auto-generated; regenerate when tool changes
    """
    import hashlib as _h
    _tool_path = Path(__file__).parent / "{tool_file}"
    if _tool_path.exists():
        _current_hash = _h.sha256(_tool_path.read_bytes()).hexdigest()[:16]
        if _current_hash != "{tool_hash}":
            _record("{stem}:tests", FAIL, f"STALE TEST: tool hash {{_current_hash}} != embedded {tool_hash} — regenerar con auto_register.py")
            return
    rc, out, err = _run("{stem}.py", ["--test"])
    if rc != 0:
        _record("{stem}:tests", FAIL, f"rc={{rc}} {{(err or out)[-80:]}}")
        return
    # Validate structured JSON output: {{"tool": ..., "status": "ok", "checks": [...]}}
    try:
        data = json.loads(out.strip().splitlines()[-1] if out.strip() else "{{}}")
        assert data.get("status") == "ok", f"status={{data.get('status')}}"
        checks = data.get("checks", [])
        assert isinstance(checks, list) and len(checks) > 0, "checks list empty"
        failed = [c for c in checks if not c.get("passed", False)]
        if failed:
            _record("{stem}:tests", FAIL, f"{{len(failed)}} checks failed: {{failed[0].get('name','')}}")
        else:
            _record("{stem}:tests", PASS, f"{{len(checks)}} checks OK")
    except (json.JSONDecodeError, AssertionError, IndexError) as e:
        _record("{stem}:tests", FAIL, f"bad JSON output: {{e}} | last line: {{out.strip().splitlines()[-1][:60] if out.strip() else '(empty)'}}")
'''


def register_in_integration_tests(tool_file: str, dry_run: bool = False) -> str:
    """Añade test function + ALL_TESTS entry en integration_tests.py."""
    if is_in_integration_tests(tool_file):
        return "REG-W001"
    try:
        src = INTEGRATION_TESTS.read_text(encoding="utf-8")
        func_name = tool_file_to_func(tool_file)
        stem = tool_file_to_stem(tool_file)

        # 1. Generate test function
        test_func = generate_test_function(tool_file)

        # 2. Insert test function before ALL_TESTS = [
        all_tests_pos = src.find("\nALL_TESTS = [")
        if all_tests_pos == -1:
            return "REG-E001"

        new_src = src[:all_tests_pos] + test_func + src[all_tests_pos:]

        # 3. Find last entry in ALL_TESTS and insert after it
        next_num = get_next_test_number(new_src)
        new_entry = f'\n    ({next_num}, "{stem}", {func_name}),'
        # Insert before the closing ]
        end_of_list = new_src.rfind("\n]", new_src.find("ALL_TESTS = ["))
        if end_of_list == -1:
            return "REG-E001"
        new_src = new_src[:end_of_list] + new_entry + new_src[end_of_list:]

        if not dry_run:
            INTEGRATION_TESTS.write_text(new_src, encoding="utf-8")
        return "REG-I001"
    except Exception as e:
        return f"REG-E001:{e}"


def register_in_bago_script(tool_file: str, description: str = "", dry_run: bool = False) -> str:
    """Añade routing elif + help entry en el script bago.

    Since v3.2-kernel, the bago launcher dispatches via tool_registry (COMMANDS
    is built dynamically from REGISTRY). If neither legacy anchor exists,
    the tool is handled automatically by the registry — no injection needed.
    Returns REG-I002 in that case.
    """
    if is_in_bago_script(tool_file):
        return "REG-W001"
    try:
        src = BAGO_SCRIPT.read_text(encoding="utf-8")

        # v3.2-kernel+: launcher uses registry-based dispatch (_build_commands).
        # If the bago script has _build_commands, injection is not needed.
        if "_build_commands" in src or "tool_registry" in src:
            return "REG-I002"  # Registry-based dispatch: tool is registered when added to REGISTRY.

        stem = tool_file_to_stem(tool_file)
        cmd = tool_file_to_cmd(tool_file)

        # Legacy path (pre-v3.2): inject elif routing block.
        routing_anchor = '    elif cmd == "hotspot":'
        if routing_anchor not in src:
            return "REG-E001"

        new_routing = f'''    elif cmd == "{cmd}":
        subprocess.run(
            [sys.executable, str(TOOLS / "{stem}.py")] + rest,
            cwd=str(BAGO_ROOT.parent)
        )
'''
        src = src.replace(routing_anchor, new_routing + routing_anchor)

        if not dry_run:
            BAGO_SCRIPT.write_text(src, encoding="utf-8")
        return "REG-I001"
    except Exception as e:
        return f"REG-E001:{e}"


def regen_checksums(dry_run: bool = False) -> bool:
    """Regenera CHECKSUMS.sha256 y TREE.txt."""
    if dry_run:
        return True
    try:
        py_files = sorted(TOOLS_DIR.glob("*.py"))
        js_files = sorted(TOOLS_DIR.glob("*.js"))
        all_files = py_files + js_files
        lines = []
        for f in all_files:
            content = f.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            rel = f.relative_to(BAGO_ROOT)
            lines.append(f"{sha}  {rel}")
        CHECKSUMS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # TREE
        all_entries = sorted(BAGO_ROOT.rglob("*"))
        tree_lines = []
        for e in all_entries:
            if ".git" in str(e) or "node_modules" in str(e) or "__pycache__" in str(e):
                continue
            tree_lines.append(str(e.relative_to(BAGO_ROOT)))
        TREE_FILE.write_text("\n".join(tree_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def check_registration(tool_file: str) -> dict:
    return {
        "tool": tool_file,
        "integration": is_in_integration_tests(tool_file),
        "routing": is_in_bago_script(tool_file),
        "in_tools": (TOOLS_DIR / tool_file).exists(),
    }


def check_all() -> list:
    results = []
    for f in sorted(TOOLS_DIR.glob("*.py")):
        if f.name in INTERNAL_TOOLS:
            continue
        results.append(check_registration(f.name))
    return results


def cmd_register(tool_file: str, description: str = "", dry_run: bool = False) -> int:
    if not tool_file.endswith(".py"):
        tool_file += ".py"
    filepath = TOOLS_DIR / tool_file
    if not filepath.exists():
        print(f"  [REG-E001] No existe: {tool_file}")
        return 1

    print(f"\n  Registrando: {tool_file}" + (" (DRY-RUN)" if dry_run else ""))
    print("  " + "─" * 46)

    # 1. Integration tests
    code = register_in_integration_tests(tool_file, dry_run=dry_run)
    if code == "REG-I001" or code.startswith("REG-I001"):
        print(f"  [REG-I001] ✅  integration_tests.py → test_{tool_file_to_stem(tool_file)}")
    elif code == "REG-W001":
        print("  [REG-W001] ⚠️  integration_tests.py → ya registrado")
    else:
        print(f"  [{code}] ❌  integration_tests.py")

    # 2. Bago script
    code2 = register_in_bago_script(tool_file, description, dry_run=dry_run)
    cmd = tool_file_to_cmd(tool_file)
    if code2 == "REG-I001":
        print(f"  [REG-I001] ✅  bago script → elif cmd == '{cmd}'")
    elif code2 == "REG-W001":
        print("  [REG-W001] ⚠️  bago script → ya registrado")
    else:
        print(f"  [{code2}] ❌  bago script")

    # 3. CHECKSUMS
    if not dry_run:
        ok = regen_checksums()
        print(f"  [REG-I001] {'✅' if ok else '❌'}  CHECKSUMS + TREE regenerados")
    else:
        print("  [REG-I001] DRY  CHECKSUMS sería regenerado")

    print()
    return 0


def cmd_check_all():
    results = check_all()
    total = len(results)
    fully = sum(1 for r in results if r["integration"] and r["routing"])
    print(f"\n  Tool Registration Status — {fully}/{total} completamente integrados")
    print("  " + "─" * 56)
    for r in results:
        it = "✅" if r["integration"] else "❌"
        rt = "✅" if r["routing"] else "❌"
        print(f"  {r['tool']:35s}  test:{it}  route:{rt}")
    print()


def cmd_fix_all(dry_run: bool = False) -> int:
    """Registra todos los tools no registrados en integration_tests.py y COMMANDS_MAIN.

    Estrategia:
    - Solo actúa sobre tools que no están en INTERNAL_TOOLS.
    - Un tool se considera "no registrado" si falta en integration_tests.py
      O si falta en el routing del script bago (COMMANDS_MAIN).
    - Nunca sobrescribe registros existentes (idempotente).
    - Regenera manifest y checksums al final si hubo cambios.
    """
    # INTERNAL_TOOLS ya contiene nombres con sufijo .py (via _load_internal_tools_auto)
    candidates = [
        p for p in sorted(TOOLS_DIR.glob("*.py"))
        if p.name not in INTERNAL_TOOLS
        and not p.stem.startswith("__")
    ]

    unregistered = [
        p for p in candidates
        if not is_in_integration_tests(p.name) or not is_in_bago_script(p.name)
    ]

    if not unregistered:
        print(f"\n  ✅  fix-all: todos los tools ya están registrados ({len(candidates)} tools)")
        return 0

    print(f"\n  fix-all {'(DRY-RUN) ' if dry_run else ''}— {len(unregistered)} tools sin registro completo")
    print("  " + "─" * 56)

    registered = 0
    errors = 0
    for p in unregistered:
        it = "✅" if is_in_integration_tests(p.name) else "❌"
        rt = "✅" if is_in_bago_script(p.name) else "❌"
        print(f"\n  {p.name}  test:{it}  route:{rt}")
        rc = cmd_register(p.name, dry_run=dry_run)
        if rc == 0:
            registered += 1
        else:
            errors += 1

    if not dry_run and registered > 0:
        regen_checksums()
        print(f"\n  CHECKSUMS + TREE regenerados")

    print(f"\n  fix-all completado: {registered} registrados, {errors} errores")
    return 0 if errors == 0 else 1


def run_tests():
    results = []

    # Test 1: tool_file_to_cmd
    cmd = tool_file_to_cmd("my_awesome_tool.py")
    ok1 = cmd == "my-awesome-tool"
    results.append(("auto_register:file_to_cmd", ok1, f"cmd={cmd}"))

    # Test 2: tool_file_to_func
    fn = tool_file_to_func("dep_audit.py")
    ok2 = fn == "test_dep_audit"
    results.append(("auto_register:file_to_func", ok2, f"fn={fn}"))

    # Test 3: is_in_integration_tests for known tool
    ok3 = is_in_integration_tests("dep_audit.py")
    results.append(("auto_register:detect_registered", ok3, "dep_audit should be in suite"))

    # Test 4: is_in_bago_script for known routing
    ok4 = is_in_bago_script("cosecha.py")
    results.append(("auto_register:detect_bago_routing", ok4, "cosecha should have routing"))

    # Test 5: get_next_test_number
    fake_src = 'ALL_TESTS = [\n    (1, "a", test_a),\n    (2, "b", test_b),\n]'
    n = get_next_test_number(fake_src)
    ok5 = n == 3
    results.append(("auto_register:next_test_number", ok5, f"n={n}"))

    # Test 6: generate_test_function produces valid Python
    import ast
    func_src = generate_test_function("my_tool.py")
    try:
        ast.parse(func_src)
        ok6 = True
    except SyntaxError:
        ok6 = False
    results.append(("auto_register:generate_func_valid_python", ok6, ""))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        status = "✅" if ok else "❌"
        print(f"  {status}  {name}: {detail}")
    print(f"\n  {passed}/{len(results)} pasaron")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        raise SystemExit(0)

    if "--test" in args:
        raise SystemExit(run_tests())

    if "--gen-manifest" in args:
        # Trap #8: generate canonical .bago/tools.manifest.json
        internal = {
            "integration_tests", "bago_utils", "bago_banner", "bago_start", "bago_on",
            "bago_debug", "bago_watch", "bago_chat_server", "bago_ask", "bago_lint_cli",
            "bago_search", "auto_register", "ci_generator", "tool_guardian", "contracts",
        }
        tools_data: dict = {}
        for p in sorted(TOOLS_DIR.glob("*.py")):
            if p.stem.startswith("_") or p.stem in internal:
                continue
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            tools_data[p.stem] = {
                "file": p.name,
                "sha256": sha,
                "cmd": tool_file_to_cmd(p.name),
            }
        manifest = {
            "version": 1,
            "generated_by": "auto_register.py --gen-manifest",
            "tool_count": len(tools_data),
            "tools": tools_data,
        }
        out = BAGO_ROOT / "tools.manifest.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"  Manifest generado: {out}  ({len(tools_data)} tools)")
        raise SystemExit(0)

    dry_run = "--dry-run" in args
    args_clean = [a for a in args if not a.startswith("--")]

    if "--check-all" in args:
        cmd_check_all()
        raise SystemExit(0)

    if "--fix-all" in args:
        raise SystemExit(cmd_fix_all(dry_run=dry_run))

    if "--check" in args:
        i = args.index("--check")
        tool = args[i + 1] if i + 1 < len(args) else ""
        if tool:
            r = check_registration(tool)
            print(f"\n  {tool}: test={r['integration']}  route={r['routing']}")
        raise SystemExit(0)

    if not args_clean:
        print("  Uso: auto_register.py <tool_file.py> [--cmd cmd-name] [--desc 'descripción']")
        raise SystemExit(1)

    tool_file = args_clean[0]
    description = ""
    if "--desc" in args:
        i = args.index("--desc")
        description = args[i + 1] if i + 1 < len(args) else ""

    raise SystemExit(cmd_register(tool_file, description=description, dry_run=dry_run))
