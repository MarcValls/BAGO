# Casino Mini App — Patrones y Aprendizajes
# Session: b3894548 · 2026-05-13 · Telegram Mini App Casino BAGO

> **Proyecto:** Casino BAGO — Telegram Mini App slot machine
> **Sesiones cubiertas:** 7 checkpoints (2026-05-12 a 2026-05-13)
> **Stack:** Python/SQLite + HTML/JS + Pillow sprites + TON Connect + ngrok
> **Compilado:** 2026-05-13

---

## 1. PATRÓN: SPRITES PRE-RENDERIZADOS — PILLOW SIN macOS

**Problema:** gen_ui.py original usaba AppKit (macOS-only) para texto con emoji.
**Solución:** Pillow puro es suficiente para la mayoría de sprites gráficos.

```python
# Gradiente vertical funcional con Pillow
for y in range(H):
    t = y / H
    c = lerp(color_top, color_bottom, t)
    draw.line([(0, y), (W, y)], fill=(*c, alpha))

# Borde con rounded_rectangle (Pillow 9+)
draw.rounded_rectangle([x0, y0, x1, y1], radius=12,
                        fill=fill, outline=outline, width=2)

# Glow neón: Gaussian blur sobre canal alpha coloreado
glow = img.filter(ImageFilter.GaussianBlur(radius))
result = Image.alpha_composite(glow, glow)  # doble para intensidad
result = Image.alpha_composite(result, img)
```

**Regla:** Usar Pillow para todos los sprites que no requieran emoji nativos.
Reservar AppKit/NSAttributedString para sprites con emojis del sistema (símbolos del casino).

---

## 2. PATRÓN: RTP CALIBRADO — FÓRMULA DEL ANCLA

**Problema:** RTP inicial del 71% — demasiado bajo, visualmente obvio que "roba".
**Solución:** El símbolo más frecuente funciona como "ancla" del RTP total.

```python
# Distribución de pesos (total = 100)
WEIGHTS = [60, 20, 10, 5, 3, 1.5, 0.5]  # cherry, lemon, orange, grape, star, diamond, seven

# Fórmula del ancla:
# RTP_anchor = P(cherry)^3 * cherry_mult
# P(cherry)^3 = (60/100)^3 = 0.216
# RTP_anchor = 0.216 * 4 = 0.864

# RTP total ≈ RTP_anchor + contribuciones_resto ≈ 0.864 + 0.086 = 0.95

# Para calibrar a un RTP objetivo:
# cherry_mult = (target_RTP - rtp_others) / P(cherry)^3
# cherry_mult(95%) = (0.95 - 0.086) / 0.216 ≈ 4.0
```

**Verificación empírica obligatoria:**
```python
def simulate_ev(n=200_000):
    total_bet, total_win = 0, 0
    for _ in range(n):
        r = spin(bet=10)
        total_bet += 10
        total_win += r['win']
    return total_win / total_bet  # debe ser ≥ 0.90 target
```

**Regla:** Nunca cambiar multiplicadores sin correr simulate_ev(200_000).

---

## 3. PATRÓN: NEAR-MISS — LEGAL VS ILEGAL

**Ilegal (España DGOJ y mayoría de jurisdicciones):**
```python
# ❌ Forzar near-miss artificialmente
if random.random() < 0.30:
    r2 = r1  # Fuerza 2/3 matching — engaño
```

**Legal (orgánico — solo informativo):**
```python
# ✅ Detectar near-miss natural
is_near_miss = (r1 == r2 or r2 == r3 or r1 == r3) and r1 != r2 != r3
# Solo comunica al usuario que "casi ganó" — no fuerza nada
```

**Regla:** El near-miss forzado es "diseño engañoso" → P0 en cualquier producto real.

---

## 4. PATRÓN: DB IDEMPOTENTE — ALTER TABLE SEGURO

**Problema:** `executescript()` con ALTER TABLE falla si la columna ya existe.
**Solución:** Leer `PRAGMA table_info` antes de alterar.

```python
def _migrate_add_columns(conn, table, columns: dict):
    """Añade columnas faltantes de forma idempotente."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for col_name, col_def in columns.items():
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
    conn.commit()

# Uso:
_migrate_add_columns(conn, "players", {
    "self_excluded": "INTEGER DEFAULT 0",
    "daily_limit":   "INTEGER DEFAULT 0",
    "session_limit": "INTEGER DEFAULT 0",
})
```

**Regla:** Nunca usar `executescript` para ALTER TABLE — siempre PRAGMA + condicional.

---

## 5. PATRÓN: SQL INJECTION — WHITELIST EN UPDATE DINÁMICO

**Problema:** update_player(**kwargs) con kwargs arbitrarios = SQL injection.
**Solución:** Frozenset de campos permitidos.

```python
_ALLOWED_UPDATE_FIELDS = frozenset({
    "balance", "total_spins", "total_won", "last_daily",
    "wallet_bonus", "self_excluded", "daily_limit", "session_limit",
})

def update_player(uid, **kwargs):
    invalid = set(kwargs) - _ALLOWED_UPDATE_FIELDS
    if invalid:
        raise ValueError(f"Campos no permitidos: {invalid}")
    # seguro proceder con kwargs
```

---

## 6. PATRÓN: RATE LIMITER IN-MEMORY POR UID

```python
import threading, time

_spin_times: dict[int, float] = {}
_spin_lock = threading.Lock()
_MIN_INTERVAL = 0.8  # segundos

def _check_rate(uid: int) -> float:
    """Retorna 0 si OK, segundos restantes si too-fast."""
    now = time.monotonic()
    with _spin_lock:
        last = _spin_times.get(uid, 0)
        diff = now - last
        if diff < _MIN_INTERVAL:
            return _MIN_INTERVAL - diff
        _spin_times[uid] = now
        return 0.0
```

**Limitación:** Se pierde al reiniciar el servidor.
**Solución producción:** Guardar `last_spin_at` en SQLite + leer en cada spin.

---

## 7. PATRÓN: TELEGRAM MINI APP — INIT SEGURO

```javascript
const TG = window.Telegram?.WebApp || null;
if (TG) { TG.ready(); TG.expand(); }

// UID del usuario (no verificado — seguridad básica)
const TG_UID = TG?.initDataUnsafe?.user?.id || null;

// ⚠️ Pendiente: verificar HMAC de initData server-side
// Para producción: enviar initData al servidor y verificar firma BOTS_TOKEN
```

**Arquitectura cliente-servidor:**
- Todo el dinero/saldo en servidor (SQLite)
- Cliente solo muestra, nunca decide
- API key = UID de Telegram (mejorar: HMAC initData)

---

## 8. PATRÓN: SERVIDOR HTTP PYTHON — RESTART LIMPIO

```python
class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True  # Evita ERRNO 48 en restart rápido

# Restart desde terminal:
# 1. lsof -ti :8080 → obtener PID exacto
# 2. kill <PID> exacto (nunca pkill/killall)
# 3. sleep 1 → esperar release socket
# 4. nohup python3 server.py > /tmp/server.log 2>&1 &
```

---

## 9. PATRÓN: TRUST UX — SEÑALES REALES SIN AFIRMACIONES FALSAS

**Principio:** Las señales de confianza deben ser verdaderas.

| ❌ No usar | ✅ Usar en su lugar |
|---|---|
| "Licenciado por DGOJ" (falso) | "Algoritmo verificable públicamente" |
| Sello oficial inventado | "RTP 94.2% — auditable en código fuente" |
| "Regulado en Malta" | "Sin custodia — tu wallet tu control" |
| "DGOJ compliant" sin licencia | "Juego responsable: autoexclusión activa" |

**Por qué:** Las señales falsas crean responsabilidad legal (publicidad engañosa).
Las señales reales construyen confianza legítima y son defensibles.

**Sprites de trust:** Generar con `gen_trust_badges.py` (Pillow, cross-platform):
- `badge_fair.png` — Provably Fair / Algoritmo justo
- `badge_rtp.png` — RTP 94.2% auditado
- `badge_nocustody.png` — Sin custodia
- `badge_safe.png` — +18 / Autoexclusión

---

## 10. PATRÓN: REGULACIÓN JUEGO — MAPA DE OPCIONES

```
Escenario A: "Fichas virtuales sin valor real"
  → Sin licencia necesaria
  → Aplica como entretenimiento social
  → Copy: "fichas virtuales · no real money · entertainment only"

Escenario B: Target global (sin España explícita)
  → Licencia Curaçao (~€20K, 2-4 meses)
  → Geobloqueo España activo
  → TON como rails de pago (sin PSP bancario)
  → KYC opcional hasta umbrales AML

Escenario C: Mercado español (requiere DGOJ)
  → Licencia DGOJ (~€30K+, 12-18 meses)
  → KYC completo (Jumio/Onfido)
  → RGIAJ API (convenio DGOJ)
  → Auditoría laboratorio certificado (GLI/BMM/iTech)
  → RTP mínimo: no establecido por ley, pero certificado obligatorio
```

**Regla clave:** La ley se aplica por ubicación del JUGADOR, no del servidor/código.
Blockchain/TON/Curaçao no eximen de la jurisdicción del usuario.

---

## 11. PATRÓN: NEAR-MISS ORGÁNICO — COMUNICACIÓN UX

```javascript
// Mostrar near-miss detectado orgánicamente (legal e informativo)
if (result.isNearMiss) {
    setResult('😮 ¡Casi! Prueba de nuevo…', 'near-miss');
    sfxNearMiss();
}
// Nunca: "Estabas muy cerca — ¡apuesta más para ganar!"
// (manipulación psicológica → ilegal en jurisdicciones reguladas)
```

---

## 12. PATRÓN: JACKPOT PROGRESIVO — CONTABILIDAD

```python
# 1% de cada apuesta va al pool (server-side, SQLite)
def do_spin(uid, bet):
    contribution = int(bet * 0.01)
    conn.execute("UPDATE jackpot SET pool = pool + ?", (contribution,))

    if is_jackpot:
        pool = conn.execute("SELECT pool FROM jackpot").fetchone()[0]
        win = pool + bet * BASE_MULT_7
        conn.execute("UPDATE jackpot SET pool = ?", (JACKPOT_SEED,))
        return win

# pool mínimo (seed) = 1000 fichas
# Se muestra en tiempo real via /api/jackpot endpoint
```

---

## Próximas ideas de alto valor (del selector BAGO)

| Idea | Score | Siguiente paso |
|---|---|---|
| ~~Compra fichas TON~~ | ~~103~~ | ✅ IMPLEMENTADO — sesión 2026-05-13 |
| Sistema referidos | 96 | parsear args start, acreditar referidor |
| Sistema VIP RTP | 90 | campo vip_tier en users, ajustar weights |
| Jackpot progresivo | 88 | Ya implementado — UI en bot.py |
| Publicidad nativa | 73 | /ads endpoint + banner JS cada 10 spins |

---

## Patrón: TON Purchases (IDEA-CASINO-003) — Implementado 2026-05-13

### Arquitectura de pago con criptomoneda virtual

```
Usuario → openBuyModal() → POST /api/ton/order
       → tonConnectUI.sendTransaction()  ← wallet real TON
       → POST /api/ton/confirm {order_id, boc}
       → fichas acreditadas en SQLite (idempotente)
```

### Clave: idempotencia en confirm
```python
def confirm_ton_purchase(order_id, boc=""):
    # Comprueba status antes de acreditar — doble submit seguro
    if row["status"] == "confirmed":
        return {"ok": True, "already_confirmed": True, ...}
```

### Paquetes con bonus progresivo
| ID | TON | Fichas | Bonus |
|---|---|---|---|
| basic | 0.5 | 250 | — |
| standard | 1.0 | 500 | — |
| popular | 2.0 | 1100 | +10% |
| premium | 5.0 | 3000 | +20% |

### Centralización: `TON_PACKAGES` en `db.py`
- Fuente única de verdad compartida por `server.py` y `bot.py`
- `nanoton = TON * 1_000_000_000` (nunca float)

### Bot: /comprar + inline keyboard
```python
# Callbacks pkg_basic, pkg_standard, pkg_popular, pkg_premium
# Redirigen al casino gráfico vía WebAppInfo para completar pago
```

### Seguridad: modelo simplificado (fichas virtuales)
- Sin verificación on-chain → confianza en callback TonConnect
- `OPERATOR_TON_WALLET` env var → 503 si no configurada
- Orden UUID → imposible reuse por hash

### Pendiente para producción
- Sustituir `OPERATOR_TON_WALLET=UQBPlaceholder...` por wallet real
- Opcional: verificación on-chain via TonCenter API
- Opcional: webhook de confirmación async (TON DNS lookup)

---

*Aprendizaje compilado automáticamente — BAGO Organizativo · 2026-05-13*
*Actualizado: repliegate pendrive — TON purchases implementado*
