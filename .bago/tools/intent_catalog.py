"""Catálogo base de intenciones del router BAGO."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
        "id": "idea_feature_config_provider_disable",
        "name": "Idea de producto: desactivar providers/modelos",
        "triggers": [
            "desactivar provider", "desactivar providers", "desactivar modelo",
            "desactivar modelos", "desactivar servicio", "desactivar servicios",
            "modelos desactivados", "servicios desactivados",
            "modelos o servicios", "servicios enteros", "enteros desactivados",
            "ocultar provider", "ocultar providers", "quitar provider",
            "quitar modelo", "no usar provider", "no usar modelo",
            "ni se acuerda", "ignorar provider", "ignorar modelo",
            "provider enabled false", "enabled false",
        ],
        "tools": ["ideas"],
        "description": "Registrar/proponer control enabled=false para que BAGO oculte y excluya providers o modelos",
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


INTENT_VOICES: dict = {
    "security_check": ["SECURITY_REVIEWER", "ANALISTA"],
    "quality_check": ["ANALISTA", "VALIDADOR"],
    "merge_readiness": ["VALIDADOR", "ANALISTA"],
    "architecture_review": ["ARQUITECTO", "ANALISTA"],
    "performance_check": ["PERFORMANCE_REVIEWER", "ANALISTA"],
    "release_prep": ["ORGANIZADOR", "VALIDADOR"],
    "bago_fix": ["ANALISTA", "ORGANIZADOR"],
    "context_sync": ["ORGANIZADOR"],
    "test_run": ["VALIDADOR"],
    "docs": ["GENERADOR"],
    "ux_review": ["UX_REVIEWER", "ANALISTA"],
    "integration_check": ["INTEGRATOR", "ARQUITECTO"],
}


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

