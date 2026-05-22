from __future__ import annotations

# Cada entrada: (nombre_grupo, [(cmd, descripción_corta, descripción_larga[, sub_opciones])])
# Sub-opciones: [(args, etiqueta_corta, descripción)]
#
# Reglas de este archivo:
#   · Sin duplicados: cada comando aparece UNA sola vez en el menú.
#   · Sin solapamiento: si dos comandos hacen lo mismo, uno es sub-opción del otro.
#   · Descriptores vivid: qué hace, cómo ayuda, sin jerga de framework.

MENU: list[tuple[str, list[tuple]]] = [

    # ══════════════════════════════════════════════════════════════
    #  ARRANQUE — Lo primero que ves al entrar
    # ══════════════════════════════════════════════════════════════
    ("🚀  Arranque", [
        ("launch",           "Inicia BAGO con la intro animada",   "Pantalla de bienvenida completa: avispa, logo, campo magnético y estado del sistema"),
        ("start",            "Panel completo de estado",           "Workspace, tarea activa, ideas priorizadas y health score de un vistazo"),
        ("status",           "Resumen rápido en 3 líneas",         "Flujo activo + tarea pendiente + health score. Para pulsar a cualquier momento"),
        ("devmode",          "Alterna modo Dev / Usuario",         "Developer: vista framework completa. User: solo lo relevante para tu proyecto"),
        ("workspace-select", "Cambia el espacio de trabajo",       "Framework (self) | directorio padre | ruta externa. Persiste en repo_context.json"),
        ("recent-projects",  "Proyectos recientes",                "Historial de repos visitados con sesiones, ideas implementadas y health score"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  MODOS — Entornos de trabajo especializados
    # ══════════════════════════════════════════════════════════════
    ("🎨  Modos", [
        ("create",           "Modo creación — 3 paneles",          "Layout tipo AI Studio: sesiones, área de trabajo y cambios/archivos/preview/issues"),
        ("focus",            "Modo enfoque minimalista",             "Muestra la tarea activa en una línea o en un panel limpio para segundo plano"),
        ("menu",             "Menú interactivo jerárquico",          "Navegación por categorías con previsualización live y sub-opciones"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  IDEAS — Del caos a la tarea
    # ══════════════════════════════════════════════════════════════
    ("💡  Ideas", [
        ("ideas",   "Backlog priorizado",               "Lista ideas ordenadas por contexto, sprint y urgencia", [
            ("",           "ver backlog",    "Top 5–20 ideas priorizadas por contexto (predeterminado)"),
            ("--select",   "--select",       "Selector interactivo con navegación y filtros"),
            ("--baseline", "--baseline",     "Solo ideas de bajo riesgo, estables y probadas"),
            ("--export",   "--export",       "Exporta snapshot del backlog a ideas_snapshot.md"),
            ("--health",   "--health",       "Estadísticas: total, por estado, por intención, por sprint"),
            ("--all",      "--all",          "Muestra ideas de todos los proyectos activos"),
        ]),
        ("cosecha", "Capturar una idea nueva",          "Registra título, contexto y prioridad en bago.db de forma estructurada"),
        ("inbox",   "Bandeja de entrada",               "Ideas sin clasificar pendientes de triaje — el lugar donde todo llega primero"),
        ("next",    "Convertir la idea top en tarea",   "Toma la idea #1 del backlog y la convierte en tarea activa del sprint"),
        ("assign",  "Asignar idea específica a tarea",  "Elige una idea concreta del backlog y ábrela como tarea activa"),
        ("promote", "Subir idea al sprint activo",      "Escala una idea al sprint con prioridad ajustada y contexto copiado"),
        ("reopen",  "Reabrir una tarea cerrada",        "Reabre una tarea done para revisión, corrección o continuación"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  TAREA ACTIVA — El ciclo de trabajo
    # ══════════════════════════════════════════════════════════════
    ("📋  Tarea activa", [
        ("task",  "Ver la tarea en curso",         "Tarea activa: idea origen, contexto, pasos pendientes y progreso"),
        ("scope", "Definir scope de la tarea",     "Declara qué archivos/módulos están en scope para esta tarea"),
        ("flow",  "Estado del flujo de trabajo",   "Grafo del workflow activo: nodos, transiciones, estado actual"),
        ("done",  "Cerrar la tarea actual",        "Registra la tarea como completada con evidencia y cierra el ciclo"),
        ("sprint","Panel del sprint",              "Sprint completo: ideas completadas, en curso, velocidad y próximas"),
        ("goals", "Objetivos cualitativos",        "Define y revisa qué quieres lograr en este sprint más allá de los tickets"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  AGENTES & IA — Los colaboradores digitales
    # ══════════════════════════════════════════════════════════════
    ("🤖  Agentes & IA", [
        ("agent",      "Panel de agentes",
         "Lanza, lista y coordina todos los agentes BAGO. Gateway central del sistema multi-agente", [
            ("list",       "listar",         "Lista todos los agentes activos con skills, fase y estado"),
            ("run",        "ejecutar",       "Lanza un agente concreto con tarea y contexto"),
            ("status",     "estado",         "Estado en vivo de los agentes en ejecución"),
            ("history",    "historial",      "Log de decisiones y outputs de sesiones de agente anteriores"),
        ]),
        ("agent_coder",     "⌨  Coder — /code",
         "Tu par programador. Implementa features, escribe módulos y refactoriza desde cero manteniéndose en contexto del repo. Shortcuts: /code /impl /write"),
        ("agent_planner",   "📐  Planner — /sprint",
         "El estratega. Descompone objetivos ambiguos en sprints concretos, prioriza el backlog y diseña el roadmap. Shortcuts: /sprint /plan"),
        ("agent_debugger",  "🔬  Debugger — /debug",
         "El detective de errores. Analiza trazas, reproduce bugs y propone el fix exacto con contexto de fichero. Shortcuts: /debug /trace"),
        ("agent_architect", "🏛  Architect — /arch",
         "El diseñador de sistemas. Modela arquitecturas, evalúa trade-offs y propone patrones para el proyecto. Shortcuts: /arch /design"),
        ("agent_refactor",  "🔧  Refactor — /refactor",
         "El cirujano del código. Elimina deuda técnica, simplifica lógica y mejora la estructura sin romper tests. Shortcuts: /refactor /clean"),
        ("agent_git",       "🌿  Git Agent — /git",
         "El gestor de cambios. Commit semántico, branch, rebase y PR con contexto de sesión y historial BAGO. Shortcuts: /git /commit /pr"),
        ("autonomous",      "🌀  Bucle autónomo",
         "BAGO decide, ejecuta y evalúa solo en ciclos controlados. Tú defines el objetivo y los límites; el sistema hace el resto"),
        ("route",           "🧭  Router de intención",
         "Di qué quieres en lenguaje natural — 'quiero ver mis ideas pendientes' — y BAGO encuentra el comando exacto"),
        ("advisor",         "🔮  Consejero estratégico",
         "Analiza el estado completo del sistema y dice cuál es el siguiente paso de mayor impacto. Tu oráculo de next steps"),
        ("neural",          "⚡  Bus inter-agente",
         "Red de mensajes SSE que conecta y sincroniza agentes en paralelo. Para flujos multi-modelo y orquestación avanzada"),
        ("toolsmith",       "🛠  Creador de tools",
         "Genera nuevas herramientas BAGO desde una descripción en lenguaje natural. Del texto a la tool registrada y testada"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  CAMPO & REACTOR — La capa cognitiva de BAGO
    # ══════════════════════════════════════════════════════════════
    ("🧠  Campo & Reactor", [
        ("field",     "Matriz de campo magnético",
         "Escanea proveedores y modelos disponibles. Muestra la matriz local/cloud/código/validación con scores de coste, privacidad y capacidad", [
            ("scan",       "escanear",       "Detecta y puntúa todos los modelos disponibles (Ollama, Codex, Copilot, cloud)"),
            ("status",     "estado",         "Estado actual del campo: qué modelos están activos y en qué polo"),
            ("calibrate",  "calibrar",       "Ejecuta test de calibración en un modelo y genera su perfil de confianza"),
            ("route",      "enrutar",        "Propone el mejor modelo/proveedor para una tarea descrita"),
        ]),
        ("boot",      "Arranque examinado",
         "Examina el proyecto al arrancar: directorio, repo, índice, modelos disponibles y frases-operador dinámicas", [
            ("examine",    "examinar",       "Análisis completo del proyecto: estructura, estado, modelos, safeguards"),
            ("phrases",    "frases",         "Muestra las frases-operador generadas para este arranque"),
            ("index",      "índice",         "Genera o actualiza el índice resumido del proyecto"),
        ]),
        ("safeguard", "Panel de salvaguardas",
         "Gestiona los 4 genes de seguridad: identity · safety_contract · kill_switch_policy · project_boundary", [
            ("status",     "estado",         "Muestra el estado ON/OFF de los 4 genes de safeguard"),
            ("explain",    "explicar",       "Explica qué protege cada gen y qué ocurre si se apaga"),
            ("set",        "configurar",     "Cambia el estado de un gen (ON / SOFT_OFF / OFF) con confirmación"),
        ]),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  CALIDAD & SALUD — El motor de integridad
    # ══════════════════════════════════════════════════════════════
    ("✅  Calidad & Salud", [
        ("health",    "Score de salud 0–100",
         "5 dimensiones: integridad, disciplina, decisiones, stale y consistencia. Tu termómetro del sistema", [
            ("",            "score global",   "Score ponderado 0–100 (predeterminado)"),
            ("report",      "informe",        "Reporte completo con todos los checks en Markdown/HTML"),
            ("stability",   "estabilidad",    "Tendencia histórica del health score con alertas de regresión"),
            ("efficiency",  "eficiencia",     "Ratio de eficiencia inter-versiones del framework"),
            ("consistency", "consistencia",   "Anti-drift: verifica coherencia entre registry, CI y README"),
            ("sincerity",   "sinceridad",     "Detecta promesas vacías y sycofancía en docs y sesiones"),
        ]),
        ("validate",  "Validación completa GO/FAIL",
         "Verifica manifest, state y pack antes de cada commit. Si falla, no hagas push", [
            ("",         "completo",     "Validación completa: manifest + state + pack (predeterminado)"),
            ("manifest", "manifest",     "Solo valida pack.json contra global_state.json"),
            ("state",    "state",        "Solo valida coherencia de global_state.json y sesiones"),
            ("contents", "pack",         "Valida un ZIP de pack distribuible"),
        ]),
        ("audit",         "Auditoría de sesión completa",  "Trail completo: roles activados, contratos, evidencias y decisiones de la sesión"),
        ("orphan-shield", "Escudo anti-huérfanos",         "Detecta 4 tipos: archivos sin registro, registry sin archivo, rutas rotas, docs desconectados", [
            ("",        "escanear",    "Escaneo completo de los 4 tipos (predeterminado)"),
            ("--fix",   "--fix",       "Repara automáticamente los huérfanos que sean seguros de eliminar"),
            ("--report","--report",    "Exporta informe de huérfanos a Markdown"),
        ]),
        ("canon",     "Bucle de Shepard BAGO",
         "4 modos × 3 voces: MODULAR · SCAN · CREATE · EVOLVE. El ciclo que nunca vuelve al mismo estado exacto"),
        ("heal",      "Reparar inconsistencias auto",      "Auto-repair de problemas detectados por health/validate. Solo actúa sobre lo seguro"),
        ("siembra",   "Semillas de mejora",                "Registra aprendizajes de la sesión como semillas para ideas futuras"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  ANÁLISIS DE CÓDIGO — La lupa del codebase
    # ══════════════════════════════════════════════════════════════
    ("🔍  Análisis de código", [
        ("code-metrics", "Métricas del código",       "Complejidad ciclomática, duplicaciones y líneas por módulo"),
        ("code-search",  "Búsqueda semántica",        "Busca en el historial de código del proyecto con contexto y relevancia"),
        ("lint-runner",  "Linter configurable",       "pyflakes / ruff / eslint según el tipo de proyecto detectado"),
        ("rubber-duck",  "Debug conversacional",      "Explica el problema en voz alta — el sistema hace las preguntas correctas"),
        ("secrets",      "Auditoría de secretos",     "Detecta API keys, passwords y tokens expuestos en el código"),
        ("deps",         "Análisis de dependencias",  "Estado de dependencias: desactualizadas, vulnerables o sin usar"),
        ("naming",       "Check de nomenclatura",     "Verifica convenciones de nombres aplicadas en el codebase"),
        ("hardcode",     "Detectar hardcoding",       "Encuentra valores hardcodeados que deberían vivir en config o variables"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  WORKSPACE & REPOS — La gestión del espacio
    # ══════════════════════════════════════════════════════════════
    ("📁  Workspace & Repos", [
        ("git",         "Contexto y estado git",     "Branch, staged, unstaged, remotes, stale. Vista git completa del workspace", [
            ("",        "resumen",      "Estado git completo con contexto BAGO (predeterminado)"),
            ("status",  "--status",     "Solo status: staged, unstaged, untracked"),
            ("log",     "--log",        "Log de commits recientes con contexto de sesión"),
            ("stale",   "--stale",      "Detecta branches abandonados y remotes obsoletos"),
        ]),
        ("project",     "Gestión del proyecto",      "Crea, vincula o consulta el estado del proyecto activo"),
        ("context",     "Detector de contexto",      "Identifica el tipo de proyecto y sugiere workflow y agentes adecuados"),
        ("map",         "Mapa del workspace",         "Vista estructural completa del workspace y sus relaciones entre repos"),
        ("repo-clone",  "Clonar repositorio",         "Clona un repo GitHub con auto-setup BAGO y configuración inicial"),
        ("repo-list",   "Listar repos del workspace", "Lista repositorios clonados con estado, health y sesiones recientes"),
        ("repo-switch", "Cambiar repo activo",        "Cambia el contexto BAGO al repositorio que elijas del workspace"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  INFORMES & MEMORIA — El conocimiento que persiste
    # ══════════════════════════════════════════════════════════════
    ("📊  Informes & Memoria", [
        ("dashboard",     "Panel visual completo",      "Dashboard interactivo: métricas, sprint, salud y actividad reciente en una pantalla"),
        ("weekly-report", "Informe semanal",            "Resumen de la semana: ideas implementadas, velocidad del sprint y evolución del health"),
        ("snapshot",      "Snapshot del estado",        "Captura y compara snapshots del sistema para detectar drift o progreso", [
            ("",        "comparar",     "Compara los dos últimos snapshots (predeterminado)"),
            ("--list",  "--list",       "Lista todos los snapshots con fecha y tamaño"),
            ("--ideas", "--ideas",      "Compara solo la sección de ideas"),
            ("--tools", "--tools",      "Compara solo la sección de herramientas"),
            ("--json",  "--json",       "Salida de comparación en JSON"),
        ]),
        ("chronicle",     "Crónica del proyecto",       "Historia narrativa: decisiones tomadas, hitos conseguidos y aprendizajes acumulados"),
        ("search-history","Búsqueda en historial",      "Busca en todo el historial de sesiones BAGO con contexto y relevancia"),
        ("docs",          "Documentación generada",     "Documentación auto-generada de todos los comandos activos — siempre sincronizada"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  CONFIGURACIÓN — Los mandos del sistema
    # ══════════════════════════════════════════════════════════════
    ("⚙️  Configuración", [
        ("backup-vault",      "Backups trifásicos",                 "Engine limpio + engine+memory + memoria fusionada. Rotación automática"),
        ("setup",             "Asistente de configuración inicial", "Wizard que configura BAGO en un sistema nuevo paso a paso"),
        ("install",           "Instalar BAGO en un repo",           "Instala la capa BAGO en un repositorio externo"),
        ("llm",               "Modelo de IA activo",                "Cambia el modelo, proveedor, temperatura y parámetros del LLM en uso"),
        ("personality-panel", "Perfil del agente",                  "Configura tono, verbosidad, idioma y estilo de respuesta del agente BAGO"),
        ("alias-manager",     "Gestión de alias",                   "Crea, edita y elimina alias personalizados para comandos frecuentes"),
        ("env-manager",       "Variables de entorno",               "Gestiona el .env del proyecto con validación, diff y sincronización"),
        ("version",           "Versión del sistema",                "Versión actual de BAGO con changelog, notas de upgrade y estado del pack"),
    ]),

    # ══════════════════════════════════════════════════════════════
    #  INFRAESTRUCTURA — Las tuberías del sistema
    # ══════════════════════════════════════════════════════════════
    ("🛠️  Infraestructura", [
        ("build-run",     "Ejecutar build",        "Lanza el pipeline de build del proyecto activo"),
        ("build-clean",   "Limpiar build",         "Elimina artefactos de build: __pycache__, dist, .eggs"),
        ("state-manager", "Gestor de estado",      "Split, materialize y merge del estado por capas — para mantenimiento avanzado"),
        ("net-scan",      "Escaneo de red",        "Descubre puertos y servicios activos en la red local"),
        ("ping-server",   "Check de servicio",     "Verifica disponibilidad y latencia de un endpoint HTTP/TCP"),
        ("seed",          "Semillas del sistema",  "Gestiona las semillas de conocimiento que alimentan el motor BAGO"),
        ("notify-bago",   "Notificación interna",  "Envía un evento al sistema de presencia BAGO para sincronización"),
    ]),
]
