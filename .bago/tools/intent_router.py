#!/usr/bin/env python3
"""intent_router.py — Interpreta lenguaje natural y ejecuta los tools BAGO correctos.

La utopía de BAGO: el usuario describe su problema en su propio lenguaje
y el framework entiende, elige los tools correctos y los ejecuta.

Sin necesidad de conocer 130+ comandos. Sin documentación necesaria.

Uso:
    python3 intent_router.py "mi código tiene passwords hardcodeados"
    python3 intent_router.py "quiero saber si puedo hacer merge"
    python3 intent_router.py "el proyecto tiene funciones muy largas y complejas"
    python3 intent_router.py "prepara el código para producción"
    python3 intent_router.py "algo va mal con el framework BAGO"
    python3 intent_router.py --dry-run "secretos en el código"
    python3 intent_router.py --list-intents
    python3 intent_router.py --test

Códigos: INT-I001 (intención clara), INT-I002 (intención parcial),
         INT-W001 (sin match), INT-E001 (tool falló)
"""
import sys
import re
import subprocess
from functools import lru_cache
from pathlib import Path

BAGO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_SCRIPT = PROJECT_ROOT / "bago"


# ─────────────────────────────────────────────────────────────────────────────
# INTENT DEFINITIONS
# Cada intención tiene: nombre, patrones de activación, tools a ejecutar (en orden),
# mensaje explicativo, y si es destructivo (requiere confirmación)
# ─────────────────────────────────────────────────────────────────────────────
INTENTS = [
    {
        "id": "security_check",
        "name": "Auditoría de seguridad",
        "triggers": [
            "secret", "secreto", "password", "passwd", "contraseña", "token",
            "api key", "hardcode", "hardcoded", "credencial", "credentials",
            "seguridad", "security", "vulnerable", "vulnerabilidad", "cve",
            "inject", "inyección", "xss", "sql injection",
        ],
        "tools": ["secret-scan", "dep-audit"],
        "description": "Escanea secretos hardcodeados y dependencias vulnerables",
        "destructive": False,
    },
    {
        "id": "quality_check",
        "name": "Calidad de código",
        "triggers": [
            "calidad", "quality", "lint", "estilo", "style", "pep8",
            "imports", "import", "unused", "no usad", "línea larga", "linea larga",
            "legibilidad", "limpio", "clean",
        ],
        "tools": ["lint", "naming-check", "doc-coverage"],
        "description": "Analiza calidad: estilo, naming y documentación",
        "destructive": False,
    },
    {
        "id": "complexity_check",
        "name": "Complejidad y refactoring",
        "triggers": [
            "complej", "complex", "largo", "large", "grande", "refactor",
            "función larga", "funcion larga", "demasiado", "too long",
            "cognitiv", "ciclomát", "ciclomatico", "cyclomatic",
            "difícil de leer", "dificil de leer", "difícil de entender",
        ],
        "tools": ["complexity", "refactor"],
        "description": "Detecta complejidad alta y sugiere refactoring",
        "destructive": False,
    },
    {
        "id": "dead_code",
        "name": "Código muerto",
        "triggers": [
            "muerto", "dead", "dead code", "no usado", "no se usa", "unused",
            "variable no usada", "función no llamada", "import sin usar",
            "eliminar", "limpiar código", "clean up",
        ],
        "tools": ["dead-code", "duplicate-check"],
        "description": "Detecta código muerto y bloques duplicados",
        "destructive": False,
    },
    {
        "id": "pre_merge",
        "name": "Preparar para merge/PR",
        "triggers": [
            "merge", "pull request", "commit", "push", "producción",
            "produccion", "production", "release", "listo", "ready",
            "puedo mergear", "puedo hacer merge", "puedo commitear",
            "está listo", "esta listo", "deploy",
        ],
        "tools": ["commit-ready", "ci-report"],
        "description": "Evalúa si el código está listo para merge/producción",
        "destructive": False,
    },
    {
        "id": "types_check",
        "name": "Type hints y anotaciones",
        "triggers": [
            "tipo", "type", "type hint", "anotacion", "anotación",
            "mypy", "tipado", "sin tipo", "untyped", "any",
        ],
        "tools": ["type-check"],
        "description": "Verifica anotaciones de tipo en funciones y métodos",
        "destructive": False,
    },
    {
        "id": "deps_check",
        "name": "Dependencias y librerías",
        "triggers": [
            "dependencia", "dependency", "requirements", "pip", "package",
            "paquete", "librería", "libreria", "version", "versión",
            "actualizar", "upgrade", "obsoleto", "deprecated",
        ],
        "tools": ["dep-audit"],
        "description": "Audita dependencias en requirements.txt / pyproject.toml",
        "destructive": False,
    },
    {
        "id": "docs_check",
        "name": "Documentación",
        "triggers": [
            "documentaci", "docstring", "readme", "doc", "docs",
            "sin documentar", "sin docs", "falta documentación",
            "badge", "enlace roto", "broken link",
        ],
        "tools": ["doc-coverage", "readme-check"],
        "description": "Verifica docstrings y README",
        "destructive": False,
    },
    {
        "id": "framework_health",
        "name": "Salud del framework BAGO",
        "triggers": [
            "bago", "framework", "tool guardian", "guardian", "salud",
            "health", "coherencia", "coherente", "integrado",
            "sin test", "sin routing", "sin registro", "registro",
            "herramienta", "herramientas",
        ],
        "tools": ["tool-guardian"],
        "description": "Valida coherencia interna del framework BAGO",
        "destructive": False,
    },
    {
        "id": "full_audit",
        "name": "Auditoría completa",
        "triggers": [
            "todo", "completo", "full", "audit", "auditoría", "auditoria",
            "reporte completo", "full report", "todo el proyecto",
            "análisis completo", "analisis completo", "revisar todo",
        ],
        "tools": ["ci-report"],
        "description": "Reporte CI completo: 10 scanners, score 0-100",
        "destructive": False,
    },
    {
        "id": "self_heal",
        "name": "Auto-reparación del framework",
        "triggers": [
            "reparar", "repair", "arreglar", "fix", "corregir",
            "auto", "automático", "automatico", "self", "heal",
            "integrar tool", "registrar tool", "añadir test",
        ],
        "tools": ["tool-guardian", "auto-register"],
        "description": "Detecta y auto-repara problemas del framework",
        "destructive": True,
    },
    {
        "id": "hotspot_analysis",
        "name": "Archivos de alto riesgo",
        "triggers": [
            "hotspot", "riesgo", "risk", "cambio frecuente", "más cambiado",
            "inestable", "unstable", "git history", "historial",
        ],
        "tools": ["hotspot"],
        "description": "Identifica archivos más cambiados = mayor riesgo",
        "destructive": False,
    },
    {
        "id": "ableton_project",
        "name": "Proyecto Ableton / Producción musical",
        "triggers": [
            "ableton", "live", "proyecto musical", "proyecto de música",
            "producción musical", "produccion musical", "music production",
            "techno", "track", "beats", "drums", "bass", "samples",
            "scaffold musical", "plantilla ableton", "template ableton",
            "daw", "midi", "audio", "loop", "arrangement", "pista",
            "quiero hacer música", "quiero hacer musica",
        ],
        "tools": ["ableton-template"],
        "description": "Genera scaffold de proyecto Ableton techno (carpetas, README, template.json)",
        "destructive": False,
    },
    {
        "id": "music_pipeline",
        "name": "Pipeline musical (MusicXML / transposición)",
        "triggers": [
            "musicxml", "transpos", "transponer", "transpose", "nota musical",
            "partitura", "sheet music", "score", "clef", "clave musical",
            "instrumento", "instrument", "convert music", "convertir música",
        ],
        "tools": ["music"],
        "description": "Convierte, transpone y valida archivos MusicXML",
        "destructive": False,
    },
]


@lru_cache(maxsize=1)
def _load_intents() -> list:
    try:
        from bago_config import load_config
        data = load_config("intents_catalog", fallback=None)
        if data and isinstance(data.get("intents"), list):
            return data["intents"]
    except Exception:
        pass
    return INTENTS


# ── CAP voice-role mapping ─────────────────────────────────────────────────
# Mapa de intención → roles sugeridos por ShepardCycle.
# El Orquestador selecciona voces complementarias, nunca solapadas, máx 3.
_INTENT_VOICES: dict = {
    "security_check":        ["SECURITY_REVIEWER", "ANALISTA"],
    "quality_check":         ["ANALISTA", "VALIDADOR"],
    "merge_readiness":       ["VALIDADOR", "ANALISTA"],
    "architecture_review":   ["ARQUITECTO", "ANALISTA"],
    "performance_check":     ["PERFORMANCE_REVIEWER", "ANALISTA"],
    "release_prep":          ["ORGANIZADOR", "VALIDADOR"],
    "bago_fix":              ["ANALISTA", "ORGANIZADOR"],
    "context_sync":          ["ORGANIZADOR"],
    "test_run":              ["VALIDADOR"],
    "docs":                  ["GENERADOR"],
    "ux_review":             ["UX_REVIEWER", "ANALISTA"],
    "integration_check":     ["INTEGRATOR", "ARQUITECTO"],
}


def _cap_activate_voices(intent_id: str, task_desc: str, dry_run: bool = False) -> None:
    """
    ShepardCycle: activa las voces (roles) CAP apropiadas para la intención.
    Llamada silenciosamente al enrutar — no interrumpe el flujo principal.
    """
    voices = _INTENT_VOICES.get(intent_id, [])
    if not voices:
        return
    try:
        import importlib.util
        vc_path = Path(__file__).parent / "voice_conductor.py"
        if not vc_path.exists():
            return
        spec = importlib.util.spec_from_file_location("voice_conductor", str(vc_path))
        mod  = importlib.util.module_from_spec(spec)          # type: ignore
        spec.loader.exec_module(mod)                           # type: ignore

        cycle = mod.VoiceConductor()
        activated = cycle.activate_voices(
            task=task_desc,
            available_roles=voices,
        )
        if activated and not dry_run:
            gate_state = cycle._state.get("gate", "PUERTA_CERRADA")
            print(f"\n  🎼 CAP·ShepardCycle → {' + '.join(activated)}"
                  + f"  [{gate_state}]")
    except Exception:
        # CAP activation is non-critical — never crash intent routing
        pass


def tokenize(text: str) -> list:
    return re.findall(r'\w+', text.lower())


def score_intent(query: str, intent: dict) -> int:
    query_lower = query.lower()
    tokens = tokenize(query_lower)
    score = 0
    for trigger in intent["triggers"]:
        # Exact substring match (highest weight)
        if trigger in query_lower:
            score += 20
        # Token match — trigger debe tener al menos 5 chars para evitar false positives
        elif len(trigger) >= 6 and any(tok.startswith(trigger[:5]) for tok in tokens if len(trigger) >= 5):
            score += 10
        # Partial token match — solo si trigger es suficientemente específico
        elif len(trigger) >= 7 and any(trigger[:6] in tok for tok in tokens):
            score += 5
    return score


def identify_intents(query: str, top_n: int = 3) -> list:
    """Retorna lista de (score, intent) ordenada por score."""
    scored = []
    for intent in _load_intents():
        s = score_intent(query, intent)
        if s > 0:
            scored.append((s, intent))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


def run_tool(cmd: str, extra_args: list = None, dry_run: bool = False) -> tuple:
    """Ejecuta un tool BAGO via el script bago. Retorna (returncode, output)."""
    if dry_run:
        return (0, f"[DRY-RUN] bago {cmd}")
    try:
        full_cmd = [str(BAGO_SCRIPT), cmd] + (extra_args or [])
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=60
        )
        out = result.stdout + result.stderr
        return (result.returncode, out)
    except subprocess.TimeoutExpired:
        return (1, f"[INT-E001] Timeout en: bago {cmd}")
    except Exception as e:
        return (1, f"[INT-E001] Error ejecutando bago {cmd}: {e}")


def execute_intent(intent: dict, dry_run: bool = False, confirm_destructive: bool = True) -> int:
    """Ejecuta todos los tools de una intención. Retorna exit code."""
    if intent.get("destructive") and confirm_destructive and not dry_run:
        print(f"\n  ⚠️  Esta acción es destructiva: {intent['description']}")
        print("  Ejecuta con --yes para confirmar, o --dry-run para previsualizar.")
        return 1

    errors = 0
    for tool_cmd in intent["tools"]:
        print(f"\n  ▶ bago {tool_cmd}")
        print("  " + "─" * 50)
        rc, output = run_tool(tool_cmd, dry_run=dry_run)
        if output.strip():
            for line in output.strip().splitlines():
                print(f"  {line}")
        if rc != 0 and not dry_run:
            print(f"\n  [INT-E001] bago {tool_cmd} salió con código {rc}")
            errors += 1
    return errors


def cmd_route(query: str, dry_run: bool = False, yes: bool = False, verbose: bool = False):
    """Ruta principal: analiza la query y ejecuta los tools."""
    intents = identify_intents(query)

    if not intents:
        print(f"\n  [INT-W001] No identifiqué una intención clara en: '{query}'")
        print("  Prueba: bago intent --list-intents")
        print("  O describe el problema con más detalle.")
        return 1

    score, best = intents[0]
    confidence = "INT-I001" if score >= 20 else "INT-I002"

    print(f"\n  [{confidence}] Intención identificada: {best['name']}")
    print(f"  {best['description']}")
    print(f"  Tools a ejecutar: {' → '.join(best['tools'])}")

    if len(intents) > 1 and verbose:
        print("\n  Alternativas:")
        for s, intent in intents[1:]:
            print(f"    • {intent['name']} (score={s})")

    # ── CAP: ShepardCycle activa voces según intención ───────────────────────
    _cap_activate_voices(best.get("id", ""), query, dry_run=dry_run)

    execute_intent(best, dry_run=dry_run, confirm_destructive=not yes)
    return 0


def cmd_list_intents():
    intents = _load_intents()
    print(f"\n  BAGO — Intenciones reconocidas ({len(intents)})")
    print("  " + "─" * 56)
    for intent in intents:
        tools_str = " + ".join(intent["tools"])
        destructive = " ⚠️ " if intent.get("destructive") else "    "
        print(f"  {destructive}{intent['name']:30s}  [{tools_str}]")
        # Show sample triggers
        sample = ", ".join(intent["triggers"][:4])
        print(f"       Palabras clave: {sample}…")
        print()


def run_tests():
    results = []
    loaded_intents = _load_intents()

    # Test 1: identify_intents — secretos → security
    intents = identify_intents("mi código tiene passwords hardcodeados")
    ok1 = len(intents) > 0 and intents[0][1]["id"] == "security_check"
    results.append(("intent_router:security_intent", ok1,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    # Test 2: merge/PR intent
    intents = identify_intents("quiero hacer merge y push a producción")
    ok2 = len(intents) > 0 and intents[0][1]["id"] == "pre_merge"
    results.append(("intent_router:merge_intent", ok2,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    # Test 3: complexity intent
    intents = identify_intents("las funciones son muy largas y complejas")
    ok3 = len(intents) > 0 and intents[0][1]["id"] == "complexity_check"
    results.append(("intent_router:complexity_intent", ok3,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    # Test 4: no match for garbage
    intents = identify_intents("xyz123 nada relevante aquí")
    ok4 = len(intents) == 0
    results.append(("intent_router:no_match", ok4, f"count={len(intents)}"))

    # Test 5: score_intent returns int
    s = score_intent("secretos y passwords", loaded_intents[0])
    ok5 = isinstance(s, int) and s > 0
    results.append(("intent_router:score_positive", ok5, f"score={s}"))

    # Test 6: all intents have required fields
    required = {"id", "name", "triggers", "tools", "description"}
    ok6 = all(required.issubset(intent.keys()) for intent in loaded_intents)
    results.append(("intent_router:intents_schema_valid", ok6,
                     f"intents={len(loaded_intents)}"))

    # Test 7: Ableton/music intent
    intents = identify_intents("quiero hacer un proyecto en ableton")
    ok7 = len(intents) > 0 and intents[0][1]["id"] == "ableton_project"
    results.append(("intent_router:ableton_intent", ok7,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

    # Test 8: "pr" trigger no longer pollutes proyecto queries
    intents = identify_intents("nuevo proyecto python sin PR aún")
    ok8 = len(intents) == 0 or intents[0][1]["id"] != "pre_merge"
    results.append(("intent_router:pr_no_false_positive", ok8,
                     f"top={intents[0][1]['id'] if intents else 'none'}"))

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

    if "--list-intents" in args:
        cmd_list_intents()
        raise SystemExit(0)

    dry_run = "--dry-run" in args
    yes = "--yes" in args
    verbose = "--verbose" in args or "-v" in args

    # Query = all non-flag args joined
    query_parts = [a for a in args if not a.startswith("--")]
    if not query_parts:
        print("  Describe el problema: bago intent 'mi código tiene secretos'")
        raise SystemExit(1)

    query = " ".join(query_parts)
    raise SystemExit(cmd_route(query, dry_run=dry_run, yes=yes, verbose=verbose))
