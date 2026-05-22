# BAGO 3.5.0 — Escalacion Multi-Provider

**Fecha:** 2026-05-22  
**Tag:** v3.5.0  
**Tipo:** Stable

---

## Instalacion

### Desde cero (Windows)

`powershell
# 1. Clonar
git clone https://github.com/MarcValls/BAGO.git
cd BAGO

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Instalar BAGO
python install.ps1

# 4. Primera ejecucion
bago launch
`

### Actualizar desde 3.4.x

`powershell
cd BAGO
git pull origin main

# Solo los archivos modificados:
#   .bago/tools/bago/credentials/manager.py
#   .bago/tools/bago/llm/routing.py
#   .bago/tools/bago/llm/orchestrator.py
#   .bago/tools/bago/providers.py
#   .bago/state/model_providers.json

# Reiniciar BAGO
bago restart
`

### Registrar providers adicionales

`ash
# En el REPL de BAGO:
/login github        # GitHub Copilot / Models (token o browser)
/login openai        # OpenAI API key o ChatGPT Plus login
/login anthropic     # Anthropic Claude API key
/login replicate     # Replicate API key
/login deepseek      # DeepSeek API key
/login groq          # Groq API key
/login ollama-cloud  # Ollama Cloud signin

# O directamente en credentials.json:
# Las claves se leen de ~/.bago/credentials.json
# Y tambien de variables de entorno (ANTHROPIC_API_KEY, etc.)
`

---

## Novedades

### 1. Escalacion iterativa sobre TODOS los providers

**Antes:** Cuando un modelo fallaba (auth, quota, conexion), BAGO probaba UN solo provider y fallaba silenciosamente.

**Ahora:** BAGO itera sobre TODOS los providers con credenciales validas, probando cada uno hasta encontrar uno que funcione.

`
0.5b local (respuesta basura)
  -> codex/gpt-5.5 (OAuth token ChatGPT Plus)
  -> copilot/claude-sonnet (GitHub token)
  -> replicate/llama-4-maverick (API key)
  -> ollama-local/qwen25-coder (local 7b)
  -> ollama-cloud/devstral-2 (ollama signin)
`

Cada fallo marca el provider como degradado (mark_provider_degraded) y pasa al siguiente.

### 2. Validacion de credenciales

- OPENAI_API_KEY=ollama ya no activa el provider codex.
- Las keys se validan con heuristica: longitud minima 8, no palabras obvias.
- credentials.json se lee ademas de env vars (replicate, github, etc.).

### 3. Soporte dinamico de providers

Si anades un provider nuevo (deepseek, groq, etc.) via /login o env var, aparece automaticamente en la escalacion sin cambios de codigo.

### 4. Replicate como provider

Modelos disponibles:
- llama-4-maverick — general
- deepseek-r1 — reasoning
- qwen25-coder-32b — code

### 5. Copilot: token desde credentials.json

Si GITHUB_TOKEN no esta en env, lo busca en ~/.bago/credentials.json.

### 6. Codex: OAuth prioritario

Si OPENAI_API_KEY es invalida, salta al OAuth token de ChatGPT Plus (~/.codex/auth.json).

---

## Arquitectura de la escalacion

`
Usuario escribe prompt
  |
  v
auto_route() -> elige modelo inicial (0.5b local)
  |
  v
_llm_call() -> respuesta basura?
  |
  v  (si basura)
_quality_cloud_retry() -> itera _cloud_escalation_candidates()
  |- codex/gpt-5.5      -> auth error? mark_degraded, siguiente
  |- copilot/claude      -> funciona! return respuesta
  |- replicate/llama-4   -> (no probado, ya tiene respuesta)
  |- ollama-local/7b     -> (no probado)
  |- ollama-cloud/devstral-> (no probado)
`

Si TODOS fallan, retorna la mejor respuesta disponible (local).

---

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| credentials/manager.py | ctive_bago_providers() lee credentials.json, valida keys |
| llm/routing.py | _escalate_candidates(), _cloud_escalation_candidates(), _cloud_priority_order() dinamicos |
| llm/orchestrator.py | _quality_cloud_retry() itera candidatos, ctx-overflow itera |
| providers.py | _is_valid_api_key(), esolve_litellm() generico, copilot lee cred file |
| model_providers.json | Provider eplicate anadido |

---

## Compatibilidad

- Retrocompatible: _escalate_model() y _cloud_escalation_for_quality() siguen existiendo como wrappers.
- Sin cambios en CLI ni comandos de usuario.
- Los providers existentes siguen funcionando igual.
