# BAGO Canary — Trampas éticas de detección

## Qué es

BAGO Canary genera **señuelos locales** (archivos que parecen contener credenciales reales pero son falsas) y los coloca en ubicaciones donde un atacante buscaría secrets. Si alguien los lee, modifica o elimina, el sistema lo detecta.

**Diferencia con "trampa":**
- No ataca a naden ni usa APIs ajenas de forma maliciosa
- Son archivos en tu propio disco
- Detectan accesos no autorizados (como una alarma en tu casa)

---

## Tipos de señuelos

| Tipo | Qué parece | Cómo detecta |
|------|-----------|-------------|
| `aws_keys` | Credenciales AWS (AccessKey + Secret) | Modificación/eliminación |
| `openai_api` | API key de OpenAI (sk-...) | Modificación/eliminación |
| `github_pat` | Token de GitHub (ghp_...) | Modificación/eliminación |
| `telegram_bot` | Bot token de Telegram | Modificación/eliminación |
| `google_api` | API key de Google (AIza...) | Modificación/eliminación |
| `web_bug` | URL de webhook con bug HTTP | Visitas reales a la URL |

---

## Comandos

```bash
# Desplegar un señuelo
python E:/bago_fw/.bago/tools/bago_canary.py deploy --type aws_keys
python E:/bago_fw/.bago/tools/bago_canary.py deploy --type telegram_bot
python E:/bago_fw/.bago/tools/bago_canary.py deploy --type web_bug

# Revisar si hubo alertas
python E:/bago_fw/.bago/tools/bago_canary.py check

# Listar todos los señuelos activos
python E:/bago_fw/.bago/tools/bago_canary.py list

# Purga: elimina TODOS los señuelos
python E:/bago_fw/.bago/tools/bago_canary.py purge
```

---

## Archivos generados

 Estado persistente: `E:/bago_fw/.bago/state/canary_tokens.json`
 Log de eventos:    `E:/bago_fw/.bago/state/canary_log.jsonl`

---

## Flujo de uso recomendado

1. Despliega 2-3 señuelos en tipos diferentes
2. Ejecuta `check` cada día o programa un cron/task scheduler
3. Si alguien toca los archivos, `check` mostrará:
   - Tipo de alteración (LEÍDO, MODIFICADO, ELIMINADO)
   - Ruta del archivo
   - Timestamp
   - Para web_bug: IP, User-Agent, timestamp de visita

4. Las alertas se registran en `canary_log.jsonl`

---

## Dónde se colocan los señuelos

Se colocan automáticamente en ubicaciones realistas:

- `E:/.bago/user/aws_credentials.bak.json`
- `E:/.bago/user/credentials_old.json`
- `E:/.bago/state/backup_tokens.env`
- `E:/bago_fw/.bago/.env.backup`
- `E:/tmp/bago/session_export.json`
- etc.

Si ya existe un archivo en una ubicación, se prueba la siguiente.

---

## Integración con BAGO Health

Para añadir a `bago health`:
```bash
bago validate
bago health
```

El canary_log se puede revisar manualmente o con:
```bash
python E:/bago_fw/.bago/tools/bago_canary.py check
```

---

## Seguridad y ética

- ✅ Tokens generados son **falsos** — no funcionan en ningún servicio real
- ✅ Archivos están en tu propio sistema
- ✅ No se envía nada sin tu permiso
- ✅ `check` solo lee estados locales y webhook.site público
- ✅ No es vigilancia — es defensa pasiva de propiedad

---

## Estado actual en tu sistema

Señuelo desplegado:
```
Path:   E:/.bago/user/aws_credentials.bak.json
Tipo:   aws_keys
SHA256: dd027bc138caf03b...
```

Este archivo parece 100% real pero el token es inválido.
Si alguien lo usa en AWS, AWS rechazará la autenticación.
Pero BAGO Canary sabrá que alguien lo tocó.
