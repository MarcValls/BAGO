# BAGO API — Informe de Integración

## Estado Actual
- **API BAGO**: ✅ Activa en http://127.0.0.1:11435
- **Providers disponibles**: ollama-local, ollama-cloud, copilot, codex
- **Modelos detectados**: phi4:14b, llama3.2, y otros

## Endpoints BAGO (compatibles con Ollama)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | /api/chat | Chat completions (streaming soportado) |
| POST | /api/generate | Generación de texto |
| POST | /api/embed | Embeddings |
| GET | /api/tags | Lista de modelos disponibles |
| GET | /api/providers | Providers configurados |
| POST | /api/route | Enrutamiento automático BAGO |
| GET | /api/health | Health check |

## Integración con n8n

### 1. HTTP Request Node → BAGO API

`json
{
  "method": "POST",
  "url": "http://127.0.0.1:11435/api/chat",
  "body": {
    "model": "phi4:14b",
    "messages": [
      {"role": "user", "content": "{{['mensaje']}}"}
    ],
    "stream": false
  }
}
`

### 2. Webhook Node (n8n → BAGO)

- **Webhook URL**: http://127.0.0.1:11435/api/chat
- **HTTP Method**: POST
- **Authentication**: None (local)
- **Response**: JSON con {message: {content: "..."}}

## Bots de Mensajería

### Telegram Bot
`powershell
# Requiere TOKEN de @BotFather
="tu_token_aqui"
bago bot telegram
`

**Comandos:**
- /start — Presentación
- /status — Estado de providers
- /model <nombre> — Cambiar modelo
- /informe <asunto> — Generar informe

### Utopia Bot
`powershell
# Requiere Utopia client corriendo con API HTTP
bago bot utopia
`

## Arquitectura de Puertos

| Puerto | Servicio | Uso |
|--------|----------|-----|
| 11434 | ollama-local | Ollama nativo |
| 11435 | **bago** | **Orquestador principal** |
| 11436 | copilot | GitHub Models |
| 11437 | codex | OpenAI |
| 11438 | ollama-cloud | Ollama Cloud |
| 11439 | telegram-bot | Bot Telegram |
| 11440 | utopia-bot | Cliente Utopia |

## Flujo: Telegram → BAGO → n8n → Informe

1. Usuario envía mensaje a bot Telegram
2. Bot reenvía a http://127.0.0.1:11435/api/chat
3. BAGO orquesta entre 3 providers (ollama, copilot, codex)
4. Respuesta consolidada vuelve a Telegram
5. n8n puede interceptar/webhook para guardar informes

## Comandos de Prueba

`powershell
# Ver modelos disponibles
Invoke-RestMethod http://127.0.0.1:11435/api/tags

# Chat directo
 = @{model="phi4:14b"; messages=@(@{role="user"; content="Hola"})} | ConvertTo-Json
Invoke-RestMethod -Method POST http://127.0.0.1:11435/api/chat -Body  -ContentType "application/json"

# Iniciar bot Telegram
="token"
bago bot telegram
