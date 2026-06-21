# Piezas de Alto y Medio Interés — Inventario Cruzado BAGO

> Generado automáticamente desde el inventario de sesión.  
> Última actualización: 2026-06-21

---

## 🟢 Alto Interés (24 piezas)

| ID | Zona | Ruta | Tipo | Descripción |
|---|---|---|---|---|
| bago-user-config | .bago (user runtime) | `.bago\state\config.json` | config | Configuración activa del usuario: default_provider ollama-local, model llama3.2:3b, y providers habilitados. Es la fuente de verdad del runtime. |
| bago-user-knowledge-db | .bago (user runtime) | `.bago\state\knowledge.db` | database | Base de conocimiento SQLite viva del usuario. Contiene memorias operativas acumuladas. |
| codex-memories-summary | .codex/memories | `.codex\memories\memory_summary.md` | memory | Resumen compacto del perfil del usuario, preferencias operativas y zonas clave. Migrar a bago_fw como CONTRACTO_DE_USO. |
| codex-skill-bago-reparador | .codex/skills | `.codex\skills\bago-reparador\SKILL.md` | skill | Skill de diagnóstico/reparación de BAGO: smoke test, orquestación, fix PS1. Adoptar como skill oficial del proyecto. |
| codex-script-smoke | .codex/skills/scripts | `.codex\skills\bago-reparador\scripts\bago_smoke_diagnose.py` | script | Diagnóstico rápido de estructura, imports, Ollama y permisos. Reusable para CI y runtime health. |
| legacy-agent-definitions | Downloads/BAGOS/3.5-RC1 | `Downloads\BAGOS\BAGO-3.5-CLEAN-CORE-RC1\.bago\agents\*.md` | contracts | 9 contratos de rol estáticos (MAESTRO, ARQUITECTO, CENTINELA, COPILOT, ORGANIZADOR...). Adoptables como system-prompts de agentes. |
| legacy-agent-factory | Downloads/BAGOS/3.5-RC1 | `Downloads\BAGOS\BAGO-3.5-CLEAN-CORE-RC1\.bago\agents\agent_factory.py` | factory | Fábrica dinámica de agentes especializados bajo demanda. Persiste en state/agents/. Muy maduro. |
| legacy-pack-json-35 | Downloads/BAGOS/3.5-RC1 | `Downloads\BAGOS\BAGO-3.5-CLEAN-CORE-RC1\.bago\pack.json` | manifest | Manifiesto maduro con ~50 comandos declarativos, entrypoints, governance, workflows W0-W10, y política de evidencia. Fusionable como catálogo de referencia. |
| legacy-tools-manifest | Downloads/BAGOS/3.5-RC1 | `Downloads\BAGOS\BAGO-3.5-CLEAN-CORE-RC1\.bago\tools.manifest.json` | manifest | Catálogo declarativo de herramientas con type, reads_only, description. Esquema superior al actual. |
| v4-cli-trace-pattern | Downloads/BAGOS/Bago_v4 | `Downloads\BAGOS\Bago_v4\bago_core\cli.py` | cli | CLI con formato de traza obligatorio: assertion→action→evidence→conclusion. Adoptable para toda superficie de comandos. |
| v4-test-e2e | Downloads/BAGOS/Bago_v4 | `Downloads\BAGOS\Bago_v4\test_e2e.py` | test | Simulación completa de sesión multi-provider con switch, compress, RL feedback, save/load. Template de test suite. |
| artefactos-integrate-router | Downloads/BAGOS/artefactos | `Downloads\BAGOS\ARCHIVO_BAGO\artefactos_sueltos\integrate_router.py` | patch | Parche de referencia que inserta routing por reglas JSON y MUSIC_KEYWORDS en agent_router.py. Clave para entender cómo se extendió routing sin romper motor. |
| ft-llama32-kit | Downloads/BAGOS/bago_ft_llama32 | `Downloads\BAGOS\bago_ft_llama32` | training_kit | Kit completo de fine-tuning LoRA para llama3.2: dataset builder, Modelfile.persona, train_lora.py. Clave para modelo local identitario. |
| ft-llama32-modelfile | Downloads/BAGOS/bago_ft_llama32 | `Downloads\BAGOS\bago_ft_llama32\ollama\Modelfile.persona` | model_definition | System prompt del modelo BAGO local con reglas de no-autoentrenamiento. Reutilizar como contrato de identidad. |
| rescue-newv4-registry-autonomy | Downloads/BAGOS/new_v4 | `Downloads\BAGOS\BAGO_RESCUE_v3.4\new_v4\registry\autonomy.py` | registry | Registro de herramientas de autonomía: autonomous_loop, inbox, siembra, recientes. Semántica madura para agentes. |
| rescue-newv4-registry-menu | Downloads/BAGOS/new_v4 | `Downloads\BAGOS\BAGO_RESCUE_v3.4\new_v4\registry\menu.py` | registry | Definición declarativa de entradas de menú con preflight, agent, stability, risk. Modelo de registro superior al actual. |
| rescue-newv4-canonical-gate | Downloads/BAGOS/new_v4 | `Downloads\BAGOS\BAGO_RESCUE_v3.4\new_v4\tools\ideas\canonical_gate.py` | validator | Validador canónico (validate_pack + validate_state + smoke) con política GO/KO/WARN. Fusionar con doctor/test existentes. |
| bago-fw-dotbago-agent-start | bago_fw/.bago | `bago_fw\.bago\AGENT_START.md` | contract | Contrato de agente ya consolidado en bago_fw. Referencia canónica. |
| bago-fw-dotbago-bootstrap | bago_fw/.bago | `bago_fw\.bago\BOOTSTRAP.md` | contract | Contrato de arranque ya consolidado en bago_fw. Referencia canónica. |
| bago-fw-dotbago-system-prompt | bago_fw/.bago | `bago_fw\.bago\chat\system_prompt.py` | prompt | Prompt de sistema actual con orden de carga. Pieza crítica ya en edición. |
| bago_fw-env-cjs | bago_fw/electron | `bago_fw\electron\environment.cjs` | runtime_resolver | Resolución robusta de raíz instalada, dev y empaquetada. Lógica de hasBagoRuntime y fallback ya consolidada. Segunda pasada innecesaria salvo para documentar. |
| bago_fw-runtime-svc | bago_fw/electron | `bago_fw\electron\runtime-service.cjs` | service | Construcción del comando CLI, base-path, y openCliChat. **Observación:** openCliChat usa `developmentRoot` pero no verifica que sea el editable. |
| bago_fw-core-js | bago_fw/manager | `bago_fw\manager\js\core.js` | frontend_core | Payload local, sesiones, providers, copia de comandos y openCliChat/openWebChat. **Observación:** afinar para que openCliChat priorice bago_fw sobre instalada. |

---

## 🟡 Medio Interés (17 piezas)

| ID | Zona | Ruta | Tipo | Descripción |
|---|---|---|---|---|
| bago-user-sessions | .bago (user runtime) | `.bago\state\sessions` | sessions | ~25 sesiones históricas con JSON de metadata. Fuente de ejemplos para dataset de fine-tuning. |
| codex-memories-bago-runtime | .codex/memories | `.codex\memories\bago_runtime` | memory_tree | Proyectos de image_generation y music con sus estados y herramientas. Evaluar si el pipeline music es rescatable. |
| codex-skill-playwright | .codex/skills | `.codex\skills\playwright` | skill | Skill de automatización web. Útil para testear el manager Electron headless. |
| codex-skill-screenshot | .codex/skills | `.codex\skills\screenshot` | skill | Skill de screenshot reusable para tests visuales y evidencia de CI. |
| codex-script-sync | .codex/skills/scripts | `.codex\skills\bago-reparador\scripts\bago_sync_bidirectional.py` | script | Sync bidireccional motor+knowledge entre USB/disco/GitHub. Lógica de merge útil para releases. |
| legacy-prompt-router | Downloads/BAGOS/3.5-RC1 | `Downloads\BAGOS\BAGO-3.5-CLEAN-CORE-RC1\.bago\core\prompt_router.py` | router | Motor de adaptación de prompts según métricas de señal (banda, canales, interferencia). Experimental pero ingenioso. |
| v4-system-prompt-neutral | Downloads/BAGOS/Bago_v4 | `Downloads\BAGOS\Bago_v4\.bago\chat\system_prompt.py` | prompt | Prompt neutral sin gates artificiales. Buena referencia para reducir restricciones innecesarias. |
| v4-bago-true-bridge | Downloads/BAGOS/Bago_v4 | `Downloads\BAGOS\Bago_v4\bago_core\bago_true_bridge.py` | bridge | Detector del backend bago_true con reglas de migración bridge_only. Útil si se reactiva subsistema RL. |
| music-ableton-template | Downloads/BAGOS/MUSIC | `Downloads\BAGOS\BAGO_MUSIC_PIPELINE\ableton\ableton_template.py` | generator | Scaffolding de proyectos Ableton techno con tracks, BPM y metadatos JSON. |
| music-pipeline-router | Downloads/BAGOS/MUSIC | `Downloads\BAGOS\BAGO_MUSIC_PIPELINE\pipeline\bago_music.py` | router | Router de subcomandos musicales: plan, convert, run, transpose, render. Diseño modular con códigos de salida semánticos. |
| marc-dynperf | source-archive | `source-archive\DynPerf-CacheClean.ps1` | script | Limpieza automática de cache Windows cada 4h. Reusable como utilidad de mantenimiento del runtime BAGO. |
| artefactos-fix-scripts | Downloads/BAGOS/artefactos | `Downloads\BAGOS\ARCHIVO_BAGO\artefactos_sueltos\fix_*.py` | patches | Colección de fixes rápidos (arrow, bom, cost, model, paths...). Patrón de patch-reusable. |
| artefactos-fix-router | Downloads/BAGOS/artefactos | `Downloads\BAGOS\ARCHIVO_BAGO\artefactos_sueltos\fix_router.py` | patch | Parche alternativo con music_hits en scores y fallback force_cloud. |
| rescue-newv4-bin-ps1 | Downloads/BAGOS/new_v4 | `Downloads\BAGOS\BAGO_RESCUE_v3.4\new_v4\bin\bago.ps1` | launcher | Launcher minimalista que delega a core/launcher.py. Limpio y reutilizable como fallback. |
| rescue-newv4-cajafisica | Downloads/BAGOS/new_v4 | `Downloads\BAGOS\BAGO_RESCUE_v3.4\new_v4\registry\cajafisica_imported.py` | module | Importación/migración de caja física. Si hay lógica de hardware legacy, encapsularla como plugin. |
| rescue-backup-analyze | Downloads/BAGOS/rescue | `Downloads\BAGOS\BAGO_RESCUE_v3.4\C_BAGO_backup\BAGO\analyze_results.py` | script | Análisis de resultados de test. Lógica de parsing CSV/JSON para reportes. |
| rescue-backup-evolution | Downloads/BAGOS/rescue | `Downloads\BAGOS\BAGO_RESCUE_v3.4\C_BAGO_backup\BAGO\compare_evolution.py` | script | Comparador de evolución entre versiones. Útil para release drift. |
| rescue-backup-patch-collection | Downloads/BAGOS/rescue | `Downloads\BAGOS\BAGO_RESCUE_v3.4\C_BAGO_backup\BAGO\patch_*.py` | patches | ~15 scripts de parcheo (gate, launcher, toolreg, disk_guard, ensemble...). Patrones de fix automatizado reutilizables. |

---

## Acciones recomendadas (orden de prioridad)

1. **codex-memories-summary** → migrar a `docs/CONTRACTO_DE_USO.md`
2. **legacy-agent-definitions** → adoptar como contratos de rol en `.bago/agents/`
3. **legacy-tools-manifest** → fusionar esquema en `tool_registry.py` actual
4. **v4-cli-trace-pattern** → aplicar formato de traza a `cli.py` actual
5. **ft-llama32-modelfile** → reusar identidad como contrato de modelo local
6. **rescue-newv4-registry-menu** → comparar con registro actual y mejorar si es inferior
7. **rescue-newv4-canonical-gate** → fusionar validación con `doctor` / `test` existente
8. **legacy-agent-factory** → evaluar si se necesita generación dinámica de agentes
9. **legacy-pack-json-35** → extraer comandos/governance como referencia de catálogo
10. **bago_fw-runtime-svc / bago_fw-core-js** → corregir priorización editable vs instalada

---

*Archivo mantenido a mano en el árbol de desarrollo para consulta rápida.*
