# BAGO Master Plan — Framework Completo
## Version: 2026-05-14

### FASE 1: INFRAESTRUCTURA (en progreso)

#### 1.1 Jerarquia de fuente de verdad [HECHO]
- bago_locate.py: detecta PC vs USB vs BOTH vs NONE
- Reglas: local explícito > repo local > repo padre > global PATH > error

#### 1.2 Launcher global [HECHO]
- Instalar BAGO en PATH (Windows: %USERPROFILE%\BAGO\, Unix: ~/.local/bin/)
- BAGO.cmd / bago.sh wrappers
- Desinstalador clean

#### 1.3 Health Check completo [HECHO]
- bago_health_check.py: modelos REALMENTE disponibles
- Ollama list, Codex config.toml, Copilot gh, Ollama Cloud API key

### FASE 2: ORQUESTACION (en progreso)

#### 2.1 Router dinámico [HECHO]
- bago_dynamic_router.py: Task → Type → Agent → Role → Tools → Model
- Cruza model_routing.json + agent_tool_matrix.json

#### 2.2 Orquestador de modelos [HECHO]
- bago_orchestrator.py: selecciona modelo óptimo por coste/tarea
- Modos: offline, económico, estándar, full
- En Codex CLI: simples → Ollama gratis, complejas → Codex barato

#### 2.3 Integración launcher + orquestador [HECHO]
- BAGO launch (sin args) → orquestador interactivo
- BAGO launch [modelo] → manual override
- BAGO launch --task "descripción" → orquesta directo

### FASE 3: SINCRONIZACION [HECHO]

#### 3.1 USB ↔ PC [HECHO]
- BAGO sync --to-usb / --from-usb
- Robocopy con /MIR /XD .git
- Sincroniza knowledge + state

#### 3.2 Git sync (contribuciones) [HECHO]
- BAGO contribute: prepara informe, sube a MarcValls/BAGO
- BAGO repo init: crea repo Git del usuario
- BAGO repo sync: sube progresos

### FASE 4: INSTALACION DE MODELOS [HECHO]

#### 4.1 Descarga automática [HECHO]
- BAGO install qwen25-coder → ollama pull
- BAGO install codex → verifica/instala CLI
- BAGO install copilot → gh extension install
- BAGO install all → instala todos los locales

#### 4.2 Verificación post-install
- Check que modelo responde
- Registro en model_providers.json
- Actualización de health check

### FASE 5: TESTS [HECHO]

#### 5.1 Tests unitarios [HECHO]
- test_router.py: verifica routing por tarea
- test_orchestrator.py: verifica selección de modelo
- test_locate.py: verifica detección de fuente

#### 5.2 Tests de integración [HECHO]
- Simular entorno Codex → debe elegir Codex para complejas
- Simular offline → debe elegir Ollama local
- Simular sin modelos → debe devolver error informativo

#### 5.3 CI/CD [HECHO]
- GitHub Actions: correr tests en push
- Pre-commit hooks: validar JSON de configuración

### FASE 6: EXTENSIBILIDAD (puntos fáciles de incrustar)

#### 6.1 Nuevos proveedores (fácil)
- Añadir entrada en model_providers.json
- Añadir health check en model_orchestrator.json
- El orquestador automáticamente los incluye

#### 6.2 Nuevos agentes (fácil)
- Crear .bago/agents/NUEVO_AGENTE.md
- Añadir a agent_tool_matrix.json
- Router lo detecta automáticamente

#### 6.3 Nuevas herramientas MCP (fácil)
- Crear script en .bago/tools/
- Registrar en toolbox_catalog.json
- MCP server lo expone

#### 6.4 Nuevas reglas de routing (fácil)
- Añadir a model_routing.json
- Formato: keywords, provider, model, reason
- No requiere código

#### 6.5 Nuevas tareas del orquestador (fácil)
- Añadir a task_preference en model_orchestrator.json
- Formato: task_type, models, reason
- No requiere código

### FASE 7: FUTURO (no implementar ahora)

#### 7.1 BAGO_H.1 (modelo propio)
- Fine-tuning sobre historial de decisiones
- 1-3B parámetros, corre en CPU
- Reemplaza clasificador local

#### 7.2 GUI/Web
- Reemplazar bago_mindmap.html estático
- Usar GoJS o D3.js para mind map interactivo
- Dashboard de estado en localhost

#### 7.3 Plugins
- Sistema de plugins tipo VS Code
- marketplace.json para descubrir plugins
- Instalación: BAGO plugin install nombre

### CHECKLIST DE COHERENCIA
- [ ] Cada paso deja variables que el siguiente reutiliza
- [ ] No repetir trabajo (instalar PATH una sola vez)
- [ ] Jerarquía clara: local > repo > global
- [ ] Fallbacks en cada nivel
- [ ] Configuración pura JSON (no código) para reglas nuevas

### SIGUIENTE PASO INMEDIATO
Instalar BAGO global en PATH → deja variable que todo usa.

### FASE 7: TERMINOLOGIA [HECHO]

#### 7.1 Clarificación Agente vs Modelo
- **BAGO** = Framework de orquestación (director)
- **Agente** = Proveedor de ejecución (codex, copilot, ollama)
- **Modelo** = LLM específico (gpt-5.4, claude-sonnet, qwen2.5)
- Documentación en .bago/docs/TERMINOLOGIA.md
- Salida del orquestador actualizada: separa Agente/Modelo
- Salida del router dinámico: ya separaba Agente/Modelo
- Tests actualizados para validar consistencia

#### 7.2 Jerarquía de ejecución documentada
`
USUARIO → TAREA → BAGO (Router+Orquestador+Launcher)
                              |
                              v
                        AGENTE (codex/copilot/ollama)
                              |
                              v
                        MODELO (gpt-5.4/claude-sonnet/qwen2.5)
                              |
                              v
                        RESULTADO
`
