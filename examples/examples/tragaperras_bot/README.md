# 🎰 Tragaperras — Bot de Telegram

Bot de Telegram con un juego de tragaperras completo.  
La banca siempre gana (~29% house edge) pero el jugador siente que casi gana.

## Mecánicas de diseño

| Mecánica | Descripción |
|---|---|
| **House edge real** | ~29% (RTP ≈ 71%) — calibrado con 100 000 giros de simulación |
| **Near-miss** | 30% de giros perdedores terminan con 2 iguales visibles; el 3er carrete "se escapa" |
| **Victorias frecuentes** | Triple cereza cae ~6.4% de las veces — el jugador gana a menudo en pequeño |
| **Ilusión de control** | Botones de apuesta (➕➖) dan sensación de estrategia |
| **Mensajes contextuales** | Mensajes distintos para near-miss, victoria, jackpot |

### Tabla de pagos

| Combo | Multiplicador | Frecuencia aprox. |
|---|---|---|
| 🍒🍒🍒 | ×8 | 1 de cada 16 giros |
| 🍋🍋🍋 | ×8 | 1 de cada 64 giros |
| 🍊🍊🍊 | ×15 | 1 de cada 296 giros |
| 🍇🍇🍇 | ×25 | 1 de cada 1 000 giros |
| ⭐⭐⭐ | ×60 | 1 de cada 8 000 giros |
| 💎💎💎 | ×150 | 1 de cada 37 000 giros |
| 7️⃣7️⃣7️⃣ | ×500 JACKPOT | 1 de cada 125 000 giros |

---

## Instalación

```bash
# 1. Clonar o copiar esta carpeta
cd tragaperras_bot

# 2. Crear entorno virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar el token
cp .env.example .env
# Edita .env y pega tu token de BotFather
```

## Obtener token de BotFather

1. Abre Telegram → busca `@BotFather`
2. Escribe `/newbot`
3. Elige nombre (ej: `Casino BAGO`) y username (ej: `casino_bago_bot`)
4. Copia el token que te da y pégalo en `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   ```

## Arrancar el bot

```bash
python3 bot.py
```

El bot queda escuchando. Búscalo en Telegram por el username que elegiste.

## Comandos del bot

| Comando | Acción |
|---|---|
| `/start` | Bienvenida + 500 fichas gratis |
| `/girar` | Girar los rodillos |
| `/apostar <N>` | Cambiar la apuesta (5–500) |
| `/saldo` | Ver saldo y estadísticas personales |
| `/tabla` | Ver tabla de pagos |
| `/ayuda` | Mostrar ayuda |

También funciona con los botones inline — no hace falta escribir comandos.

## Estructura del proyecto

```
tragaperras_bot/
├── slot_engine.py   # Motor del juego (probabilidades, near-miss, RTP)
├── bot.py           # Bot de Telegram
├── requirements.txt
├── .env.example
└── README.md
```

## Despliegue en producción

Para que el bot corra 24/7 puedes usar:

**Railway / Render (gratis):**
```bash
# Añade TELEGRAM_BOT_TOKEN como variable de entorno en el dashboard
# Procfile:
echo "worker: python bot.py" > Procfile
```

**VPS con systemd:**
```ini
# /etc/systemd/system/tragaperras.service
[Unit]
Description=Tragaperras Telegram Bot

[Service]
WorkingDirectory=/opt/tragaperras_bot
ExecStart=/opt/tragaperras_bot/.venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable tragaperras && sudo systemctl start tragaperras
```

> ⚠️ **Aviso legal:** Este bot usa fichas virtuales sin valor económico real.  
> Está diseñado exclusivamente como entretenimiento y demostración técnica.  
> No fomentes el juego con dinero real.
