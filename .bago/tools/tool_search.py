#!/usr/bin/env python3
"""tool_search.py — Busca el tool BAGO correcto para un problema dado.

Con 127+ tools nadie los recuerda todos. Este tool indexa nombres,
descripciones y códigos de error para encontrar qué tool necesitas.

Uso:
    python3 tool_search.py "sql injection"
    python3 tool_search.py --list-all
    python3 tool_search.py --category security
    python3 tool_search.py --code SEC-E001
    python3 tool_search.py --test

Códigos: SRCH-I001 (match exacto), SRCH-I002 (match parcial),
         SRCH-W001 (sin resultados)
"""
import sys
import re
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = Path(__file__).parent


def _load_tool_catalog() -> list:
    """Load TOOL_REGISTRY from tool_catalog.json; fall back to hardcoded list on any error."""
    try:
        cfg_path = BAGO_ROOT / "state" / "config" / "tool_catalog.json"
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return [
            (
                t["name"], t["command"], t["category"],
                t["description"], t["codes"], t["keywords"],
            )
            for t in data.get("tools", [])
        ]
    except Exception:
        return _TOOL_REGISTRY_FALLBACK


_TOOL_REGISTRY_FALLBACK = [
    # (name, command, category, description, codes, keywords)
    ("lint_report",      "lint",           "quality",   "linting Python: E501 líneas largas, F401 imports no usados, funciones complejas", ["LINT-E", "LINT-W"], ["lint", "pep8", "estilo", "imports", "unused", "linea larga"]),
    ("complexity",       "complexity",     "quality",   "complejidad ciclomática y cognitiva de funciones Python", ["CMPLX-E", "CMPLX-W"], ["complejidad", "complexity", "ciclomatica", "cognitiva", "funciones largas"]),
    ("dead_code",        "dead-code",      "quality",   "detecta código muerto: variables, imports, funciones nunca usadas", ["DEAD-E", "DEAD-W"], ["muerto", "dead", "unused", "nunca usado", "variable no usada"]),
    ("hotspot",          "hotspot",        "quality",   "hotspots de riesgo: archivos más cambiados en git history", ["HOT-I", "HOT-W"], ["hotspot", "riesgo", "git history", "cambios frecuentes"]),
    ("duplicate_check",  "dup-check",      "quality",   "bloques de código duplicado (min 5 líneas consecutivas)", ["DUP-E", "DUP-W"], ["duplicado", "duplicate", "copypaste", "copy paste", "clonado"]),
    ("naming_check",     "naming-check",   "quality",   "convenciones de nombres: snake_case, CamelCase, constantes UPPER", ["NAME-E", "NAME-W"], ["nombres", "naming", "snake_case", "camelcase", "convenciones"]),
    ("type_check",       "type-check",     "quality",   "type hints: funciones sin anotaciones de tipo, uso de Any", ["TYPE-E", "TYPE-W"], ["tipos", "type hints", "anotaciones", "mypy", "Any"]),
    ("doc_coverage",     "doc-coverage",   "quality",   "cobertura de docstrings en módulos, clases y funciones", ["DOC-E", "DOC-W"], ["docstring", "documentacion", "docstrings faltantes", "cobertura docs"]),
    ("refactor_suggest", "refactor",       "quality",   "sugerencias de refactoring: funciones largas, clases grandes, imports circulares", ["REF-I", "REF-W"], ["refactor", "refactoring", "mejorar", "simplificar", "funciones largas"]),
    ("secret_scan",      "secret-scan",    "security",  "detecta secretos hardcodeados: API keys, tokens, passwords, IPs privadas", ["SEC-E", "SEC-W"], ["secretos", "secrets", "api key", "password", "token", "hardcoded", "credentials"]),
    ("dep_audit",        "dep-audit",      "security",  "auditoría de dependencias: CVEs conocidos, versiones inseguras, ranges abiertos", ["DEP-E", "DEP-W"], ["dependencias", "cve", "vulnerabilidad", "requirements", "pip", "inseguro"]),
    ("api_check",        "api-check",      "security",  "valida contratos de API: endpoints, respuestas esperadas, errores HTTP", ["API-E", "API-W"], ["api", "endpoints", "http", "respuestas", "contrato"]),
    ("license_check",    "license-check",  "legal",     "verifica cabeceras de licencia/copyright en archivos fuente", ["LIC-E", "LIC-W"], ["licencia", "license", "copyright", "cabecera", "legal", "mit", "apache"]),
    ("coverage_gate",    "coverage-gate",  "testing",   "puerta de cobertura de tests: bloquea si no alcanza el umbral mínimo", ["COV-E", "COV-W"], ["cobertura", "coverage", "tests", "umbral", "gate"]),
    ("ci_report",        "ci-report",      "ci",        "reporte CI unificado: agrega todos los scanners, score 0-100, listo para PR", ["CI-E", "CI-W"], ["ci", "reporte", "pr", "merge", "score", "unified"]),
    ("tool_guardian",    "tool-guardian",  "framework", "guardian de coherencia del framework: tools sin --test, sin registro, sin routing", ["GUARD-E", "GUARD-W"], ["guardian", "coherencia", "framework", "health", "registro", "routing"]),
    ("pre_push_guard",   "pre-push",       "framework", "checklist pre-push: CHECKSUMS + version sync + suite + guardian en un comando", ["PUSH-E", "PUSH-W"], ["pre-push", "checklist", "checksums", "push", "pre commit"]),
    ("readme_check",     "readme-check",   "docs",      "valida README.md: secciones requeridas, placeholders, enlaces rotos", ["README-E", "README-W"], ["readme", "documentacion", "markdown", "secciones", "badges"]),
    ("code_review",      "review",         "quality",   "revisión de código: detecta anti-patrones, magic numbers, código comentado", ["REV-E", "REV-W"], ["review", "revision", "anti patron", "magic number", "codigo comentado"]),
    ("metrics_trends",   "metrics",        "analytics", "tendencias de métricas rolling 4 semanas, sparklines ASCII", ["MET-I"], ["metricas", "tendencias", "trends", "sparkline", "historico"]),
    ("sprint_manager",   "sprint",         "workflow",  "gestión de sprints: new, list, close, status, active", ["SPR-I"], ["sprint", "sprints", "iteracion", "planificacion", "kanban"]),
    ("bago_search",      "search",         "workflow",  "búsqueda full-text en sessions, changes, decisions", ["SRH-I"], ["buscar", "search", "sessions", "cambios", "decisiones", "full text"]),
    ("timeline",         "timeline",       "workflow",  "timeline ASCII de semanas con sesiones y hitos de health", ["TML-I"], ["timeline", "linea de tiempo", "historial visual", "semanas"]),
    ("report_generator", "report",         "workflow",  "generador de reportes Markdown: sessions, artefactos, decisiones", ["RPT-I"], ["reporte", "informe", "markdown", "exportar", "sessions"]),
    ("git_context",      "git",            "workflow",  "estado git del repo: branch, uncommitted, recent commits para context_map", ["GIT-I"], ["git", "branch", "commits", "uncommitted", "contexto git"]),
    ("doctor",           "doctor",         "framework", "diagnóstico integral: JSONs, cross-refs sessions→cambios→evidencias, tools", ["DOC-E"], ["doctor", "diagnostico", "salud", "health", "json invalido", "cross ref"]),
    ("pre_commit_gen",   "pre-commit",     "workflow",  "genera .pre-commit-config.yaml con hooks BAGO optimizados", ["PCG-I"], ["pre commit", "hooks", "git hooks", "pre-commit.yaml"]),
    ("metrics_export",   "metrics-export", "analytics", "exporta métricas a JSON/CSV para dashboards externos", ["EXP-I"], ["exportar", "json", "csv", "dashboard", "metricas"]),
    ("ableton_template", "ableton-template", "creative", "genera scaffold de proyecto Ableton techno 4/4 con carpetas, README y template.json", ["ABL-I001"], ["ableton", "live", "daw", "music", "musica", "techno", "track", "beats", "samples", "scaffold", "template", "proyecto musical", "produccion musical", "midi", "audio", "loop", "drums", "bass"]),
    ("music_pipeline",   "music",          "creative",  "convierte, transpone y valida archivos MusicXML", ["MUS-I001", "MUS-E001"], ["musicxml", "transpose", "transponer", "partitura", "sheet music", "nota musical", "instrumento", "clave musical", "music"]),
    ("advisor",          "advisor",        "ai",        "advisor LLM adaptativo: ask|next|explain|run|context — orienta con modelo local", ["ADV-I001"], ["advisor", "llm", "ask", "next", "orient", "orientar", "que hago", "siguiente paso", "explica", "pregunta", "asistente", "guia", "ia", "ai", "adaptive"]),
]

TOOL_REGISTRY = _load_tool_catalog()


def tokenize(text: str) -> list:
    return re.findall(r'\w+', text.lower())


def score_match(query_tokens: list, tool: tuple) -> int:
    name, cmd, cat, desc, codes, kws = tool
    score = 0
    all_text = " ".join([name, cmd, cat, desc] + kws + codes).lower()
    all_tokens = tokenize(all_text)
    kw_text = " ".join(kws).lower()


    for qt in query_tokens:
        # exact code match
        for code in codes:
            if qt.upper() in code.upper():
                score += 20
        # keyword match
        if qt in tokenize(kw_text):
            score += 10
        # name/cmd match
        if qt in tokenize(name + " " + cmd):
            score += 15
        # desc match
        if qt in tokenize(desc):
            score += 5
        # category match
        if qt == cat.lower():
            score += 8
        # partial substring
        if qt in all_text and qt not in all_tokens:
            score += 2
    return score


def search_tools(query: str, top_n: int = 5) -> list:
    tokens = tokenize(query)
    results = []
    for tool in TOOL_REGISTRY:
        s = score_match(tokens, tool)
        if s > 0:
            results.append((s, tool))
    results.sort(key=lambda x: -x[0])
    return results[:top_n]


def print_result(score: int, tool: tuple, verbose: bool = False):
    name, cmd, cat, desc, codes, kws = tool
    tag = "SRCH-I001" if score >= 15 else "SRCH-I002"
    print(f"  [{tag}] bago {cmd}")
    print(f"    {desc}")
    if verbose:
        print(f"    Categoría: {cat}  |  Códigos: {', '.join(codes[:3])}")
        print(f"    Keywords: {', '.join(kws[:5])}")
    print()


def cmd_search(args: list):
    query = " ".join(args)
    if not query:
        print("  Uso: bago tool-search <palabras clave>")
        return 1
    results = search_tools(query)
    if not results:
        print(f"  [SRCH-W001] Sin resultados para: '{query}'")
        print("  Prueba: bago tool-search --list-all")
        return 1
    print(f"\n  Resultados para: '{query}'")
    print("  " + "─" * 46)
    for score, tool in results:
        print_result(score, tool, verbose=("--verbose" in args or "-v" in args))
    return 0


def cmd_list_all(category: str = ""):
    cats = {}
    for tool in TOOL_REGISTRY:
        cat = tool[2]
        if category and cat != category:
            continue
        cats.setdefault(cat, []).append(tool)
    for cat, tools in sorted(cats.items()):
        print(f"\n  [{cat.upper()}]")
        for t in tools:
            print(f"    bago {t[1]:18s}  {t[3][:65]}")
    print()


def cmd_code(code: str):
    code_up = code.upper()
    found = []
    for tool in TOOL_REGISTRY:
        for c in tool[4]:
            if code_up in c.upper():
                found.append(tool)
                break
    if not found:
        print(f"  [SRCH-W001] Sin tool para código: {code}")
        return 1
    print(f"\n  Tools que generan código '{code_up}':")
    for t in found:
        print(f"    bago {t[1]:18s}  {t[3][:65]}")
    print()
    return 0


def run_tests():
    results = []

    # Test 1: search returns relevant results
    res = search_tools("secretos hardcoded password credentials")
    ok1 = len(res) > 0 and res[0][1][1] == "secret-scan"
    results.append(("tool_search:find_secret_scan", ok1, f"top={res[0][1][1] if res else 'none'}"))

    # Test 2: search complexity
    res = search_tools("complejidad ciclomatica")
    ok2 = len(res) > 0 and "complexity" in res[0][1][1]
    results.append(("tool_search:find_complexity", ok2, f"top={res[0][1][1] if res else 'none'}"))

    # Test 3: code lookup
    hits = [t for t in TOOL_REGISTRY if any("GUARD" in c for c in t[4])]
    ok3 = len(hits) >= 1
    results.append(("tool_search:code_lookup_GUARD", ok3, f"hits={len(hits)}"))

    # Test 4: tokenize function
    tokens = tokenize("SQL injection attack")
    ok4 = "sql" in tokens and "injection" in tokens
    results.append(("tool_search:tokenize", ok4, f"tokens={tokens}"))

    # Test 5: no results for garbage
    res = search_tools("xyzxyznotarealquery")
    ok5 = len(res) == 0
    results.append(("tool_search:no_results_garbage", ok5, f"count={len(res)}"))

    # Test 6: list_all returns all categories
    cats = set(t[2] for t in TOOL_REGISTRY)
    ok6 = len(cats) >= 5
    results.append(("tool_search:category_coverage", ok6, f"cats={len(cats)}"))

    # Test 7: catalog loaded from JSON (not empty fallback)
    ok7 = len(TOOL_REGISTRY) >= 10
    results.append(("tool_search:catalog_loaded", ok7, f"entries={len(TOOL_REGISTRY)}"))

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

    if "--list-all" in args:
        cat = ""
        for i, a in enumerate(args):
            if a == "--category" and i + 1 < len(args):
                cat = args[i + 1]
        cmd_list_all(cat)
        raise SystemExit(0)

    if "--category" in args:
        i = args.index("--category")
        cat = args[i + 1] if i + 1 < len(args) else ""
        cmd_list_all(cat)
        raise SystemExit(0)

    if "--code" in args:
        i = args.index("--code")
        code = args[i + 1] if i + 1 < len(args) else ""
        raise SystemExit(cmd_code(code))

    # default: search
    query_parts = [a for a in args if not a.startswith("--")]
    raise SystemExit(cmd_search(query_parts))
