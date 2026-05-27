"""bago.tumba_schema — Catálogo de slots predefinidos por provider para el Modo Tumba.

Cada provider define exactamente qué secretos necesita:
  - name    → clave tumba canónica (lo que el usuario escribe como "Nombre clave:")
  - env     → variable de entorno que consume ese secreto (None si no aplica)
  - desc    → qué es y para qué sirve
  - format  → pista del formato esperado
  - required → True = obligatorio para que el provider funcione
  - url     → dónde obtenerlo

Agrupado por: llm · repo · cloud · messaging · payments · infra · database · email · devops · pm
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from typing import TypedDict


class TumbaSlot(TypedDict):
    name: str       # clave canónica en la tumba → usada como {{name}}
    env: str | None # variable de entorno que consume este secreto
    desc: str
    format: str     # hint de formato para el usuario
    required: bool
    url: str


# ──────────────────────────────────────────────────────────────────────────────
# SCHEMA COMPLETO
# provider_id (igual que en CredentialManager.PROVIDERS) → lista de slots
# ──────────────────────────────────────────────────────────────────────────────

TUMBA_SCHEMA: dict[str, list[TumbaSlot]] = {

    # ── LLM / AI providers ────────────────────────────────────────────────────

    "github": [
        {
            "name":     "GitHub Token",
            "env":      "GITHUB_TOKEN",
            "desc":     "Personal Access Token (classic) o token OAuth de gh CLI. "
                        "Permisos mínimos: repo, read:org, gist, copilot.",
            "format":   "ghp_XXXX... (classic PAT)  /  gho_XXXX... (OAuth)",
            "required": True,
            "url":      "https://github.com/settings/tokens",
        },
        {
            "name":     "GitHub App ID",
            "env":      "GITHUB_APP_ID",
            "desc":     "ID numérico de la GitHub App (solo si usas GitHub Apps, no PAT).",
            "format":   "123456",
            "required": False,
            "url":      "https://github.com/settings/apps",
        },
        {
            "name":     "GitHub App Private Key",
            "env":      "GITHUB_APP_PRIVATE_KEY",
            "desc":     "Clave privada PEM de la GitHub App (solo si usas GitHub Apps).",
            "format":   "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----",
            "required": False,
            "url":      "https://github.com/settings/apps",
        },
    ],

    "openai": [
        {
            "name":     "OpenAI API Key",
            "env":      "OPENAI_API_KEY",
            "desc":     "API key de OpenAI. Necesaria para GPT-4, GPT-4o, etc.",
            "format":   "sk-...",
            "required": True,
            "url":      "https://platform.openai.com/api-keys",
        },
        {
            "name":     "OpenAI Org ID",
            "env":      "OPENAI_ORG_ID",
            "desc":     "ID de organización OpenAI. Solo necesario en cuentas de empresa "
                        "con múltiples orgs.",
            "format":   "org-XXXX...",
            "required": False,
            "url":      "https://platform.openai.com/account/organization",
        },
        {
            "name":     "OpenAI Project ID",
            "env":      "OPENAI_PROJECT_ID",
            "desc":     "ID de proyecto OpenAI (nueva estructura de proyectos). "
                        "Opcional; por defecto usa el proyecto Default.",
            "format":   "proj_XXXX...",
            "required": False,
            "url":      "https://platform.openai.com/settings/organization/projects",
        },
    ],

    "anthropic": [
        {
            "name":     "Anthropic API Key",
            "env":      "ANTHROPIC_API_KEY",
            "desc":     "API key de Anthropic para Claude (Haiku, Sonnet, Opus).",
            "format":   "sk-ant-api03-XXXX...",
            "required": True,
            "url":      "https://console.anthropic.com/keys",
        },
    ],

    "gemini": [
        {
            "name":     "Gemini API Key",
            "env":      "GEMINI_API_KEY",
            "desc":     "API key de Google AI Studio para Gemini Flash, Pro, Ultra.",
            "format":   "AIzaSyXXXX...",
            "required": True,
            "url":      "https://aistudio.google.com/app/apikey",
        },
    ],

    "groq": [
        {
            "name":     "Groq API Key",
            "env":      "GROQ_API_KEY",
            "desc":     "API key de Groq. Inferencia ultra-rápida de Llama, Mistral, Mixtral.",
            "format":   "gsk_XXXX...",
            "required": True,
            "url":      "https://console.groq.com/keys",
        },
    ],

    "mistral": [
        {
            "name":     "Mistral API Key",
            "env":      "MISTRAL_API_KEY",
            "desc":     "API key de Mistral AI (Mistral Large, Mistral Small, Codestral).",
            "format":   "XXXX... (32 chars hex)",
            "required": True,
            "url":      "https://console.mistral.ai/api-keys",
        },
    ],

    "together": [
        {
            "name":     "Together API Key",
            "env":      "TOGETHER_API_KEY",
            "desc":     "API key de Together AI. Acceso a +100 modelos open-source en la nube.",
            "format":   "XXXX... (64 chars hex)",
            "required": True,
            "url":      "https://api.together.ai/settings/api-keys",
        },
    ],

    "deepseek": [
        {
            "name":     "DeepSeek API Key",
            "env":      "DEEPSEEK_API_KEY",
            "desc":     "API key de DeepSeek (V3, R1 para razonamiento). "
                        "Formato idéntico a OpenAI.",
            "format":   "sk-XXXX...",
            "required": True,
            "url":      "https://platform.deepseek.com/api_keys",
        },
    ],

    "xai": [
        {
            "name":     "xAI API Key",
            "env":      "XAI_API_KEY",
            "desc":     "API key de xAI para Grok-2, Grok Vision.",
            "format":   "xai-XXXX...",
            "required": True,
            "url":      "https://console.x.ai",
        },
    ],

    "perplexity": [
        {
            "name":     "Perplexity API Key",
            "env":      "PPLX_API_KEY",
            "desc":     "API key de Perplexity AI. Acceso a modelos sonar con búsqueda en tiempo real.",
            "format":   "pplx-XXXX...",
            "required": True,
            "url":      "https://www.perplexity.ai/settings/api",
        },
    ],

    "cohere": [
        {
            "name":     "Cohere API Key",
            "env":      "COHERE_API_KEY",
            "desc":     "API key de Cohere (Command R+, Embed, Rerank).",
            "format":   "XXXX... (40 chars)",
            "required": True,
            "url":      "https://dashboard.cohere.com/api-keys",
        },
    ],

    "replicate": [
        {
            "name":     "Replicate API Token",
            "env":      "REPLICATE_API_TOKEN",
            "desc":     "Token de Replicate. Ejecuta modelos open-source en la nube "
                        "(Stable Diffusion, Llama, Whisper, etc.).",
            "format":   "r8_XXXX...",
            "required": True,
            "url":      "https://replicate.com/account/api-tokens",
        },
    ],

    "huggingface": [
        {
            "name":     "HuggingFace Token",
            "env":      "HF_TOKEN",
            "desc":     "Access token de Hugging Face. Tipo 'read' para inferencia, "
                        "'write' para subir modelos/datasets.",
            "format":   "hf_XXXX...",
            "required": True,
            "url":      "https://huggingface.co/settings/tokens",
        },
    ],

    "openrouter": [
        {
            "name":     "OpenRouter API Key",
            "env":      "OPENROUTER_API_KEY",
            "desc":     "API key de OpenRouter. Un solo endpoint para +200 modelos "
                        "(Claude, GPT, Llama, Gemini...).",
            "format":   "sk-or-XXXX...",
            "required": True,
            "url":      "https://openrouter.ai/keys",
        },
    ],

    "ollama_cloud": [
        {
            "name":     "Ollama Cloud API Key",
            "env":      "OLLAMA_CLOUD_API_KEY",
            "desc":     "API key de Ollama Cloud (ollama.com). Alternativa a ollama signin.",
            "format":   "e85aXXXX... (obtenida en ollama.com/settings/api)",
            "required": True,
            "url":      "https://ollama.com/settings/api",
        },
    ],

    # ── Repositorios de código ────────────────────────────────────────────────

    "gitlab": [
        {
            "name":     "GitLab Token",
            "env":      "GITLAB_TOKEN",
            "desc":     "Personal Access Token de GitLab. "
                        "Permisos mínimos: api (para operaciones completas) o "
                        "read_repository + write_repository (solo repos).",
            "format":   "glpat-XXXX...",
            "required": True,
            "url":      "https://gitlab.com/-/user_settings/personal_access_tokens",
        },
    ],

    "codeberg": [
        {
            "name":     "Codeberg Token",
            "env":      "CODEBERG_TOKEN",
            "desc":     "Personal Access Token de Codeberg (Gitea). "
                        "Creado en User Settings → Applications.",
            "format":   "XXXX... (40 chars hex)",
            "required": True,
            "url":      "https://codeberg.org/user/settings/applications",
        },
    ],

    # ── Cloud / Almacenamiento ─────────────────────────────────────────────────

    "sendcm": [
        {
            "name":     "SendCM Email",
            "env":      None,
            "desc":     "Email de tu cuenta send.now. Se usa para autenticarse y obtener la API key.",
            "format":   "usuario@dominio.com",
            "required": True,
            "url":      "https://send.now/api",
        },
        {
            "name":     "SendCM Password",
            "env":      None,
            "desc":     "Contraseña de tu cuenta send.now. Solo se usa durante el login inicial.",
            "format":   "contraseña de la cuenta",
            "required": True,
            "url":      "https://send.now/api",
        },
        {
            "name":     "SendCM API Key",
            "env":      None,
            "desc":     "API key obtenida tras autenticarse en send.now. "
                        "Se usa para account/info, upload/server, upload/url, file/* y folder/*.",
            "format":   "XXXX... (token largo)",
            "required": False,
            "url":      "https://send.now/api",
        },
    ],

    # ── Mensajería / Bots ─────────────────────────────────────────────────────

    "telegram": [
        {
            "name":     "Telegram Bot Token",
            "env":      "TELEGRAM_BOT_TOKEN",
            "desc":     "Token del bot de Telegram. Se obtiene de @BotFather con /newbot.",
            "format":   "1234567890:ABCDefGHIjklMNOpqrSTUvwXYZ...",
            "required": True,
            "url":      "https://t.me/BotFather",
        },
        {
            "name":     "Telegram Chat ID",
            "env":      "TELEGRAM_CHAT_ID",
            "desc":     "ID del chat/canal/grupo donde enviar mensajes. "
                        "Usa @userinfobot para obtenerlo. Puede ser negativo para grupos.",
            "format":   "123456789  /  -100123456789  /  @username",
            "required": False,
            "url":      "https://t.me/userinfobot",
        },
        {
            "name":     "Telegram API ID",
            "env":      "TELEGRAM_API_ID",
            "desc":     "API ID de Telegram (MTProto). Solo necesario para apps cliente "
                        "(Telethon, Pyrogram). NO es el token del bot.",
            "format":   "12345678 (número entero)",
            "required": False,
            "url":      "https://my.telegram.org/apps",
        },
        {
            "name":     "Telegram API Hash",
            "env":      "TELEGRAM_API_HASH",
            "desc":     "API Hash de Telegram (MTProto). Acompaña siempre al API ID.",
            "format":   "a1b2c3d4e5f6... (32 chars hex)",
            "required": False,
            "url":      "https://my.telegram.org/apps",
        },
    ],

    "discord": [
        {
            "name":     "Discord Bot Token",
            "env":      "DISCORD_BOT_TOKEN",
            "desc":     "Token del bot de Discord. Se obtiene en el Portal de Developers "
                        "bajo Bot → Reset Token.",
            "format":   "MTxxxxxx.Gxxxxx.xxxxxxxxxxxxxxxxxx",
            "required": True,
            "url":      "https://discord.com/developers/applications",
        },
        {
            "name":     "Discord Webhook URL",
            "env":      "DISCORD_WEBHOOK_URL",
            "desc":     "URL de webhook de Discord para enviar mensajes sin bot completo. "
                        "Configurado en Channel Settings → Integrations → Webhooks.",
            "format":   "https://discord.com/api/webhooks/ID/TOKEN",
            "required": False,
            "url":      "https://discord.com/developers/applications",
        },
        {
            "name":     "Discord Client ID",
            "env":      "DISCORD_CLIENT_ID",
            "desc":     "Application ID (Client ID) de la app de Discord. "
                        "Visible en General Information.",
            "format":   "123456789012345678 (snowflake ID)",
            "required": False,
            "url":      "https://discord.com/developers/applications",
        },
        {
            "name":     "Discord Client Secret",
            "env":      "DISCORD_CLIENT_SECRET",
            "desc":     "Client Secret de la app de Discord. Para flujos OAuth2.",
            "format":   "XXXX... (32 chars)",
            "required": False,
            "url":      "https://discord.com/developers/applications",
        },
    ],

    "slack": [
        {
            "name":     "Slack Bot Token",
            "env":      "SLACK_BOT_TOKEN",
            "desc":     "Bot User OAuth Token de Slack. Se obtiene tras instalar la app "
                        "en un workspace. Permisos mínimos: chat:write.",
            "format":   "xoxb-XXXX-XXXX-XXXX",
            "required": True,
            "url":      "https://api.slack.com/apps",
        },
        {
            "name":     "Slack App Token",
            "env":      "SLACK_APP_TOKEN",
            "desc":     "App-Level Token de Slack. Necesario para Socket Mode "
                        "(recibir eventos sin servidor HTTP público).",
            "format":   "xapp-1-XXXX-XXXX-XXXX",
            "required": False,
            "url":      "https://api.slack.com/apps",
        },
        {
            "name":     "Slack Signing Secret",
            "env":      "SLACK_SIGNING_SECRET",
            "desc":     "Signing Secret de Slack. Se usa para verificar que los eventos "
                        "vienen de Slack. Obligatorio si recibes webhooks HTTP.",
            "format":   "XXXX... (32 chars hex)",
            "required": False,
            "url":      "https://api.slack.com/apps",
        },
        {
            "name":     "Slack Webhook URL",
            "env":      "SLACK_WEBHOOK_URL",
            "desc":     "Incoming Webhook URL de Slack. Para enviar mensajes a un canal "
                        "sin bot completo.",
            "format":   "https://hooks.slack.com/services/T.../B.../...",
            "required": False,
            "url":      "https://api.slack.com/apps",
        },
    ],

    "twilio": [
        {
            "name":     "Twilio Account SID",
            "env":      "TWILIO_ACCOUNT_SID",
            "desc":     "Account SID de Twilio. Es el identificador de tu cuenta, "
                        "no es secreto per se, pero se requiere para todas las llamadas.",
            "format":   "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "required": True,
            "url":      "https://console.twilio.com",
        },
        {
            "name":     "Twilio Auth Token",
            "env":      "TWILIO_AUTH_TOKEN",
            "desc":     "Auth Token de Twilio. ES el secreto real — trátalo como contraseña.",
            "format":   "XXXX... (32 chars hex)",
            "required": True,
            "url":      "https://console.twilio.com",
        },
        {
            "name":     "Twilio Phone Number",
            "env":      "TWILIO_PHONE_NUMBER",
            "desc":     "Número de teléfono de Twilio desde el que se envían SMS/llamadas.",
            "format":   "+15551234567 (E.164 format)",
            "required": False,
            "url":      "https://console.twilio.com/us1/develop/phone-numbers",
        },
    ],

    # ── Pagos ──────────────────────────────────────────────────────────────────

    "stripe": [
        {
            "name":     "Stripe Secret Key",
            "env":      "STRIPE_SECRET_KEY",
            "desc":     "Clave secreta de Stripe. NUNCA va al frontend. "
                        "sk_test_... para tests, sk_live_... para producción.",
            "format":   "sk_live_XXXX...  /  sk_test_XXXX...",
            "required": True,
            "url":      "https://dashboard.stripe.com/apikeys",
        },
        {
            "name":     "Stripe Publishable Key",
            "env":      "STRIPE_PUBLISHABLE_KEY",
            "desc":     "Clave publicable de Stripe. Puede ir al frontend. "
                        "pk_test_... para tests, pk_live_... para producción.",
            "format":   "pk_live_XXXX...  /  pk_test_XXXX...",
            "required": False,
            "url":      "https://dashboard.stripe.com/apikeys",
        },
        {
            "name":     "Stripe Webhook Secret",
            "env":      "STRIPE_WEBHOOK_SECRET",
            "desc":     "Webhook signing secret de Stripe. Se usa para verificar "
                        "que los eventos POST vienen de Stripe y no de terceros.",
            "format":   "whsec_XXXX...",
            "required": False,
            "url":      "https://dashboard.stripe.com/webhooks",
        },
    ],

    # ── Infraestructura cloud ──────────────────────────────────────────────────

    "aws": [
        {
            "name":     "AWS Access Key ID",
            "env":      "AWS_ACCESS_KEY_ID",
            "desc":     "Access Key ID de IAM de AWS. Identifica la cuenta/usuario. "
                        "Se usa junto con el Secret Access Key.",
            "format":   "AKIAIOSFODNN7EXAMPLE",
            "required": True,
            "url":      "https://console.aws.amazon.com/iam/home#/security_credentials",
        },
        {
            "name":     "AWS Secret Access Key",
            "env":      "AWS_SECRET_ACCESS_KEY",
            "desc":     "Secret Access Key de IAM de AWS. Es el secreto real — "
                        "trátalo como contraseña.",
            "format":   "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "required": True,
            "url":      "https://console.aws.amazon.com/iam/home#/security_credentials",
        },
        {
            "name":     "AWS Region",
            "env":      "AWS_DEFAULT_REGION",
            "desc":     "Región AWS por defecto. No es secreto, pero es configuración necesaria.",
            "format":   "us-east-1  /  eu-west-1  /  ap-southeast-1",
            "required": False,
            "url":      "https://docs.aws.amazon.com/general/latest/gr/rande.html",
        },
    ],

    "cloudflare": [
        {
            "name":     "Cloudflare API Token",
            "env":      "CLOUDFLARE_API_TOKEN",
            "desc":     "API Token de Cloudflare (granular, con permisos específicos). "
                        "Preferido sobre la Global API Key.",
            "format":   "XXXX... (40 chars)",
            "required": True,
            "url":      "https://dash.cloudflare.com/profile/api-tokens",
        },
        {
            "name":     "Cloudflare Account ID",
            "env":      "CLOUDFLARE_ACCOUNT_ID",
            "desc":     "Account ID de Cloudflare. Visible en el dashboard. "
                        "Necesario para Workers, R2, D1, etc.",
            "format":   "XXXX... (32 chars hex)",
            "required": False,
            "url":      "https://dash.cloudflare.com",
        },
        {
            "name":     "Cloudflare Zone ID",
            "env":      "CLOUDFLARE_ZONE_ID",
            "desc":     "Zone ID del dominio específico en Cloudflare. "
                        "Necesario para operaciones DNS/página en ese dominio.",
            "format":   "XXXX... (32 chars hex)",
            "required": False,
            "url":      "https://dash.cloudflare.com",
        },
    ],

    "vercel": [
        {
            "name":     "Vercel Token",
            "env":      "VERCEL_TOKEN",
            "desc":     "Personal Access Token de Vercel para la CLI y la API REST.",
            "format":   "XXXX... (24 chars)",
            "required": True,
            "url":      "https://vercel.com/account/tokens",
        },
    ],

    "netlify": [
        {
            "name":     "Netlify Auth Token",
            "env":      "NETLIFY_AUTH_TOKEN",
            "desc":     "Personal Access Token de Netlify para la CLI y la API.",
            "format":   "XXXX... (UUID format)",
            "required": True,
            "url":      "https://app.netlify.com/user/applications",
        },
    ],

    # ── Bases de datos ─────────────────────────────────────────────────────────

    "supabase": [
        {
            "name":     "Supabase URL",
            "env":      "SUPABASE_URL",
            "desc":     "URL del proyecto Supabase. No es secreto per se, pero se "
                        "necesita junto a la clave.",
            "format":   "https://xxxxxxxxxxxx.supabase.co",
            "required": True,
            "url":      "https://supabase.com/dashboard/project/_/settings/api",
        },
        {
            "name":     "Supabase Anon Key",
            "env":      "SUPABASE_ANON_KEY",
            "desc":     "Clave anónima (pública) de Supabase. Puede ir al frontend. "
                        "Sujeta a Row Level Security.",
            "format":   "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "required": True,
            "url":      "https://supabase.com/dashboard/project/_/settings/api",
        },
        {
            "name":     "Supabase Service Key",
            "env":      "SUPABASE_SERVICE_ROLE_KEY",
            "desc":     "Clave de servicio de Supabase. BYPASEA Row Level Security. "
                        "SOLO en backend. Nunca en el frontend.",
            "format":   "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "required": False,
            "url":      "https://supabase.com/dashboard/project/_/settings/api",
        },
    ],

    "firebase": [
        {
            "name":     "Firebase Project ID",
            "env":      "FIREBASE_PROJECT_ID",
            "desc":     "ID del proyecto Firebase. Visible en la configuración del proyecto.",
            "format":   "mi-proyecto-123",
            "required": True,
            "url":      "https://console.firebase.google.com",
        },
        {
            "name":     "Firebase Private Key",
            "env":      "FIREBASE_PRIVATE_KEY",
            "desc":     "Clave privada RSA de la cuenta de servicio Firebase. "
                        "Del archivo JSON descargado desde la consola.",
            "format":   "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----",
            "required": True,
            "url":      "https://console.firebase.google.com/project/_/settings/serviceaccounts",
        },
        {
            "name":     "Firebase Client Email",
            "env":      "FIREBASE_CLIENT_EMAIL",
            "desc":     "Email de la cuenta de servicio Firebase. "
                        "Del archivo JSON de credenciales.",
            "format":   "firebase-adminsdk-XXXX@mi-proyecto.iam.gserviceaccount.com",
            "required": True,
            "url":      "https://console.firebase.google.com/project/_/settings/serviceaccounts",
        },
    ],

    "mongodb": [
        {
            "name":     "MongoDB URI",
            "env":      "MONGODB_URI",
            "desc":     "Connection string de MongoDB Atlas o instancia propia. "
                        "Incluye usuario, contraseña y host. Tratar como secreto.",
            "format":   "mongodb+srv://usuario:contraseña@cluster.mongodb.net/database",
            "required": True,
            "url":      "https://cloud.mongodb.com",
        },
    ],

    "postgresql": [
        {
            "name":     "Database URL",
            "env":      "DATABASE_URL",
            "desc":     "Connection string de PostgreSQL. Incluye usuario, contraseña, "
                        "host y base de datos.",
            "format":   "postgresql://usuario:contraseña@host:5432/database",
            "required": True,
            "url":      "",
        },
    ],

    "redis": [
        {
            "name":     "Redis URL",
            "env":      "REDIS_URL",
            "desc":     "Connection string de Redis. Incluye contraseña si está configurada.",
            "format":   "redis://:contraseña@host:6379/0  /  redis://host:6379",
            "required": True,
            "url":      "",
        },
    ],

    # ── Email / SMS ────────────────────────────────────────────────────────────

    "sendgrid": [
        {
            "name":     "SendGrid API Key",
            "env":      "SENDGRID_API_KEY",
            "desc":     "API key de SendGrid para enviar emails transaccionales.",
            "format":   "SG.XXXX...",
            "required": True,
            "url":      "https://app.sendgrid.com/settings/api_keys",
        },
    ],

    "mailgun": [
        {
            "name":     "Mailgun API Key",
            "env":      "MAILGUN_API_KEY",
            "desc":     "API key de Mailgun para enviar emails.",
            "format":   "key-XXXX...",
            "required": True,
            "url":      "https://app.mailgun.com/settings/api_security",
        },
        {
            "name":     "Mailgun Domain",
            "env":      "MAILGUN_DOMAIN",
            "desc":     "Dominio verificado en Mailgun desde el que se envían emails.",
            "format":   "mg.tudominio.com",
            "required": True,
            "url":      "https://app.mailgun.com/domains",
        },
    ],

    # ── DevOps / Registros de paquetes ────────────────────────────────────────

    "npm": [
        {
            "name":     "NPM Token",
            "env":      "NPM_TOKEN",
            "desc":     "Automation token de npm para publicar paquetes en CI/CD "
                        "sin interacción manual.",
            "format":   "npm_XXXX...",
            "required": True,
            "url":      "https://www.npmjs.com/settings/~/tokens",
        },
    ],

    "pypi": [
        {
            "name":     "PyPI Token",
            "env":      "PYPI_API_TOKEN",
            "desc":     "API token de PyPI para publicar paquetes Python. "
                        "Tiene alcance global o por proyecto.",
            "format":   "pypi-XXXX...",
            "required": True,
            "url":      "https://pypi.org/manage/account/token/",
        },
    ],

    # ── Gestión de proyectos ───────────────────────────────────────────────────

    "jira": [
        {
            "name":     "Jira API Token",
            "env":      "JIRA_API_TOKEN",
            "desc":     "API Token de Jira Cloud (Atlassian). Se usa junto al email "
                        "en autenticación Basic.",
            "format":   "XXXX... (24 chars base64)",
            "required": True,
            "url":      "https://id.atlassian.com/manage-profile/security/api-tokens",
        },
        {
            "name":     "Jira Base URL",
            "env":      "JIRA_BASE_URL",
            "desc":     "URL base de tu instancia Jira Cloud.",
            "format":   "https://tu-empresa.atlassian.net",
            "required": True,
            "url":      "",
        },
        {
            "name":     "Jira Email",
            "env":      "JIRA_EMAIL",
            "desc":     "Email de la cuenta Atlassian asociado al API Token.",
            "format":   "usuario@empresa.com",
            "required": True,
            "url":      "",
        },
    ],

    "linear": [
        {
            "name":     "Linear API Key",
            "env":      "LINEAR_API_KEY",
            "desc":     "API key de Linear para gestión de issues y proyectos.",
            "format":   "lin_api_XXXX...",
            "required": True,
            "url":      "https://linear.app/settings/api",
        },
    ],

    "notion": [
        {
            "name":     "Notion API Key",
            "env":      "NOTION_API_KEY",
            "desc":     "Integration Secret de Notion (Internal Integration Token). "
                        "Se genera en notion.so/my-integrations.",
            "format":   "secret_XXXX...",
            "required": True,
            "url":      "https://www.notion.so/my-integrations",
        },
        {
            "name":     "Notion Database ID",
            "env":      "NOTION_DATABASE_ID",
            "desc":     "ID de la base de datos Notion. Visible en la URL de la página: "
                        "notion.so/workspace/ESTE-ES-EL-ID?...",
            "format":   "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (UUID)",
            "required": False,
            "url":      "",
        },
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def get_slots(provider: str) -> list[TumbaSlot]:
    """Devuelve los slots predefinidos para un provider. Lista vacía si no existe."""
    return TUMBA_SCHEMA.get(provider, [])


def all_providers() -> list[str]:
    """Lista todos los providers con schema predefinido."""
    return list(TUMBA_SCHEMA.keys())


def required_slots(provider: str) -> list[TumbaSlot]:
    """Devuelve solo los slots obligatorios de un provider."""
    return [s for s in get_slots(provider) if s["required"]]


def missing_slots(provider: str, tumba_keys: list[str]) -> list[TumbaSlot]:
    """Devuelve slots requeridos que aún no están en la tumba."""
    existing = set(tumba_keys)
    return [s for s in get_slots(provider) if s["name"] not in existing]


def optional_slots(provider: str) -> list[TumbaSlot]:
    """Devuelve solo los slots opcionales de un provider."""
    return [s for s in get_slots(provider) if not s["required"]]


def provider_group(provider: str) -> str:
    """Devuelve el grupo semántico de un provider."""
    _GROUPS = {
        "llm":       {"github","openai","anthropic","gemini","groq","mistral",
                      "together","deepseek","xai","perplexity","cohere","replicate",
                      "huggingface","openrouter","ollama_cloud"},
        "repo":      {"gitlab","codeberg"},
        "cloud":     {"sendcm"},
        "messaging": {"telegram","discord","slack","twilio"},
        "payments":  {"stripe"},
        "infra":     {"aws","cloudflare","vercel","netlify"},
        "database":  {"supabase","firebase","mongodb","postgresql","redis"},
        "email":     {"sendgrid","mailgun"},
        "devops":    {"npm","pypi"},
        "pm":        {"jira","linear","notion"},
    }
    for group, members in _GROUPS.items():
        if provider in members:
            return group
    return "other"


def all_by_group() -> dict[str, list[str]]:
    """Devuelve todos los providers agrupados por categoría."""
    from collections import defaultdict
    result: dict[str, list[str]] = defaultdict(list)
    for prov in TUMBA_SCHEMA:
        result[provider_group(prov)].append(prov)
    return dict(result)
