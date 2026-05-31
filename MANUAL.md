# BAGO 4.1.5 â€” Manual de Usuario

> **Session-First AI Chat**  
> El contexto de sesiÃ³n sobrevive al cambio de provider.  
> El modelo es un motor temporal; la sesiÃ³n es la fuente de verdad.

---

## 1. InstalaciÃ³n y Primer Arranque

### Requisitos
- Python 3.10+
- Ollama (opcional, para provider local)
- API keys (opcionales, para providers cloud)

### Arranque

```bash
# Windows (CMD)
C:\Bago_v4> python bago_core\cli.py chat

# Windows (PowerShell)
PS C:\Bago_v4> python bago_core\cli.py chat

# Unix
$ ./bago.sh chat
```

### Banner de inicio

```
  ____    _    ____   ___  
 | __ )  / \  / ___| / _ \ 
 |  _ \ / _ \ \___ \| | | |
 | |_) / ___ \ ___) | |_| |
 |____/_/   \_\____/ \___/ 
           v4.0 â€” Session-First AI Chat

Bienvenido a BAGO 4.1.5. Escribe /help para ver comandos.
El contexto de sesiÃ³n sobrevive al cambio de provider.

â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â— ollama-local/llama3.2:3b Â· 0 tok
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
bago â¯
```

> **Nota:** Si el modelo por defecto no estÃ¡ disponible en Ollama local, BAGO 4.1.5 **auto-ajusta** al primer modelo disponible automÃ¡ticamente y te avisa.

### Runtime hÃ­brido `cpp-local` (fase 1)

BAGO puede exponer un runtime local C++ como provider `cpp-local`, manteniendo en Python la sesiÃ³n, memoria, REPL, contratos y tools.

ConfiguraciÃ³n mÃ­nima:

```bash
python bago_core\cli.py config set providers.cpp-local.enabled true
python bago_core\cli.py config set providers.cpp-local.base_url http://127.0.0.1:8765
python bago_core\cli.py config set providers.cpp-local.default_model bago-cpp:default
```

Host de referencia para desarrollo o validaciÃ³n local:

```bash
python bago_core\cli.py cpp-runtime --port 8765
```

Uso:

```bash
python bago_core\cli.py --provider cpp-local --model bago-cpp:default chat
```

Contrato inicial del runtime:

- `GET /health`
- `GET /models`
- `POST /chat`
- `POST /chat_stream`
- `POST /embed`

La especificaciÃ³n del protocolo estÃ¡ en `docs\contracts\cpp_local_runtime_protocol.md`.

Tool-calling y memoria hÃ­brida:

```bash
python bago_core\cli.py config set features.tool_calling true
```

En el chat:

- `/tools enable` activa tool-calling para providers que lo soporten
- `/memory hybrid-add <contenido>` guarda conocimiento + embedding acelerado
- `/memory hybrid-search <consulta>` busca por similitud vectorial

### SelecciÃ³n interactiva al inicio

Si el modelo por defecto no estÃ¡ disponible, o siempre que arranques el REPL, BAGO 4.1.5 te ofrece elegir provider y modelo de forma interactiva:

```
Provider actual: ollama-local/llama3.2:3b
Presiona Enter para continuar, o escribe 'cambiar' para elegir otro: cambiar

Providers configurados:
  1 ollama-local (5 modelos)
  2 openrouter (150+ modelos)
  0 Cancelar
Elige: 1

Modelos disponibles en ollama-local:
  1 llama3.2:3b
  2 mistral:7b
  ...
Elige: 2
âœ“ Conectado a ollama-local/mistral:7b
```

### Motor de Intenciones (Auto-Training)

BAGO 4.1.5 incluye un **motor de intenciones** que aprende automÃ¡ticamente de tu estilo de conversaciÃ³n para decidir cuÃ¡ndo usar herramientas y cuÃ¡ndo no.

Intenciones detectadas:
- **chat** â€” saludos, conversaciÃ³n casual. BAGO **no ofrece herramientas** al modelo.
- **review** â€” "mira", "revisa", "reune". BAGO ofrece herramientas de lectura/listado.
- **execute** â€” "ejecuta", "corre", "lanza". BAGO ofrece herramientas de ejecuciÃ³n.
- **work** â€” "trabaja", "modulariza", "adapta", "crea". BAGO ofrece herramientas de modificaciÃ³n.

Regenerar el dataset manualmente:
```bash
/retrain_intents
```

BAGO tambiÃ©n reentrena **automÃ¡ticamente** justo antes de cada compactaciÃ³n de contexto, asegurando que siempre aprenda de tus Ãºltimas interacciones.

---

## 2. Comandos del REPL

| Comando | DescripciÃ³n |
|---------|-------------|
| `/help` | Muestra esta ayuda |
| `/menu` | Abre un menÃº guiado con las funciones actuales |
| `/status` | Estado de la sesiÃ³n activa |
| `/session` | Detalles de la sesiÃ³n |
| `/models [provider]` | Lista modelos disponibles (del provider activo o especificado) |
| `/providers` | Lista providers registrados con estado de configuraciÃ³n |
| `/switch <provider> [modelo] [--force]` | Cambia de provider/modelo |
| `/save` | Guarda sesiÃ³n en disco |
| `/load <session_id>` | Carga sesiÃ³n desde disco |
| `/feedback <rating>` | Feedback explÃ­cito del usuario (-1.0 a 1.0) |
| `/suggest` | Sugerencia RL del mejor provider/modelo |
| `/good [Ã­ndice]` | Marca mensaje como importante (no diluible) |
| `/config [list\|get\|set\|reset]` | Gestiona configuraciÃ³n del sistema |
| `/credentials [list\|set\|delete]` | Gestiona credenciales de providers |
| `/tools [list\|enable\|disable]` | Gestiona herramientas del modelo |
| `/allow` | Aprueba ejecuciÃ³n de herramientas pendientes |
| `/deny` | Rechaza ejecuciÃ³n de herramientas pendientes |
| `/plan <tarea>` | Genera un plan paso a paso |
| `/autopilot <tarea>` | Ejecuta tarea autÃ³nomamente paso a paso |
| `/agents` | Lista agentes especializados |
| `/agent <nombre>` | Activa un agente especializado |
| `/memory [list\|search\|add\|delete]` | Gestiona base de conocimiento persistente |
| `/quit` | Salir del chat |

### Servidor API (`bago serve`)

BAGO 4.1.5 expone una API HTTP para integraciones externas:

```bash
C:\Bago_v4> python bago_core\cli.py serve --port 8080 --token secret123
[API] Servidor iniciado en http://0.0.0.0:8080
[API] Token requerido: secr***
```

Endpoints:
- `GET /status` â†’ Estado de la sesiÃ³n
- `GET /session` â†’ SesiÃ³n activa, provider/modelo y modo de catÃ¡logo
- `GET /history` â†’ Historial persistido de la sesiÃ³n activa
- `POST /chat` â†’ `{message: "hola"}` â†’ Respuesta del modelo
- `POST /command` â†’ `{command: "/status"}` â†’ Ejecuta el mismo backend de slash commands del REPL y devuelve `message` + `data/plan` cuando aplica
- `GET /providers` â†’ Lista providers disponibles
- `GET /models/<provider>` â†’ Lista modelos del provider
- `POST /switch` â†’ `{provider: "...", model: "...", force: false}`
- `GET /catalog/status` y `POST /catalog/config` â†’ Modo `all` o `available-only`
- `GET /simulation/status`, `GET /simulation/events` y `POST /simulation/config` â†’ Estado y trazas del shadow loop

Cabeceras Ãºtiles:

- `X-Bago-Token` â†’ token si la API estÃ¡ protegida
- `X-Bago-Channel` â†’ canal lÃ³gico de origen (`terminal`, `desktop`, `api`)

### UI React dual

La carpeta `ui-react\` contiene una capa visual React con dos superficies:

- **Terminal**: estilo shell/chat
- **Escritorio**: panel visual con el mismo control

Las dos usan la misma sesiÃ³n backend y el mismo bus de control HTTP, asÃ­ que cambiar de vista no cambia de autoridad ni rompe el contexto.

Arranque local:

```bash
# Terminal 1
python bago_core\cli.py serve --port 8080

# Terminal 2
cd ui-react
npm install
npm run dev
```

Arranque integrado con bundle compilado:

```bash
python bago_core\cli.py serve --port 8080
```

Si `ui-react\dist` existe, `serve` la expone automÃ¡ticamente. TambiÃ©n puedes forzar otra ruta:

```bash
python bago_core\cli.py serve --port 8080 --ui-dist C:\ruta\dist
```

Build:

```bash
cd ui-react
npm run build
```

SimulaciÃ³n segura (`shadow`):

- registra acciones reales sin tomar control autÃ³nomo;
- guarda estado en `.bago\state\ui_control_shadow.json`;
- guarda eventos en `.bago\logs\ui_control_shadow.jsonl`;
- expone `authority = observer-only` para dejar claro que no hay override autÃ³nomo;
- conserva `canary` y `full` como puertas futuras, pero hoy siguen siendo observaciÃ³n segura como `shadow`.

### Generador de evidencias (`bago evidence`)

BAGO 4.1.5 puede materializar un bundle de evidencia contractual para demostrar ayuda directa e indirecta al usuario.

```bash
C:\Bago_v4> python bago_core\cli.py evidence --mode simulated --objective community-knowledge --output docs\evidence\example_bundle --overwrite
âœ“ Bundle generado: C:\Bago_v4\docs\evidence\example_bundle\manifest.json
```

Comandos clave:

```bash
# Validar el generador
python bago_core\cli.py evidence --test

# Generar evidencia simulada (sin provider externo)
python bago_core\cli.py evidence --mode simulated --objective community-knowledge --output docs\evidence\example_bundle --overwrite

# Generar evidencia real con provider vivo
python bago_core\cli.py evidence --mode real --provider ollama-local --model "llama3.2:3b" --output C:\temp\bago_real_bundle
```

Contratos relacionados:

- `docs\COMMUNITY.md`
- `docs\contracts\README.md`
- `docs\contracts\bago_v4_runtime_contract.json`
- `docs\contracts\bago_v4_repl_contract.md`
- `docs\contracts\bago_v4_evidence_contract.md`
- `docs\contracts\bago_v4_knowledge_contract.md`

### Captura: `/help`

```
bago â¯ /help
Comandos disponibles:
  /switch <provider> [modelo] [--force]   Cambia de provider/modelo   
  /models [provider]                       Lista modelos disponibles  
  /status                                  Estado de la sesiÃ³n activa 
  /session                                 Detalles de la sesiÃ³n      
  /save                                    Guarda sesiÃ³n en disco     
  /load <session_id>                       Carga sesiÃ³n desde disco   
  /providers                               Lista providers registrados
  /feedback <rating>                       Feedback explÃ­cito (-1 a 1)
  /suggest                                 Sugerencia RL de provider
  /good [Ã­ndice]                           Marca mensaje como importante
  /config [list|get|set|reset]             Gestiona configuraciÃ³n
  /credentials [list|set|delete]           Gestiona credenciales API
  /tools [list|enable|disable]             Gestiona herramientas
  /allow                                   Aprueba ejecuciÃ³n de herramientas
  /deny                                    Rechaza ejecuciÃ³n de herramientas
  /plan <tarea>                           Genera plan paso a paso
  /autopilot <tarea>                       Ejecuta tarea autÃ³nomamente
  /agents                                  Lista agentes especializados
  /agent <nombre>                          Activa un agente especializado
  /memory [list|search|add|delete]           Gestiona base de conocimiento
  /help                                    Muestra esta ayuda
  /quit                                    Salir del chat
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â— ollama-local/llama3.2:3b Â· 0 tok
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
```

---

## 3. Estados de SesiÃ³n

### `/status` â€” Estado en tiempo real

```
bago â¯ /status
Session ID : 97a91109-878
Provider   : ollama-local
Model      : llama3.2:3b
Health     : OK â€” Ollama OK (5 models)
Messages   : 0
Tokens     : 0
Calls      : 0
Switches   : 0
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â— ollama-local/llama3.2:3b Â· 0 tok
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
```

### `/providers` â€” Providers registrados

Ejecuta `python bago_core\cli.py validate` para ver el estado de todos los providers:

```
[âœ“] ollama-local    â€” Ollama OK (5 models)
[âœ—] ollama-cloud    â€” No URL configured  
[âœ—] copilot         â€” No token configured
[âœ—] anthropic       â€” No API key
[âœ—] codex           â€” No API key
[âœ—] openrouter      â€” No API key
[âœ—] opencode        â€” No API key
```

> Los providers cloud requieren variables de entorno:
> - `OLLAMA_CLOUD_URL` / `OLLAMA_CLOUD_KEY`
> - `GITHUB_TOKEN` (Copilot)
> - `ANTHROPIC_API_KEY`
> - `OPENAI_API_KEY`
> - `OPENROUTER_API_KEY`
> - `OPENCODE_API_KEY`

---

## 4. Chat Multi-Provider

### Enviar un mensaje

Simplemente escribe tu mensaje y pulsa `Enter`:

```
bago â¯ Hola BAGO, confirma funcionamiento con OK
You Hola BAGO, confirma funcionamiento con OK
BAGO Â¡Hola! OK, confirmando funcionamiento... ESTOY ACTIVO. Â¿En quÃ© puedo ayudarte hoy?
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â— ollama-local/llama3.2:3b Â· 61 tok
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
```

### MultilÃ­nea

Usa tres backticks para enviar mensajes de varias lÃ­neas:

```
bago â¯ ```
... escribe
... varias
... lÃ­neas
... ```
```

---

## 5. Switch de Provider/Modelo

BAGO 4.1.5 permite cambiar de modelo **sin perder la sesiÃ³n**. El sistema evalÃºa la equivalencia entre modelos y aplica la estrategia de transferencia adecuada.

### Switch bÃ¡sico

```
bago â¯ /switch ollama-local llama3.2:1b --force
Switch completado: ollama-local/llama3.2:3b â†’ ollama-local/llama3.2:1b
âœ“ Switch: ollama-local/llama3.2:3b â†’ ollama-local/llama3.2:1b
  âš  Se aplicarÃ¡ estrategia de contexto: RESET
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
â— ollama-local/llama3.2:1b Â· 61 tok
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
```

### Niveles de equivalencia

| Tier | Modelos | Estrategia |
|------|---------|------------|
| Tier 1 (Frontier) | gpt-4o, claude-sonnet-4, qwen2.5:14b | DIRECT |
| Tier 2 (Everyday) | gpt-4o-mini, llama3.2, gemini-flash | DIRECT |
| Tier 3 (Fast) | phi4, deepseek-r1:8b | COMPRESS |
| Tier 4 (Ultra-light) | smollm2, tinyllama | REHYDRATE / RESET |

Si el switch no es recomendado, el sistema te avisarÃ¡. Usa `--force` para forzar.

### CompresiÃ³n por capas (downgrade)

Cuando cambias a un modelo menor, BAGO 4.1.5 **no pierde el contexto**: lo comprime por capas jerÃ¡rquicamente:

- **Capa 1** â†’ se resume en un bloque A
- **Capa 2** â†’ se resume + se une con A â†’ bloque unificado B
- **Capa 3** â†’ se resume + se une con B â†’ bloque C
- Y asÃ­ sucesivamente...

La idea principal se diluye progresivamente, a menos que la marques como **importante**.

### Marcar mensajes como "good" (no diluibles)

```
bago â¯ /good
Mensaje -1 marcado como 'good' â€” no se diluirÃ¡ en compresiÃ³n.
```

Los mensajes marcados como `good` sobreviven a la compresiÃ³n sin resumirse. Ãšsalos para:
- Instrucciones crÃ­ticas del system prompt
- Preguntas clave que no quieres que se diluyan
- Respuestas fundamentales que definen la conversaciÃ³n

### Ejemplo de compresiÃ³n

Historial original (3 capas):
```
[USER] Explica relatividad general en profundidad...
[ASSISTANT] La relatividad general de Einstein establece...
[USER-GOOD] Â¿Y quÃ© pasa con los agujeros negros?
[ASSISTANT] Los agujeros negros son regiones donde...
```

DespuÃ©s de compresiÃ³n:
```
[ASSISTANT] [USER] Explica relatividad... || PREV: [SYS-instrucciÃ³n base]
[ASSISTANT] [USER] Â¿Y quÃ© pasa con los agujeros negros? ... || PREV: [capa 1 resumida]
[PRESERVED USER]: Â¿Y quÃ© pasa con los agujeros negros?
```

Los datos de capas se persisten en:
```
.bago/state/layers/<session_id>_layers.jsonl
```

---

## 6. ConfiguraciÃ³n y Credenciales

BAGO 4.1.5 gestiona su configuraciÃ³n en `.bago/config.json` y las credenciales en `.bago/credentials.json`. Ya no dependes exclusivamente de variables de entorno.

### Desde la lÃ­nea de comandos

```bash
# Ver configuraciÃ³n completa
C:\Bago_v4> python bago_core\cli.py config list

# Cambiar provider por defecto
C:\Bago_v4> python bago_core\cli.py config set default_provider openrouter

# Activar un provider
C:\Bago_v4> python bago_core\cli.py config set providers.openrouter.enabled true

# Restaurar defaults
C:\Bago_v4> python bago_core\cli.py config reset
```

### Desde el REPL

```
bago â¯ /config list
ConfiguraciÃ³n:
default_provider : ollama-local
default_model    : llama3.2:3b
temperature      : 0.7
streaming        : True
compression      : True
rl_learning      : True

bago â¯ /config set temperature 0.5
âœ“ temperature = 0.5

bago â¯ /credentials set anthropic ANTHROPIC_API_KEY sk-ant-xxx
âœ“ Credencial guardada para anthropic/ANTHROPIC_API_KEY

bago â¯ /credentials list
  anthropic/ANTHROPIC_API_KEY: sk-a***
```

> **Seguridad:** Las credenciales se almacenan en `.bago/credentials.json` con permisos restrictivos (`0o600`).

---

## 7. Persistencia de SesiÃ³n

### Guardar manualmente

```
bago â¯ /save
SesiÃ³n guardada: 97a91109-878
```

### Guardado automÃ¡tico

Al salir con `/quit`, la sesiÃ³n se guarda automÃ¡ticamente:

```
bago â¯ /quit
Bye.
SesiÃ³n guardada automÃ¡ticamente: 97a91109-878
```

### Cargar una sesiÃ³n

```
bago â¯ /load 97a91109-878
SesiÃ³n cargada: 97a91109-878
```

Los archivos de sesiÃ³n se almacenan en:
```
.bago/state/sessions/<session_id>.json
```

---

## 8. Aprendizaje por Refuerzo (RL)

BAGO 4.1.5 incluye un motor de RL ligero que aprende de cada interacciÃ³n:

- **Recompensa implÃ­cita**: se calcula automÃ¡ticamente por rapidez, longitud de respuesta y ausencia de errores.
- **Recompensa explÃ­cita**: el usuario puede valorar cualquier respuesta con `/feedback <rating>`.
- **Sugerencia inteligente**: `/suggest` recomienda el provider/modelo con mejor historial.

### Feedback explÃ­cito

```
bago â¯ /feedback 1
Feedback registrado: 1.0
```

Valores vÃ¡lidos: `-1.0` (muy malo) a `1.0` (muy bueno).

### Sugerencia RL

```
bago â¯ /suggest
Sugerencia RL: ollama-local/granite3.2:8b (score=0.00)
```

A medida que uses el sistema, el score se ajustarÃ¡ y las sugerencias mejorarÃ¡n.

### Arquitectura RL

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚         FeedbackCollector               â”‚
â”‚   implicit() + explicit() â†’ RewardStore â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚         PreferenceModel                 â”‚
â”‚   score(provider, model, fingerprint)   â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚         RLPolicy (Îµ-greedy + UCB1)      â”‚
â”‚   select(candidates) â†’ best pair        â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

Los datos RL se persisten en:
```
.bago/state/rl/rewards.jsonl
```

---

## 9. Plan y Autopilot

BAGO 4.1.5 puede generar planes de tareas y ejecutarlos autÃ³nomamente.

### `/plan` â€” Generar plan paso a paso

```
bago â¯ /plan Crea un script Python que lea un CSV y genere un reporte
ðŸ“‹ Plan: Crea un script Python que lea un CSV y genere un reporte

  â—‹ 1. Crear archivo read_csv.py con funciones de lectura
  â—‹ 2. Crear funciÃ³n generate_report() que procese datos
  â—‹ 3. Escribir tests bÃ¡sicos
  â—‹ 4. Ejecutar script y verificar salida
```

### `/autopilot` â€” Ejecutar tarea autÃ³nomamente

```
bago â¯ /autopilot Crea un script Python que lea un CSV y genere un reporte
ðŸ“‹ Plan generado (4 pasos):
  â—‹ 1. Crear archivo read_csv.py...
  â—‹ 2. Crear funciÃ³n generate_report()...
  â—‹ 3. Escribir tests bÃ¡sicos...
  â—‹ 4. Ejecutar script y verificar salida...

ðŸš€ Ejecutando...
  âœ“ Paso 1: Crear archivo read_csv.py...
    â†’ Archivo escrito: read_csv.py (245 chars)...
  âœ“ Paso 2: Crear funciÃ³n generate_report()...
    â†’ FunciÃ³n aÃ±adida con formato HTML...
  âœ“ Paso 3: Escribir tests bÃ¡sicos...
    â†’ Tests escritos en test_read_csv.py...
  âœ“ Paso 4: Ejecutar script y verificar salida...
    â†’ report.html generado correctamente.
```

En modo **autopilot**, BAGO:
1. Genera un plan con el modelo activo
2. Ejecuta cada paso enviÃ¡ndolo al modelo
3. El modelo puede usar **herramientas** (`read_file`, `write_file`, `execute_command`) en cada paso
4. Muestra el progreso paso a paso

> **Nota:** Autopilot delega a `send()` (no streaming) para permitir tool calling en cada paso.

---

## 10. Allow All â€” Control de EjecuciÃ³n de Herramientas

BAGO 4.1.5 puede ejecutar herramientas automÃ¡ticamente o pedirte confirmaciÃ³n antes de hacerlo, al estilo **Copilot Allow All**.

### Comportamiento por defecto

Por defecto, `auto_allow_tools = False`: BAGO pide confirmaciÃ³n antes de ejecutar herramientas.

### Permitir ejecuciÃ³n automÃ¡tica

```
bago â¯ /config set features.auto_allow_tools true
âœ“ features.auto_allow_tools = True
```

Si mantienes el valor por defecto, cuando el modelo pida usar una herramienta, BAGO pausarÃ¡ y mostrarÃ¡:

```
â¸ï¸ El modelo quiere usar estas herramientas:
  â€¢ read_file: {"path": "main.py"}
  â€¢ execute_command: {"command": "python main.py"}

Escribe /allow para ejecutarlas o /deny para rechazarlas.
```

### Aprobar o rechazar

```
bago â¯ /allow
BAGO [resultado de las herramientas + respuesta final]
```

```
bago â¯ /deny
Herramientas rechazadas.
```

### Desde la lÃ­nea de comandos

```bash
C:\Bago_v4> python bago_core\cli.py config set features.auto_allow_tools true
```

---

## 11. Arranque LLM provider-aware

BAGO v4 puede separar providers instalados/configurados de providers disponibles para configurar:

```bash
C:\Bago_v4> python bago_core\cli.py llm list
```

Para iniciar una sesiÃ³n con un provider concreto:

```bash
C:\Bago_v4> python bago_core\cli.py llm start --provider ollama-local
```

Para validar la selecciÃ³n sin abrir el chat:

```bash
C:\Bago_v4> python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

La selecciÃ³n queda registrada en `.bago/state/llm_start.json` y se usa para esa sesiÃ³n de arranque. `cpp-local` queda fuera del camino principal y solo aparece con `--include-experimental`.

---

## 12. Base de Conocimiento (Knowledge Base)

BAGO 4.1.5 incluye una **base de conocimiento persistente** que sobrevive a las sesiones. Almacena recuerdos, hechos y notas importantes extraÃ­dos de las conversaciones.

### Almacenamiento

Los datos se guardan en SQLite (sin dependencias externas):

```
.bago/state/knowledge.db
```

### Comandos

```
bago â¯ /memory add Python fue creado por Guido van Rossum
âœ“ Recuerdo aÃ±adido (ID: 1).

bago â¯ /memory search Python
Resultados para 'Python':
  â€¢ Python fue creado por Guido van Rossum... (sesiÃ³n: 97a91109-878)

bago â¯ /memory list
Recuerdos recientes (1):
    1 | 2026-05-29T18:30:00 | Python fue creado por Guido van Rossum...

bago â¯ /memory delete 1
âœ“ Recuerdo 1 eliminado.
```

### Desde el cÃ³digo

```python
from knowledge_base import KnowledgeBase

kb = KnowledgeBase(base_path="C:\\Bago_v4")
kb.add("El usuario prefiere respuestas en espaÃ±ol.", source_session="sess-1")
results = kb.search("espaÃ±ol")
```

### IntegraciÃ³n automÃ¡tica

En el futuro, la Knowledge Base se puede conectar al `send()` para inyectar recuerdos relevantes en el system prompt antes de cada interacciÃ³n, dando al modelo contexto de largo plazo.

---

## 12. Arquitectura de BAGO 4.1.5

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚           Chat Interface (REPL)        â”‚
â”‚     renderer.py | commands.py | repl.pyâ”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚         Session Manager                 â”‚
â”‚   context_store + equiv_map + adaptersâ”‚
â”‚   + rl_engine + context_compressor    â”‚
â”‚   + plan_engine + agent_gateway         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      Tool Registry | Knowledge Base     â”‚
â”‚   read_file | write_file | execute_cmd â”‚
â”‚   search_memory | add_memory            â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚         Switch Engine                   â”‚
â”‚   validate â†’ verdict â†’ strategy â†’ exec  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      Provider Adapters (7)              â”‚
â”‚  ollama-local | ollama-cloud | copilot  â”‚
â”‚  anthropic | codex | openrouter         â”‚
â”‚  opencode                               â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      API Bridge (HTTP REST)            â”‚
â”‚   status | chat | providers | models    â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      Context Store (JSON Lines)         â”‚
â”‚  context.jsonl | timeline.jsonl         â”‚
â”‚  tokens.json | meta.json                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      Layer Store (JSON Lines)           â”‚
â”‚  <session_id>_layers.jsonl             â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      Knowledge Base (SQLite)           â”‚
â”‚  knowledge.db | memories | memories_ftsâ”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚      RL Store (JSON Lines)              â”‚
â”‚  rewards.jsonl                          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Principios

1. **SesiÃ³n = Fuente de verdad** â€” El contexto sobrevive al cambio de provider.
2. **Modelo = Motor temporal** â€” El provider es intercambiable; la sesiÃ³n persiste.
3. **No Gates** â€” El modelo actÃºa con sus capacidades nativas. El sistema no impone restricciones artificiales.
4. **Auto-ajuste** â€” Si un modelo no estÃ¡ disponible, se elige automÃ¡ticamente el primero de la lista.

---

## 13. Providers Soportados

| Provider | Tipo | Auth | Estado |
|----------|------|------|--------|
| **ollama-local** | Local | Ninguna | âœ… Listo |
| **ollama-cloud** | Cloud | URL + Key opcional | âš™ï¸ Configurable |
| **copilot** | Cloud | GitHub Token | âš™ï¸ Configurable |
| **anthropic** | Cloud | API Key | âš™ï¸ Configurable |
| **codex** | Cloud | API Key | âš™ï¸ Configurable |
| **openrouter** | Cloud | API Key | âš™ï¸ Configurable |
| **opencode** | Cloud | API Key | âš™ï¸ Configurable |

---

## 14. SoluciÃ³n de Problemas

### Error 404 / Modelo no encontrado

```
BAGO Error Ollama: HTTP Error 404: Not Found
```

**Causa:** El modelo por defecto no estÃ¡ descargado en Ollama.

**SoluciÃ³n:** BAGO 4.1.5 auto-ajusta al primer modelo disponible. Si aun asÃ­ falla, descarga un modelo:

```bash
ollama pull llama3.2:3b
```

### Timeout

```
BAGO Error Ollama: timed out
```

**Causa:** El modelo es muy lento o el sistema estÃ¡ sobrecargado.

**SoluciÃ³n:** Cambia a un modelo mÃ¡s rÃ¡pido:

```
/switch ollama-local llama3.2:3b --force
```

### Provider no configurado

```
[âœ—] anthropic â€” No API key
```

**SoluciÃ³n (vÃ­a entorno):** Exporta la variable de entorno correspondiente:

```bash
set ANTHROPIC_API_KEY=tu-key-aqui
```

**SoluciÃ³n (vÃ­a Credential Manager):** Desde el REPL:

```
bago â¯ /credentials set anthropic ANTHROPIC_API_KEY sk-ant-xxx
```

O desde lÃ­nea de comandos:

```bash
python bago_core\cli.py config set providers.anthropic.enabled true
```

> **Tip:** Al iniciar el REPL, BAGO 4.1.5 te ofrece una selecciÃ³n interactiva de providers y modelos disponibles.

---

## 15. Atajos y Tips

| Atajo | DescripciÃ³n |
|-------|-------------|
| `â†‘` / `â†“` | Navegar historial de comandos (readline) |
| `Ctrl+C` | Cancelar entrada actual |
| `Ctrl+D` | Salir del REPL (equivalente a `/quit`) |
| ```triple backticks``` | Modo multilÃ­nea |

---

**BAGO 4.1.5** â€” Session-First AI Chat  
*Construido con arquitectura atÃ³mica, sin gates, con memoria compartida.*
