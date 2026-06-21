"""
db.py — Capa de persistencia SQLite para Casino BAGO.

Tablas:
  players       → saldo, apuesta, estadísticas, referidos, VIP
  jackpot_pool  → pozo compartido progresivo
  referrals     → historial de referidos
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "casino.db")

# ─── Paquetes TON (1 TON = 1_000_000_000 nanoTON) ────────────────────────────
TON_PACKAGES = {
    "basic":    {"ton": 0.5, "nanoton": 500_000_000,  "fichas": 250,  "label": "🟢 Básico",   "bonus": ""},
    "standard": {"ton": 1.0, "nanoton": 1_000_000_000, "fichas": 500,  "label": "🔵 Estándar", "bonus": ""},
    "popular":  {"ton": 2.0, "nanoton": 2_000_000_000, "fichas": 1100, "label": "🟣 Popular",  "bonus": "+10%"},
    "premium":  {"ton": 5.0, "nanoton": 5_000_000_000, "fichas": 3000, "label": "🔴 Premium",  "bonus": "+20%"},
}

_DEFAULT_BALANCE = 500
_DAILY_BONUS = 50
_REFERRAL_BONUS = 50
_JACKPOT_SEED = 1000
_JACKPOT_PCT = 0.01  # 1% de cada apuesta al pozo

# Campos permitidos en update_player (whitelist contra inyección SQL)
_ALLOWED_UPDATE_FIELDS = frozenset({
    "balance", "bet", "total_spins", "total_won", "total_spent",
    "vip_tier", "username", "wallet_address", "wallet_bonus",
    "last_daily", "referred_by", "referral_count",
    "self_excluded", "daily_limit", "session_limit",
})


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS players (
            uid              INTEGER PRIMARY KEY,
            username         TEXT,
            balance          INTEGER DEFAULT {_DEFAULT_BALANCE},
            bet              INTEGER DEFAULT 10,
            total_spins      INTEGER DEFAULT 0,
            total_won        INTEGER DEFAULT 0,
            total_spent      INTEGER DEFAULT 0,
            vip_tier         INTEGER DEFAULT 0,
            referred_by      INTEGER DEFAULT NULL,
            referral_count   INTEGER DEFAULT 0,
            wallet_address   TEXT    DEFAULT NULL,
            wallet_bonus     INTEGER DEFAULT 0,
            last_daily       TEXT    DEFAULT NULL,
            self_excluded    INTEGER DEFAULT 0,
            daily_limit      INTEGER DEFAULT 0,
            session_limit    INTEGER DEFAULT 0,
            created_at       TEXT    DEFAULT (datetime('now')),
            updated_at       TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jackpot_pool (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            amount  INTEGER DEFAULT {_JACKPOT_SEED}
        );
        INSERT OR IGNORE INTO jackpot_pool (id, amount) VALUES (1, {_JACKPOT_SEED});

        CREATE TABLE IF NOT EXISTS referrals (
            referrer_uid  INTEGER NOT NULL,
            referred_uid  INTEGER PRIMARY KEY,
            bonus_paid    INTEGER DEFAULT 0,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ton_transactions (
            order_id      TEXT    PRIMARY KEY,
            uid           INTEGER NOT NULL,
            package_id    TEXT    NOT NULL,
            amount_nanoton INTEGER NOT NULL,
            fichas        INTEGER NOT NULL,
            status        TEXT    DEFAULT 'pending',
            tx_boc        TEXT    DEFAULT NULL,
            created_at    TEXT    DEFAULT (datetime('now')),
            confirmed_at  TEXT    DEFAULT NULL
        );
        """)

    # Migración incremental: añadir columnas nuevas si no existen (idempotente)
    _migrate_add_columns(conn, "players", [
        ("self_excluded", "INTEGER DEFAULT 0"),
        ("daily_limit",   "INTEGER DEFAULT 0"),
        ("session_limit", "INTEGER DEFAULT 0"),
    ])


def _migrate_add_columns(conn, table: str, columns: list[tuple]) -> None:
    """Añade columnas a una tabla si no existen (migración idempotente)."""
    with _connect() as c:
        existing = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
        for col_name, col_def in columns:
            if col_name not in existing:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")


# ─── Players ──────────────────────────────────────────────────────────────────

def ensure_player(uid: int, username: str = "", referred_by: int = None) -> dict:
    """Obtiene o crea el jugador. Devuelve dict con todos sus campos."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone()
        if row:
            if username:
                conn.execute(
                    "UPDATE players SET username = ?, updated_at = datetime('now') WHERE uid = ?",
                    (username, uid),
                )
            return dict(conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone())

        # Nuevo jugador
        conn.execute(
            "INSERT INTO players (uid, username, referred_by) VALUES (?, ?, ?)",
            (uid, username or f"user_{uid}", referred_by),
        )

        # Pagar bonus de referido al referidor
        if referred_by and referred_by != uid:
            conn.execute(
                "INSERT OR IGNORE INTO referrals (referrer_uid, referred_uid, bonus_paid) VALUES (?, ?, ?)",
                (referred_by, uid, _REFERRAL_BONUS),
            )
            conn.execute(
                "UPDATE players SET balance = balance + ?, referral_count = referral_count + 1, "
                "updated_at = datetime('now') WHERE uid = ?",
                (_REFERRAL_BONUS, referred_by),
            )

        return dict(conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone())


def get_player(uid: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone()
        return dict(row) if row else None


def update_player(uid: int, **kwargs) -> None:
    if not kwargs:
        return
    # Whitelist de campos para prevenir SQL injection
    invalid = set(kwargs) - _ALLOWED_UPDATE_FIELDS
    if invalid:
        raise ValueError(f"Campos no permitidos: {invalid}")
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    cols += ", updated_at = datetime('now')"
    vals = list(kwargs.values()) + [uid]
    with _connect() as conn:
        conn.execute(f"UPDATE players SET {cols} WHERE uid = ?", vals)


# ─── Spin (server-side, house edge garantizado) ───────────────────────────────

def do_spin(uid: int, bet: int) -> dict:
    """
    Ejecuta un giro completo de forma transaccional.
    Devuelve el resultado + estado actualizado del jugador.
    """
    from slot_engine import spin as engine_spin

    p = get_player(uid)
    if p is None:
        return {"error": "player_not_found"}
    if p.get("self_excluded"):
        return {"error": "self_excluded", "message": "Has activado la autoexclusión. Contacta soporte para reactivar."}
    if p["balance"] < bet:
        return {"error": "insufficient_balance", "balance": p["balance"]}

    # Giro
    result = engine_spin(bet)

    # Contribución al jackpot progresivo (antes de verificar si lo ganó)
    jackpot_contribution = max(1, int(bet * _JACKPOT_PCT))
    jackpot_amount = add_to_jackpot(jackpot_contribution)

    # ¿Jackpot progresivo (777)? → pagar el pozo acumulado
    progressive_jackpot = 0
    if result.is_jackpot:
        progressive_jackpot = jackpot_amount
        reset_jackpot(_JACKPOT_SEED)
        jackpot_amount = _JACKPOT_SEED

    total_win = result.win + progressive_jackpot
    new_balance = p["balance"] - bet + total_win

    # VIP tier update (por saldo acumulado gastado)
    new_spent = p["total_spent"] + bet
    vip_tier = 0
    if new_spent >= 10000:
        vip_tier = 2
    elif new_spent >= 2000:
        vip_tier = 1

    update_player(
        uid,
        balance=new_balance,
        bet=bet,
        total_spins=p["total_spins"] + 1,
        total_won=p["total_won"] + total_win,
        total_spent=new_spent,
        vip_tier=vip_tier,
    )

    return {
        "reels": list(result.reels),
        "win": total_win,
        "base_win": result.win,
        "progressive_jackpot": progressive_jackpot,
        "message": result.message,
        "is_jackpot": result.is_jackpot,
        "is_near_miss": result.is_near_miss,
        "balance": new_balance,
        "jackpot_pool": jackpot_amount,
        "vip_tier": vip_tier,
    }


# ─── Wallet bonus (atómico, una sola vez) ─────────────────────────────────────

def apply_wallet_bonus(uid: int, bonus: int = 100) -> dict:
    """Otorga bonus de cartera si no se ha dado ya. Devuelve el jugador actualizado."""
    with _connect() as conn:
        row = conn.execute("SELECT wallet_bonus, balance FROM players WHERE uid = ?", (uid,)).fetchone()
        if row and row["wallet_bonus"] == 0:
            conn.execute(
                "UPDATE players SET wallet_bonus = ?, balance = balance + ?, updated_at = datetime('now') WHERE uid = ?",
                (bonus, bonus, uid),
            )
        return dict(conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone())


# ─── Auto-exclusión (DGOJ obligatorio) ────────────────────────────────────────

def self_exclude(uid: int) -> dict:
    """Activa la autoexclusión del jugador. Solo soporte puede revertirla."""
    with _connect() as conn:
        conn.execute(
            "UPDATE players SET self_excluded = 1, updated_at = datetime('now') WHERE uid = ?",
            (uid,),
        )
        row = conn.execute("SELECT * FROM players WHERE uid = ?", (uid,)).fetchone()
        return dict(row) if row else {}


# ─── Daily bonus ──────────────────────────────────────────────────────────────

def claim_daily(uid: int) -> dict:
    """Otorga giros gratis diarios. Devuelve {granted, balance, hours_left}."""
    p = get_player(uid)
    if p is None:
        return {"error": "player_not_found"}

    now = datetime.now(timezone.utc)
    last = p.get("last_daily")

    if last:
        last_dt = datetime.fromisoformat(last).replace(tzinfo=timezone.utc)
        elapsed = (now - last_dt).total_seconds()
        if elapsed < 86400:
            hours_left = (86400 - elapsed) / 3600
            return {"granted": False, "hours_left": round(hours_left, 1), "balance": p["balance"]}

    new_balance = p["balance"] + _DAILY_BONUS
    update_player(uid, balance=new_balance, last_daily=now.isoformat())
    return {"granted": True, "bonus": _DAILY_BONUS, "balance": new_balance}


# ─── Jackpot pool ─────────────────────────────────────────────────────────────

def get_jackpot() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT amount FROM jackpot_pool WHERE id = 1").fetchone()
        return row["amount"] if row else _JACKPOT_SEED


def add_to_jackpot(amount: int) -> int:
    with _connect() as conn:
        conn.execute("UPDATE jackpot_pool SET amount = amount + ? WHERE id = 1", (amount,))
        return conn.execute("SELECT amount FROM jackpot_pool WHERE id = 1").fetchone()["amount"]


def reset_jackpot(seed: int = _JACKPOT_SEED) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jackpot_pool SET amount = ? WHERE id = 1", (seed,))


# ─── Leaderboard ──────────────────────────────────────────────────────────────

def get_leaderboard(limit: int = 10) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT uid, username, balance, total_spins, vip_tier "
            "FROM players ORDER BY balance DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── TON purchases ────────────────────────────────────────────────────────────

def create_ton_order(uid: int, package_id: str) -> dict:
    """Crea una orden de compra TON pendiente. Devuelve la orden o error."""
    pkg = TON_PACKAGES.get(package_id)
    if not pkg:
        return {"error": f"package_not_found: {package_id}"}

    order_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO ton_transactions (order_id, uid, package_id, amount_nanoton, fichas) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, uid, package_id, pkg["nanoton"], pkg["fichas"]),
        )
    return {
        "order_id": order_id,
        "uid": uid,
        "package_id": package_id,
        "amount_nanoton": pkg["nanoton"],
        "ton": pkg["ton"],
        "fichas": pkg["fichas"],
        "label": pkg["label"],
        "bonus": pkg["bonus"],
    }


def confirm_ton_purchase(order_id: str, boc: str = "") -> dict:
    """
    Confirma una orden TON y acredita fichas al jugador.
    Idempotente: si ya está 'confirmed' devuelve el estado sin volver a acreditar.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM ton_transactions WHERE order_id = ?", (order_id,)
        ).fetchone()

        if not row:
            return {"error": "order_not_found"}

        order = dict(row)

        if order["status"] == "confirmed":
            player = get_player(order["uid"])
            return {
                "ok": True,
                "already_confirmed": True,
                "fichas_added": order["fichas"],
                "balance": player["balance"] if player else 0,
            }

        if order["status"] == "failed":
            return {"error": "order_already_failed"}

        # Acreditar fichas
        conn.execute(
            "UPDATE players SET balance = balance + ?, updated_at = datetime('now') WHERE uid = ?",
            (order["fichas"], order["uid"]),
        )
        conn.execute(
            "UPDATE ton_transactions SET status = 'confirmed', tx_boc = ?, "
            "confirmed_at = datetime('now') WHERE order_id = ?",
            (boc or "", order_id),
        )

    player = get_player(order["uid"])
    return {
        "ok": True,
        "already_confirmed": False,
        "fichas_added": order["fichas"],
        "balance": player["balance"] if player else 0,
        "package_id": order["package_id"],
    }


def get_ton_orders(uid: int, limit: int = 10) -> list[dict]:
    """Historial de órdenes TON de un usuario."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT order_id, package_id, amount_nanoton, fichas, status, created_at, confirmed_at "
            "FROM ton_transactions WHERE uid = ? ORDER BY created_at DESC LIMIT ?",
            (uid, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# Inicializar la BD al importar
init_db()
