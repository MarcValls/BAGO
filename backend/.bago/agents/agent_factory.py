#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_factory.py — FÁBRICA DE AGENTES BAGO

Sistema que CREA dinámicamente agentes especializados bajo demanda.

Si solicitás: "detecta bugs de seguridad"
  1. Factory verifica si existe agente
  2. Si NO existe → LO CREA automáticamente
  3. Lo guarda en .bago/state/agents/  ← DINÁMICO, nunca en .bago/agents/
  4. Lo ejecuta
  5. Próximas veces: reutiliza existente

Separación motor / dinámica:
  .bago/agents/        ← MOTOR ESTÁTICO (este archivo es parte del motor)
  .bago/state/agents/  ← SALIDA DINÁMICA (aquí van los agentes generados)

BAGO = Gestor de especialistas bajo demanda
Factory = Generador de especialistas
Agents = Especialistas persistentes
"""

from pathlib import Path
import json
import sys
import importlib.util
from datetime import datetime, timezone

_HERE      = Path(__file__).resolve().parent
_BAGO      = _HERE.parent

STATIC_AGENTS_DIR  = _BAGO / "agents"
DYNAMIC_AGENTS_DIR = _BAGO / "state" / "agents"
DYNAMIC_MANIFEST   = DYNAMIC_AGENTS_DIR / "manifest.json"


def _ensure_dynamic_dir() -> None:
    DYNAMIC_AGENTS_DIR.mkdir(parents=True, exist_ok=True)


def dynamic_path(name: str) -> Path:
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"agent_factory: nombre inválido {name!r}")
    _ensure_dynamic_dir()
    return DYNAMIC_AGENTS_DIR / f"{name}.py"


def _empty_manifest() -> dict:
    return {"schema": 1, "agents": []}


def dynamic_manifest() -> dict:
    return load_manifest()


def load_manifest() -> dict:
    if not DYNAMIC_MANIFEST.exists():
        return _empty_manifest()
    try:
        return json.loads(DYNAMIC_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {**_empty_manifest(), "_warning": "manifest_unreadable"}


def save_manifest(manifest: dict) -> None:
    _ensure_dynamic_dir()
    DYNAMIC_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def audit() -> dict:
    static_roles = 0
    contaminated: list[str] = []
    if STATIC_AGENTS_DIR.exists():
        for md in STATIC_AGENTS_DIR.glob("*.md"):
            static_roles += 1
        whitelist = {
            "agent_factory.py",
            "agent_gateway.py",
            "duplication_finder.py",
            "logic_checker.py",
            "security_analyzer.py",
            "smell_detector.py",
        }
        for py in STATIC_AGENTS_DIR.glob("*.py"):
            if py.name in whitelist:
                continue
            if any(py.stem.endswith(suf) for suf in ("_checker", "_finder", "_detector", "_analyzer")):
                contaminated.append(py.name)
    dynamic_count = sum(1 for _ in DYNAMIC_AGENTS_DIR.glob("*.py")) if DYNAMIC_AGENTS_DIR.exists() else 0
    return {"static_roles": static_roles, "dynamic_count": dynamic_count, "contaminated": contaminated}


# ── Guard inline (reemplazo de agent_static_guard.py) ──────────────────────
guard = type("Guard", (), {
    "dynamic_manifest": staticmethod(dynamic_manifest),
    "load_manifest": staticmethod(load_manifest),
    "save_manifest": staticmethod(save_manifest),
    "dynamic_path": staticmethod(dynamic_path),
    "audit": staticmethod(audit),
})()

# Rutas: motor siempre estático, outputs siempre dinámicos
AGENTS_DIR      = _BAGO / "agents"                  # motor (solo lectura)
AGENTS_MANIFEST = guard.dynamic_manifest()          # dinámico

# Template universal para generar agentes
AGENT_TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{name}.py — Agente BAGO generado por Factory

Categoría: {category}
Descripción: {description}

Reglas: {rules_count}
{rules_list}

Generado: {created_at}
"""

from pathlib import Path
import ast
import re
import json
import sys

# Reglas configuradas al generar el agente
RULES: list[str] = {rules_python_list}
CATEGORY: str = "{category}"


class {class_name}(ast.NodeVisitor):
    """Agente especializado: {name}."""

    def __init__(self, filename: str):
        self.filename = filename
        self.findings: list[dict] = []

    # ── AST visitors ────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Detecta funciones según reglas de la categoría."""
        self._check_function(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Raise(self, node: ast.Raise) -> None:
        """Detecta raises desnudos (sin mensaje)."""
        if "bare_raise" in RULES or CATEGORY in ("quality", "logic"):
            if node.exc is None:
                self._add(node.lineno, "bare raise without exception object", "MEDIUM")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Detecta except genéricos."""
        if "bare_except" in RULES or CATEGORY in ("quality", "security"):
            if node.type is None:
                self._add(node.lineno, "bare except: catches all exceptions silently", "HIGH")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detecta llamadas peligrosas según categoría."""
        if CATEGORY == "security":
            dangerous = {{"eval", "exec", "compile", "__import__"}}
            if isinstance(node.func, ast.Name) and node.func.id in dangerous:
                self._add(node.lineno, f"dangerous call: {{node.func.id}}()", "CRITICAL")
        self.generic_visit(node)

    # ── Checks de texto ──────────────────────────────────────────────────────

    def check_source(self, source: str) -> None:
        """Checks basados en texto plano (complementa el AST)."""
        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Reglas por keyword
            for rule in RULES:
                if rule.startswith("pattern:"):
                    pat = rule[len("pattern:"):]
                    if re.search(pat, stripped):
                        self._add(i, f"pattern match [{{pat}}]: {{stripped[:60]}}", "MEDIUM")
                elif rule == "no_print" and re.match(r"^print\\s*\\(", stripped):
                    self._add(i, "print() in production code", "LOW")
                elif rule == "no_hardcoded_secrets":
                    if re.search(r"(password|secret|api_key|token)\\s*=\\s*[\\x27\\x22].+", stripped, re.I):
                        self._add(i, f"hardcoded secret at line {{i}}", "CRITICAL")
                elif rule == "long_functions":
                    pass  # handled via AST FunctionDef line count
                elif rule == "no_global":
                    if re.match(r"^global\\s+\\w", stripped):
                        self._add(i, f"global variable declaration: {{stripped[:40]}}", "MEDIUM")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _check_function(self, node: ast.FunctionDef) -> None:
        if "long_functions" in RULES or CATEGORY == "performance":
            end = getattr(node, "end_lineno", node.lineno)
            length = end - node.lineno
            if length > 50:
                self._add(node.lineno, f"function {{node.name!r}} is {{length}} lines (> 50)", "MEDIUM")
        if "no_args_limit" not in RULES and CATEGORY in ("quality", "design"):
            if len(node.args.args) > 7:
                self._add(node.lineno, f"function {{node.name!r}} has {{len(node.args.args)}} args (> 7)", "MEDIUM")

    def _add(self, line: int, msg: str, severity: str = "LOW") -> None:
        self.findings.append({{"line": line, "message": msg, "severity": severity}})


def analyze_file(filepath: str) -> list[dict]:
    """Analiza un archivo Python con AST + checks de texto."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except SyntaxError:
        return [{{"line": 1, "message": "SyntaxError: file could not be parsed", "severity": "HIGH", "file": filepath}}]
    except Exception as e:
        return [{{"line": 0, "message": str(e), "severity": "LOW", "file": filepath}}]

    analyzer = {class_name}(filepath)
    analyzer.visit(tree)
    analyzer.check_source(source)

    for finding in analyzer.findings:
        finding["file"] = filepath
    return analyzer.findings


def main(target_dir: str) -> int:
    """Análisis del directorio."""
    findings: list[dict] = []

    for py_file in Path(target_dir).rglob("*.py"):
        if any(d in py_file.parts for d in {{"__pycache__", ".git", ".bago"}}):
            continue
        findings.extend(analyze_file(str(py_file)))

    print(json.dumps({{
        "agent": "{name}",
        "category": "{category}",
        "rules": RULES,
        "findings": findings,
        "count": len(findings),
    }}, indent=2))

    return 1 if any(f.get("severity") in ("CRITICAL", "HIGH") for f in findings) else 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    raise SystemExit(main(target))
'''


def load_manifest() -> dict:
    """Carga manifest de agentes (dinámico)."""
    return guard.load_manifest()


def save_manifest(manifest: dict):
    """Guarda manifest (en state/agents/, nunca en agents/)."""
    guard.save_manifest(manifest)


def agent_exists(name: str) -> bool:
    """Verifica si agente dinámico existe en state/agents/."""
    return guard.dynamic_path(name).exists()


def create_agent(name: str, category: str, description: str, rules: list[str]) -> bool:
    """
    CREA agente dinámicamente.

    Args:
        name: Agent name (snake_case)
        category: Categoría (security, logic, performance, etc)
        description: Descripción
        rules: Lista de reglas

    Returns:
        True si exitoso, False si error
    """
    # Valida parámetros
    if not name or not name.replace('_', '').isalnum():
        print(f"❌ Agent name inválido: {name}", file=sys.stderr)
        return False

    if agent_exists(name):
        print(f"⚠️  Agente ya existe: {name}", file=sys.stderr)
        return False

    # Genera clase name en CamelCase
    class_name = ''.join(word.capitalize() for word in name.split('_'))

    # Genera rules list formateada (docstring y Python literal)
    rules_list = '\n'.join(f"  - {rule}" for rule in rules)
    rules_python_list = repr(rules)

    # Genera código
    code = AGENT_TEMPLATE.format(
        name=name,
        category=category,
        description=description,
        class_name=class_name,
        rules_count=len(rules),
        rules_list=rules_list,
        rules_python_list=rules_python_list,
        created_at=datetime.now(timezone.utc).isoformat()
    )

    # Guarda archivo en directorio DINÁMICO (nunca en el motor estático)
    agent_path = guard.dynamic_path(name)
    try:
        agent_path.write_text(code, encoding="utf-8")
        agent_path.chmod(0o755)
        print(f"✅ Agente creado: {name}  →  {agent_path}")
    except Exception as e:
        print(f"❌ Error creando agente: {e}", file=sys.stderr)
        return False

    # Registra en manifest
    manifest = load_manifest()
    manifest["agents"][name] = {
        "category": category,
        "description": description,
        "rules": len(rules),
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    save_manifest(manifest)

    print(f"📝 Registrado en manifest: {name}")
    return True


def list_agents() -> None:
    """Lista agentes disponibles."""
    manifest = load_manifest()
    agents = manifest.get("agents", {})

    if not agents:
        print("No agents available")
        return

    print(f"\n{'Agent':<25} {'Category':<15} {'Rules':<10} {'Status':<10}")
    print("─" * 60)

    for name, info in sorted(agents.items()):
        category = info.get("category", "?")
        rules = info.get("rules", 0)
        status = info.get("status", "?")
        print(f"{name:<25} {category:<15} {rules:<10} {status:<10}")

    print()


def get_or_create_agent(name: str, category: str, description: str, rules: list[str]) -> bool:
    """
    Obtiene agente existente O lo crea si no existe.

    Patrón clave de BAGO: adaptarse bajo demanda.
    """
    if agent_exists(name):
        print(f"✓ Usando agente existente: {name}")
        return True

    print(f"⚠️  Agente no existe: {name}")
    print(f"🔧 Generando especialista bajo demanda...")

    return create_agent(name, category, description, rules)


def main():
    """CLI de factory."""
    if len(sys.argv) < 2:
        print("agent_factory.py — Generador dinámico de agentes BAGO")
        print("\nUso:")
        print("  python agent_factory.py create <name> <category> <description> <rule1> <rule2> ...")
        print("  python agent_factory.py list")
        print("  python agent_factory.py exists <name>")
        print("\nEjemplo:")
        print('  python agent_factory.py create perf_checker performance "Check performance issues" "long_functions" "unused_vars"')
        return

    cmd = sys.argv[1]

    if cmd == "create":
        if len(sys.argv) < 5:
            print("❌ Sintaxis: create <name> <category> <description> <rule1> [<rule2> ...]")
            return

        name = sys.argv[2]
        category = sys.argv[3]
        description = sys.argv[4]
        rules = sys.argv[5:] if len(sys.argv) > 5 else []

        create_agent(name, category, description, rules)

    elif cmd == "list":
        list_agents()

    elif cmd == "exists":
        if len(sys.argv) < 3:
            print("❌ Sintaxis: exists <name>")
            return

        name = sys.argv[2]
        if agent_exists(name):
            print(f"✅ Existe: {name}")
        else:
            print(f"❌ No existe: {name}")

    else:
        print(f"Comando desconocido: {cmd}")


if __name__ == "__main__":
    main()
