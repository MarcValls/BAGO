#!/usr/bin/env python3
"""
generate_bago_dashboard.py
Genera bago_dashboard_data.json escaneando el repo BAGO actual.
Uso:
    python generate_bago_dashboard.py
    python generate_bago_dashboard.py --output REPO_ROOT/.bago/dashboard_data.json
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / ".bago" / "dashboard_data.json"


def get_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version ="):
                return line.split("=")[1].strip().strip('"')
    return "3.5.0"


def count_py_tools() -> int:
    tools_dir = REPO_ROOT / ".bago" / "tools"
    if not tools_dir.exists():
        return 0
    return len([
        p for p in tools_dir.rglob("*.py")
        if not p.name.startswith("__")
    ])


def list_music_pipeline_scripts() -> list:
    pipe = REPO_ROOT / "projects" / "music" / "pipeline"
    if not pipe.exists():
        return []
    scripts = []
    for p in sorted(pipe.glob("*.py")):
        scripts.append({
            "name": p.name,
            "desc": describe_music_script(p.name),
            "endpoint": music_endpoint(p.name),
            "deps": music_deps(p.name),
        })
    return scripts


def describe_music_script(name: str) -> str:
    return {
        "music_to_musicxml_pipeline.py": "Convierte PDF/MIDI/MSCZ → MusicXML (OMR)",
        "music_transpose_plan.py": "Crea plan auditable de transposición",
        "musicxml_render.py": "Renderiza MusicXML → PNG/SVG/PDF",
        "musicxml_target_select.py": "Inventario de partes, voces, staves, compases",
        "musicxml_transpose.py": "Transponer MusicXML por intervalo o semitonos",
        "musicxml_validate.py": "Valida transposición (original vs resultado)",
        "bago_music.py": "CLI router: plan, convert, run, inventory, transpose, validate, render",
    }.get(name, "Script de pipeline musical")


def music_endpoint(name: str) -> str:
    return {
        "music_to_musicxml_pipeline.py": "POST /api/music/omr",
        "musicxml_render.py": "POST /api/music/render",
        "musicxml_target_select.py": "POST /api/music/inventory",
        "musicxml_transpose.py": "POST /api/music/transpose",
        "musicxml_validate.py": "POST /api/music/validate",
        "bago_music.py": "CLI directo (no endpoint)",
        "music_transpose_plan.py": "CLI",
    }.get(name, "CLI")


def music_deps(name: str) -> str:
    return {
        "music_to_musicxml_pipeline.py": "Audiveris (OMR), opcional",
        "musicxml_render.py": "MuseScore 4 o Verovio (opcional)",
        "bago_music.py": "Ninguna",
        "music_transpose_plan.py": "Ninguna",
    }.get(name, "Ninguna")


def scan_tool_categories() -> list:
    tools_dir = REPO_ROOT / ".bago" / "tools"
    cats = []
    mapping = {
        "Diagnóstico": {
            "icon": "🔍",
            "prefixes": ["audit", "health", "doctor", "stale", "tool_guardian", "stability", "context"],
        },
        "Calidad de Código": {
            "icon": "✅",
            "prefixes": ["sincerity", "lint", "quality", "naming", "type", "dead", "complexity", "duplicate"],
        },
        "Generativo": {
            "icon": "💡",
            "prefixes": ["cosecha", "emit_ideas", "ideas", "ci_generator", "auto_register"],
        },
        "Reporting": {
            "icon": "📊",
            "prefixes": ["dashboard", "report", "chronicle", "efficiency"],
        },
        "Git / CI": {
            "icon": "🔀",
            "prefixes": ["git", "commit", "pre_commit", "branch"],
        },
        "Workflows": {
            "icon": "⚡",
            "prefixes": ["workflow", "intent", "flow", "cabinet"],
        },
        "Sesiones": {
            "icon": "🕐",
            "prefixes": ["session", "search_history"],
        },
        "Seguridad": {
            "icon": "🔒",
            "prefixes": ["security", "secret", "permission", "security_analyzer"],
        },
        "Imagen / Visual": {
            "icon": "🖼",
            "prefixes": ["image", "sprite", "neural_toolbox"],
        },
        "Entorno": {
            "icon": "🌍",
            "prefixes": ["env", "deps", "dep_audit", "machine"],
        },
        "Validación / Contratos": {
            "icon": "📝",
            "prefixes": ["validate", "contracts", "registry_ast"],
        },
    }

    all_files = sorted([p for p in tools_dir.rglob("*.py") if not p.name.startswith("__")])
    used = set()

    for title, cfg in mapping.items():
        items = []
        for p in all_files:
            stem = p.stem
            if any(stem.startswith(pref) or pref in stem for pref in cfg["prefixes"]):
                if stem not in used:
                    used.add(stem)
                    items.append({
                        "name": p.name,
                        "desc": guess_desc(stem),
                        "star": stem in ("cosecha", "emit_ideas", "session_preflight", "cabinet_orchestrator", "sincerity_detector"),
                        "warn": stem.startswith("validate_"),
                    })
        if items:
            cats.append({"icon": cfg["icon"], "title": title, "items": items[:10]})
    return cats


def guess_desc(stem: str) -> str:
    return {
        "audit_v2": "Auditoría integral del pack",
        "health_score": "Score salud 0-100 + breakdown",
        "doctor": "Diagnóstico + autofix seguro",
        "stale_detector": "Detecta archivos obsoletos",
        "tool_guardian": "Verifica --test, routing, docstring",
        "stability_summary": "Resumen de estabilidad",
        "context_detector": "Detecta contexto del repo activo",
        "context_map": "Mapa de contexto del repo",
        "sincerity_detector": "Anti-sycophancy + trampa semántica",
        "lint_runner": "Runner unificado de linters",
        "code_quality_orchestrator": "Orquesta análisis de calidad",
        "naming_check": "Lint de convenciones de nombres",
        "type_check": "Chequeo de tipos estáticos",
        "dead_code": "Detecta código muerto",
        "complexity": "Complejidad ciclomática",
        "duplicate_check": "Detecta código duplicado",
        "cosecha": "Síntesis de aprendizajes de sesión",
        "emit_ideas": "Generación de ideas para el proyecto",
        "ideas_selector": "Selección y priorización de ideas",
        "ci_generator": "Genera pipelines CI/CD",
        "auto_register": "Registra nuevos tools en el pack",
        "pack_dashboard": "Dashboard visual del pack",
        "health_report": "Health report completo en Markdown",
        "chronicle_reporter": "Reporte cronológico de actividad",
        "efficiency_meter": "Métricas de eficiencia de sesión",
        "git_context": "Contexto git (log/diff/brief)",
        "commit_readiness": "GO/WARN/FAIL checklist pre-commit",
        "pre_commit_gen": "Genera hooks pre-commit",
        "branch_check": "Estado y naming de branches",
        "workflow_selector": "Selector interactivo de workflow",
        "intent_router": "Lenguaje natural → tools BAGO",
        "flow": "Lista workflows disponibles",
        "cabinet_orchestrator": "Orquesta el gabinete multi-agente",
        "session_preflight": "Preflight ESCENARIO-001 antes de W7",
        "session_logger": "Registro automático de sesión",
        "session_opener": "Abre y configura nueva sesión",
        "search_history": "Búsqueda en historial de sesiones",
        "security_audit": "Auditoría de seguridad del código",
        "secret_scan": "Detecta secrets/credentials",
        "permission_check": "Verifica permisos de archivos",
        "security_analyzer": "Analizador de seguridad (agents/)",
        "image_gen": "Generación local PNG/QR/banner/chart/timeline",
        "sprite_studio": "Generador de sprites vía HF/Codex",
        "neural_toolbox": "Toolbox para modelos neuronales",
        "env_manager": "Gestión de variables de entorno",
        "deps_check": "Verifica dependencias instaladas",
        "env_setup": "Setup inicial de entorno",
        "dep_audit": "Auditoría de dependencias",
        "machine_registry": "Registro de máquinas BAGO",
        "validate_manifest": "Valida tools.manifest.json",
        "validate_pack": "Integridad completa del pack",
        "contracts": "Contratos BAGO ACTIVE/EXPIRED",
        "registry_ast_contract": "Contrato AST del registry",
    }.get(stem, "Tool BAGO")


def build_data() -> dict:
    version = get_version()
    total_tools = count_py_tools()
    music_scripts = list_music_pipeline_scripts()
    tool_cats = scan_tool_categories()

    data = {
        "meta": {
            "version": version,
            "schema_version": 2,
            "generated": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
            "repo": "MarcValls/BAGO",
            "install_root": str(REPO_ROOT),
            "user_state": r"C:\ProgramData\BAGO\user",
        },
        "stats": {
            "agents_canonical": 9,
            "roles_architectural": 4,
            "cli_commands": 154,
            "mcp_tools": 15,
            "music_pipeline_scripts": len(music_scripts),
            "total_py_tools": total_tools,
        },
        "families": [
            {
                "id": "gobierno",
                "icon": "🏛",
                "name": "Familia GOBIERNO — Coordinación Central",
                "agents": [
                    {
                        "name": "MAESTRO_BAGO", "role": f"Gobierno · v{version[:3]}-conductor",
                        "status": "activo", "status_badge": "b-purple",
                        "desc": "Líder visible. Único punto de contacto con el usuario. Recibe petición, decide delegación, entrega resultado final integrado. Orquesta agentes, mantiene coherencia de sesión y decide qué agente ejecuta cada tarea.",
                        "mcp": ["bago_status","bago_flow","bago_cabinet","bago_route","bago_health","bago_matrix"],
                        "cli": ["status","flow","cabinet","route","health"],
                    },
                    {
                        "name": "ORQUESTADOR_CENTRAL", "role": f"Gobierno · v{version[:3]}-conductor",
                        "status": "activo", "status_badge": "b-purple",
                        "desc": "Director interno. Clasifica tarea, selecciona voces activas, enforcea máximo 3 agentes simultáneos (PUERTA_CERRADA), señaliza PUERTA_ABIERTA al completar el ciclo.",
                        "note": "Routing interno entre familias. No interactúa con el usuario directamente. Controlado por tools/voice_conductor.py",
                    },
                ],
            },
            {
                "id": "produccion",
                "icon": "⚙️",
                "name": "Familia PRODUCCIÓN — Operaciones",
                "agents": [
                    {
                        "name": "ANALISTA_Contexto", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-blue",
                        "desc": "Analista de código de BAGO. Revisa calidad, detecta deuda técnica, propone mejoras concretas y prioriza por impacto. Directo y preciso, nunca genérico.",
                        "mcp": ["bago_review","bago_audit","bago_scope","bago_health","bago_context","bago_matrix"],
                        "cli": ["code-quality","context","debt","deps","detector","diff","efficiency","find-tool","habit","insights","lsp","map","naming","research","review","risk","scan","scope","stability","types","why"],
                    },
                    {
                        "name": "ARQUITECTO_Soluciones", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-blue",
                        "desc": "Arquitecto de BAGO. Diseña estructura de sistemas, propone patrones de routing entre agentes y modelos, garantiza arquitectura evolutiva sin deuda acumulada. También gestiona el pipeline musical.",
                        "mcp": ["bago_route","bago_context","bago_scope","bago_status","bago_flow","bago_matrix"],
                        "cli": ["auto","cabinet","flow","hub","llm","next","orchestrate","peer","project-init","project-link","repo-clone","route","scope","lsp"],
                    },
                    {
                        "name": "GENERADOR_Contenido", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-blue",
                        "desc": "Generador de contenido de BAGO. Produce documentación técnica, READMEs, comentarios de código y assets textuales. El contenido que genera es preciso, conciso y orientado al desarrollador.",
                        "mcp": ["bago_context","bago_status","bago_why","bago_registry","bago_validate","bago_matrix"],
                        "cli": ["banner","chronicle","cosecha","image-studio","image_gen","report","sprite-studio","context","why","docs"],
                    },
                    {
                        "name": "ORGANIZADOR_Entregables", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-blue",
                        "desc": "Organizador de entregables de BAGO. Hace seguimiento de sprints, cierra tareas completadas y mantiene el backlog limpio. Prioriza cierre sobre apertura de nuevas tareas.",
                        "mcp": ["bago_flow","bago_status","bago_health","bago_ideas"],
                        "cli": ["ask","dashboard","db","done","git","goals","ideas","learn","project","sprint","status","sync","task","workflow","session","session_close","flow"],
                    },
                    {
                        "name": "INICIADOR_MAESTRO", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-blue",
                        "desc": "Iniciador de BAGO. Al comienzo de cada sesión presenta el contexto, las ideas pendientes y propone la tarea más valiosa. Reduce la fricción de arranque al mínimo.",
                        "mcp": ["bago_ideas","bago_db","bago_status","bago_flow","bago_health","bago_matrix"],
                        "cli": ["ideas","next","start","db status","hello"],
                    },
                    {
                        "name": "ADAPTADOR_PROYECTO", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-blue",
                        "desc": "Adaptador de proyecto de BAGO. Cuando se cambia de workspace, lee el contexto local, vincula el proyecto al estado BAGO y asegura que todos los agentes tengan el contexto correcto.",
                        "mcp": ["bago_validate","bago_context","bago_scope","bago_health","bago_db","bago_matrix"],
                        "cli": ["validate","context","scope","project"],
                    },
                ],
            },
            {
                "id": "supervision",
                "icon": "🛡",
                "name": "Familia SUPERVISIÓN — Calidad e Integridad",
                "agents": [
                    {
                        "name": "CENTINELA_SINCERIDAD", "role": f"Supervisión · v{version[:3]}",
                        "status": "activo", "status_badge": "b-green",
                        "desc": "Centinela de seguridad de BAGO. Detecta secretos expuestos, evalúa riesgos y genera auditorías de seguridad. Nunca minimiza un riesgo real. Es el agente más exigente del sistema. También es anti-sycophancy.",
                        "mcp": ["bago_secrets","bago_risk","bago_audit","bago_review","bago_health","bago_validate"],
                        "cli": ["commit","pre-push","sincerity","secrets","risk","audit scan"],
                    },
                    {
                        "name": "AUDITOR_CANÓNICO", "role": f"Supervisión · v{version[:3]}",
                        "status": "activo", "status_badge": "b-green",
                        "desc": "Auditor del canon BAGO. Verifica que el sistema sigue las reglas canónicas del framework. Detecta desviaciones del contrato de rol, estructura inválida y referencias rotas.",
                        "cli": ["rules"],
                    },
                    {
                        "name": "VÉRTICE", "role": f"Supervisión · v{version[:3]}",
                        "status": "activo", "status_badge": "b-green",
                        "desc": "Guía de activación de vértices y flujos no lineales. Activa flujos no lineales, explica el 'por qué' de decisiones de routing y ayuda al sistema a navegar situaciones ambiguas.",
                        "mcp": ["bago_flow","bago_route","bago_why","bago_status","bago_matrix"],
                        "cli": ["hello","install","start","flow","route","why"],
                    },
                    {
                        "name": "VALIDADOR", "role": f"Producción · v{version[:3]}",
                        "status": "activo", "status_badge": "b-green",
                        "desc": "Valida integridad del pack, manifests, estado global y contratos BAGO. Reads-only por contrato. Única familia con permiso de auditoría profunda del sistema.",
                        "cli": ["audit","check","config-check","consistency","doctor","heal","health","stale","validate"],
                    },
                ],
            },
            {
                "id": "especialistas",
                "icon": "🔬",
                "name": "Familia ESPECIALISTAS — Dominio Específico",
                "agents": [
                    {"name":"security_reviewer","role":f"Especialista · v{version[:3]}","status":"activo","status_badge":"b-green","desc":"Revisor de seguridad especializado. Auditoría de código, detección de CVEs y secrets hardcodeados.","cli":["secrets"]},
                    {"name":"performance_reviewer","role":f"Especialista · v{version[:3]}","status":"pendiente","status_badge":"b-gray","desc":"Revisor de rendimiento. Análisis de bottlenecks, métricas de eficiencia, stress testing.","note":"tools: pendiente"},
                    {"name":"ux_reviewer","role":f"Especialista · v{version[:3]}","status":"pendiente","status_badge":"b-gray","desc":"Revisor de UX. Evaluación de interfaces, accesibilidad y experiencia de usuario en apps y TUI.","note":"tools: pendiente"},
                    {"name":"integrator","role":f"Especialista · v{version[:3]}","status":"pendiente","status_badge":"b-gray","desc":"Integrador de repositorios externos. Clona, analiza y vincula repos al contexto BAGO activo.","note":"tools: pendiente"},
                    {"name":"performance_checker","role":"Custom · pending","status":"pendiente","status_badge":"b-amber","desc":"Validación de rendimiento. Generado vía agent_factory."},
                    {"name":"test_sec","role":"Custom · active","status":"activo","status_badge":"b-green","desc":"Agente custom de seguridad test. Activo en state/agents/manifest.json."},
                ],
            },
        ],
        "spiral_agents": [
            {"name":"agent_tools","phase":"fase 0","status":"activo","status_badge":"b-amber","desc":"Agente de herramientas y revisión de código. Primera fase del ciclo espiral.","tags":[{"type":"cat","text":"categoría: tools"},{"type":"model","text":"claude-sonnet-4.6"},{"type":"cli","text":"skill: code_review"}]},
            {"name":"agent_tests","phase":"fase 4","status":"activo","status_badge":"b-amber","desc":"Agente de ejecución y validación de tests. Cuarta fase del ciclo espiral.","tags":[{"type":"cat","text":"categoría: tests"},{"type":"model","text":"claude-haiku-4.5"},{"type":"cli","text":"skill: test_runner"}]},
            {"name":"agent_docs","phase":"fase 8","status":"activo","status_badge":"b-amber","desc":"Agente de documentación y generación de contenido. Octava fase del ciclo espiral.","tags":[{"type":"cat","text":"categoría: docs"},{"type":"model","text":"claude-sonnet-4.6"},{"type":"cli","text":"skill: doc_writer"}]},
            {"name":"agent_ops","phase":"fase 2 (adicional)","status":"activo","status_badge":"b-amber","desc":"Agente de operaciones con cobertura cruzada. Puede actuar tanto en revisión de código como en documentación.","tags":[{"type":"cat","text":"categoría: ops"},{"type":"model","text":"claude-opus-4.7"},{"type":"cli","text":"skill: code_review"},{"type":"cli","text":"skill: doc_writer"}]},
        ],
        "mcp_tools": [
            {"name":"bago_status","cmd":"bago status","layer":"ejecución","agents":["MAESTRO_BAGO","INICIADOR_MAESTRO","ORGANIZADOR"]},
            {"name":"bago_health","cmd":"bago health","layer":"salud","agents":["MAESTRO_BAGO","ANALISTA","CENTINELA"]},
            {"name":"bago_validate","cmd":"bago validate","layer":"calidad","agents":["ADAPTADOR","CENTINELA"]},
            {"name":"bago_context","cmd":"bago context","layer":"analítica","agents":["ARQUITECTO","ADAPTADOR","GENERADOR"]},
            {"name":"bago_secrets","cmd":"bago secrets","layer":"calidad","agents":["CENTINELA exclusivo"]},
            {"name":"bago_review","cmd":"bago review","layer":"calidad","agents":["ANALISTA exclusivo"]},
            {"name":"bago_risk","cmd":"bago risk","layer":"analítica","agents":["CENTINELA exclusivo"]},
            {"name":"bago_why","cmd":"bago why","layer":"analítica","agents":["GENERADOR","GUIA_VERTICE"]},
            {"name":"bago_scope","cmd":"bago scope","layer":"analítica","agents":["ARQUITECTO","ANALISTA","ADAPTADOR"]},
            {"name":"bago_audit","cmd":"bago audit","layer":"calidad","agents":["ANALISTA","CENTINELA","MAESTRO"]},
            {"name":"bago_ideas","cmd":"bago ideas","layer":"ejecución","agents":["INICIADOR","ORGANIZADOR"]},
            {"name":"bago_flow","cmd":"bago flow","layer":"ejecución","agents":["MAESTRO","ARQUITECTO","GUIA","ORGANIZADOR"]},
            {"name":"bago_route","cmd":"bago route","layer":"avanzado","agents":["ARQUITECTO","MAESTRO"]},
            {"name":"bago_db","cmd":"bago db","layer":"persistencia","agents":["ORGANIZADOR","INICIADOR"]},
            {"name":"bago_cabinet","cmd":"bago cabinet","layer":"orquestación","agents":["MAESTRO exclusivo"]},
        ],
        "tool_categories": tool_cats,
        "music_pipeline": {
            "commands": ["plan","convert","run","inventory","transpose","validate","render"],
            "scripts": music_scripts,
            "synths": [
                {"name":"karpovich_synth.py","desc":"Síntesis: TR-909, LinnDrum, Fender Jazz Bass, Juno-60, synth lead","endpoint":"CLI directo (WAV)","deps":"numpy, scipy, soundfile"},
                {"name":"disc_superstar_synth.py","desc":"Síntesis French disco house (Disc Superstar)","endpoint":"CLI directo (WAV)","deps":"numpy, scipy, soundfile"},
            ],
            "extras": [
                {"name":"Inline aubio/FFT","desc":"Detección de pitch desde audio (tararear)","endpoint":"Browser mic","deps":"aubio (opcional)"},
                {"name":"Tone.js playback","desc":"Reproducción MIDI en navegador","endpoint":"Browser","deps":"Tone.js incluido"},
                {"name":"VexFlow render","desc":"Renderizado SVG de partituras en cliente","endpoint":"Browser","deps":"VexFlow incluido"},
            ],
            "ui": {
                "name": "bago_matrix_music_editor.html v4.0",
                "desc": "VexFlow + Tone.js · Estado: empty→loaded→selected→result→recording · Pipeline mode detectado automáticamente vía GET /api/status",
                "features": ["Selector de partes (inventory)","Transponer por parte/selección","Exportar SVG (browser)","Exportar MusicXML","Importar PDF/MIDI via OMR","Tararear notas (Ears)","Reproducción MIDI (Tone.js)"],
            },
        },
        "work_matrix": [
            {"label":"Código","agent":"ANALISTA_Contexto","desc":"Escribir funciones, módulos, tests o refactorizar código existente"},
            {"label":"Calidad","agent":"ANALISTA_Contexto","desc":"Linting, code review, chequeo de calidad automático"},
            {"label":"Seguridad","agent":"CENTINELA_SINCERIDAD","desc":"Secrets, vulnerabilidades, matriz de riesgo"},
            {"label":"Arquitectura","agent":"ARQUITECTO_Soluciones","desc":"Decisiones de diseño, routing entre agentes/LLMs"},
            {"label":"Contenido / Docs","agent":"GENERADOR_Contenido","desc":"Generar o actualizar docs, READMEs, comentarios"},
            {"label":"Sesión (inicio/cierre)","agent":"INICIADOR_MAESTRO","desc":"Abrir/cerrar sesión BAGO, elegir tarea inicial"},
            {"label":"Planificación","agent":"INICIADOR_MAESTRO","desc":"Seleccionar ideas, gestionar sprints, objetivos"},
            {"label":"Debug / Diagnóstico","agent":"MAESTRO_BAGO","desc":"Problemas del framework, reparar estado, health check"},
            {"label":"Estado / Base de datos","agent":"ORGANIZADOR_Entregables","desc":"bago.db, historial, ideas y guardian"},
            {"label":"Pipeline Musical","agent":"ARQUITECTO_Soluciones","desc":"Transposición, conversión, validación de partituras"},
            {"label":"Visual / Imágenes","agent":"GENERADOR_Contenido","desc":"Sprites, imágenes, assets para proyectos"},
            {"label":"Investigación","agent":"ANALISTA_Contexto","desc":"Análisis de patterns, chronicle de sesiones"},
            {"label":"Coordinación multi-agente","agent":"MAESTRO_BAGO","desc":"Orquestar agentes en paralelo, routing"},
            {"label":"Adaptación al proyecto","agent":"ADAPTADOR_PROYECTO","desc":"Cambio de workspace, vincular contexto, validar"},
        ],
    }
    return data


def main():
    parser = argparse.ArgumentParser(description="Genera bago_dashboard_data.json desde el repo")
    parser.add_argument("--output", default=str(DEFAULT_OUT), help="Ruta del JSON de salida")
    args = parser.parse_args()

    data = build_data()
    out = Path(args.output)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    import sys; sys.stdout.reconfigure(encoding="utf-8"); print(f"OK Dashboard data generado: {out}")
    print(f"   Versión: {data['meta']['version']} | Tools: {data['stats']['total_py_tools']} | Music scripts: {data['stats']['music_pipeline_scripts']}")


if __name__ == "__main__":
    main()



