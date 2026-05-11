# BAGO Agent Protocol v1.0

> Protocolo universal para orquestación de BAGO por agentes locales y externos.
> Versión: 1.0 · Fecha: 2026-05-11 · Estabilidad: experimental

---

## Visión

BAGO puede ser orquestado por cualquier agente de lenguaje:
- **Local**: Ollama (GGUF/llama.cpp), cualquier modelo GGUF
- **Copilot**: GitHub Copilot vía MCP tools
- **Claude**: Anthropic vía MCP server (ya implementado en bago_mcp_server.py)
- **Codex**: OpenAI Codex CLI vía subprocess
- **Cloud agents**: HTTP/WebSocket (Claw, custom, etc.)
- **Self**: BAGO `autonomous_loop.py` (bucle interno)

El protocolo garantiza:
- **Seguridad**: lista de intenciones permitidas, comandos dangerous nunca sin --dry-run
- **Trazabilidad**: cada llamada queda en el Neural Bus como evento
- **Portabilidad**: misma interfaz para todos los adapters
- **Fail-closed**: si el adapter no responde o falla, BAGO no ejecuta nada

---

## Conceptos clave

### AgentRequest
Petición normalizada que cualquier adapter puede enviar a BAGO:

```json
{
  "intent": "health_check",
  "context": {
    "cwd": "/path/to/project",
    "bago_version": "3.4.0b1",
    "active_workflow": "W2",
    "health_score": 100
  },
  "payload": {
    "tool": "health",
    "args": ["--report"]
  },
  "options": {
    "dry_run": false,
    "timeout": 30,
    "unsafe": false
  },
  "source": {
    "adapter": "ollama",
    "model": "qwen2.5-coder:7b",
    "session_id": "abc123"
  }
}
```

### AgentResult
Respuesta normalizada que BAGO devuelve a cualquier adapter:

```json
{
  "success": true,
  "intent": "health_check",
  "output": "Health: 100/100 ✅",
  "artifacts": [],
  "exit_code": 0,
  "duration_ms": 245,
  "cost_hint": "free/local",
  "adapter": "ollama",
  "timestamp": "2026-05-11T08:00:00Z",
  "neural_event_id": "evt-001"
}
```

### Adapter
Clase que implementa la interfaz `BaseAgentAdapter`:
- `name: str` — identificador único
- `capability() -> AdapterCapability` — qué puede hacer y con qué coste
- `health() -> bool` — está disponible ahora mismo
- `execute(AgentRequest) -> AgentResult` — ejecuta la petición
- `stream(AgentRequest) -> Iterator[str]` — streaming opcional

---

## Intenciones permitidas (allowlist)

Solo estas intenciones pueden ser enviadas por adapters externos:

### Read-only (siempre permitidas)
- `health_check` — `bago health`
- `scan` — `bago audit scan`
- `status` — `bago status`
- `list_tools` — listar herramientas disponibles
- `explain` — explicar qué hace un comando
- `ideas` — listar ideas pendientes
- `registry` — consultar el registry
- `context` — obtener contexto del proyecto
- `npath_query` — consultar el grafo cognitivo

### Mutating (requieren confirmación o dry_run=True en tests)
- `task_create` — crear una tarea W2
- `task_done` — cerrar tarea W2
- `cosecha` — bago session harvest
- `siembra_seed` — inicializar siembra en proyecto externo

### Dangerous (requieren unsafe=True explícito, nunca en CI)
- `autonomous_cycle` — ejecutar ciclo autónomo
- `heal` — reparar inconsistencias
- `db_migrate` — migrar bago.db

### Nunca permitidas vía adapter externo
- `db drop`, `rm -rf`, cualquier comando destructivo no reversible

---

## Seguridad del protocolo

1. **Allowlist estricta**: cualquier intent no listado → reject inmediato
2. **Dangerous requiere unsafe=True + confirmación explícita**
3. **MCP surface permanece readonly por defecto**
4. **Cada llamada se loguea en Neural Bus** (trazabilidad)
5. **Timeout obligatorio**: ninguna llamada sin timeout
6. **Rate limiting**: max 10 req/min por adapter externo
7. **Schema validation**: `agent_contract.json` valida cada request

---

## Adapters disponibles

| Adapter | Coste | Requiere | Estado |
|---------|-------|----------|--------|
| `local` | Gratis | nada | ✅ siempre disponible |
| `ollama` | Gratis/local | Ollama + modelo GGUF | ✅ implementado |
| `mcp` | API credits | Claude/servidor MCP | ✅ bago_mcp_server.py |
| `copilot` | Suscripción | gh CLI + auth | 🔧 en desarrollo |
| `codex` | API credits | codex CLI instalado | 🔧 en desarrollo |
| `cloud` | Variable | URL + API key | 🔧 en desarrollo |

---

## Flujo de orquestación

```
Agente externo / LLM local
        │
        │  AgentRequest (JSON)
        ▼
   AgentGateway.route()
        │
        ├─ validate_allowlist()  →  reject si intent no permitido
        ├─ validate_schema()     →  reject si malformado
        ├─ check_risk_policy()   →  block si dangerous sin unsafe
        │
        ▼
   AdapterRegistry.get(adapter)
        │
        ▼
   Adapter.execute(request)
        │
        ├─ emit_event(Neural Bus)
        ├─ run tool subprocess
        └─ return AgentResult
        │
        ▼
   Agente externo recibe resultado
```

---

## Integración con Neural Bus

Cada llamada al gateway emite eventos al Neural Bus:
- `agent.request` — cuando llega una petición
- `agent.result` — cuando se completa
- `agent.error` — cuando falla
- `agent.blocked` — cuando se bloquea por política

Esto permite que `bago autonomous` observe en tiempo real qué están haciendo los agentes externos y aprenda de ello.

---

## Roadmap del protocolo

- **v1.0** (actual): Gateway + adapters local/ollama/mcp
- **v1.1**: Streaming responses, WebSocket support
- **v2.0**: Autenticación por adapter, capabilities dinámicas
- **v3.0**: Federación multi-BAGO (varios BAGO cooperando)
