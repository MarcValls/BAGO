"""Execution coordination claims for the governed runtime."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
import weakref
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar


class ExecutionClaimError(RuntimeError):
    """A claim is stale, invalid, or no longer owns its resource."""

    def __init__(self, message: str, *, code: str = "execution_claim_invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    claim_id: str
    resource_key: str
    operation_id: str
    owner_id: str
    lease_until: float
    fencing_token: int
    status: str = "ACTIVE"
    created_at: str = ""
    renewed_at: str = ""
    released_at: str = ""


def coerce_execution_claim(value: Any) -> ExecutionClaim:
    """Normalize an internal claim across duplicate hidden-module imports."""
    if isinstance(value, ExecutionClaim):
        return value
    try:
        return ExecutionClaim(
            claim_id=str(value.claim_id),
            resource_key=str(value.resource_key),
            operation_id=str(value.operation_id),
            owner_id=str(value.owner_id),
            lease_until=float(value.lease_until),
            fencing_token=int(value.fencing_token),
            status=str(value.status),
            created_at=str(value.created_at),
            renewed_at=str(value.renewed_at),
            released_at=str(value.released_at),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Nested child requires a valid gateway-owned execution claim") from exc


_Result = TypeVar("_Result")


class ExecutionClaimStore(Protocol):
    """Stable coordination API; implementations declare their durability scope."""

    durability: str

    def try_acquire(
        self, resource_key: str, owner_id: str, operation_id: str, *, lease_seconds: float = 60.0
    ) -> ExecutionClaim | None: ...

    def renew(self, claim: ExecutionClaim, *, lease_seconds: float = 60.0) -> ExecutionClaim | None: ...

    def release(self, claim: ExecutionClaim) -> bool: ...

    def validate(self, claim: ExecutionClaim) -> bool: ...

    def expire(self) -> int: ...

    def execute_if_valid(self, claim: ExecutionClaim, operation: Callable[[], _Result]) -> _Result: ...


class InMemoryExecutionClaimStore:
    """Thread-safe, per-resource claims for a single running BAGO process."""

    durability = "process-local"

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._guard = threading.RLock()
        self._claims: dict[str, ExecutionClaim] = {}
        self._fencing: dict[str, int] = {}
        self._effect_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()

    def _effect_lock(self, resource_key: str) -> threading.Lock:
        with self._guard:
            lock = self._effect_locks.get(resource_key)
            if lock is None:
                lock = threading.Lock()
                self._effect_locks[resource_key] = lock
            return lock

    @staticmethod
    def _utc(value: float | None = None) -> str:
        return datetime.fromtimestamp(value if value is not None else time.time(), timezone.utc).isoformat()

    @staticmethod
    def _valid_identity(resource_key: str, owner_id: str, operation_id: str) -> bool:
        return bool(resource_key.strip() and owner_id.strip() and operation_id.strip())

    def try_acquire(
        self, resource_key: str, owner_id: str, operation_id: str, *, lease_seconds: float = 60.0
    ) -> ExecutionClaim | None:
        resource_key, owner_id, operation_id = resource_key.strip(), owner_id.strip(), operation_id.strip()
        if not self._valid_identity(resource_key, owner_id, operation_id):
            raise ValueError("resource_key, owner_id y operation_id son obligatorios")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser positivo")
        now = self._clock()
        with self._guard:
            current = self._claims.get(resource_key)
            if current and current.status == "ACTIVE" and current.lease_until > now:
                return None
            # Do not transfer an expired claim while its material effect is in
            # progress. A stale caller is rejected at execute_if_valid; a new
            # owner can acquire once that bounded effect has left the sink.
            effect_lock = self._effect_lock(resource_key)
            if current and current.status == "ACTIVE" and not effect_lock.acquire(blocking=False):
                return None
            if current and current.status == "ACTIVE":
                effect_lock.release()
            generation = self._fencing.get(resource_key, 0) + 1
            self._fencing[resource_key] = generation
            claim = ExecutionClaim(
                claim_id=str(uuid.uuid4()),
                resource_key=resource_key,
                operation_id=operation_id,
                owner_id=owner_id,
                lease_until=now + lease_seconds,
                fencing_token=generation,
                created_at=self._utc(now),
                renewed_at=self._utc(now),
            )
            self._claims[resource_key] = claim
            return claim

    def renew(self, claim: ExecutionClaim, *, lease_seconds: float = 60.0) -> ExecutionClaim | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser positivo")
        now = self._clock()
        with self._guard:
            current = self._claims.get(claim.resource_key)
            if not self._matches(current, claim) or current.lease_until <= now:
                return None
            renewed = replace(current, lease_until=now + lease_seconds, renewed_at=self._utc(now))
            self._claims[claim.resource_key] = renewed
            return renewed

    def release(self, claim: ExecutionClaim) -> bool:
        with self._guard:
            effect_lock = self._effect_lock(claim.resource_key)
        with effect_lock:
            with self._guard:
                current = self._claims.get(claim.resource_key)
                if not self._matches(current, claim):
                    return False
                assert current is not None
                self._claims[claim.resource_key] = replace(
                    current, status="RELEASED", released_at=self._utc(self._clock())
                )
                return True

    def validate(self, claim: ExecutionClaim) -> bool:
        with self._guard:
            current = self._claims.get(claim.resource_key)
            return bool(self._matches(current, claim) and current.lease_until > self._clock())

    def expire(self) -> int:
        now = self._clock()
        expired = 0
        with self._guard:
            for resource_key, current in list(self._claims.items()):
                if current.status == "ACTIVE" and current.lease_until <= now:
                    effect_lock = self._effect_lock(resource_key)
                    if not effect_lock.acquire(blocking=False):
                        # The lease elapsed while the gateway was inside the
                        # material adapter. Keep the claim current until that
                        # effect exits; otherwise a newer fencing generation
                        # could be issued while the old effect is still running.
                        continue
                    effect_lock.release()
                    self._claims[resource_key] = replace(
                        current, status="EXPIRED", released_at=self._utc(now)
                    )
                    expired += 1
        return expired

    def execute_if_valid(self, claim: ExecutionClaim, operation: Callable[[], _Result]) -> _Result:
        with self._guard:
            effect_lock = self._effect_lock(claim.resource_key)
        with effect_lock:
            if not self.validate(claim):
                raise ExecutionClaimError("Execution claim expired or fenced", code="execution_claim_stale")
            return operation()

    @staticmethod
    def _matches(current: ExecutionClaim | None, claim: ExecutionClaim) -> bool:
        return bool(
            current
            and current.status == "ACTIVE"
            and current.claim_id == claim.claim_id
            and current.operation_id == claim.operation_id
            and current.owner_id == claim.owner_id
            and current.fencing_token == claim.fencing_token
        )


class SQLiteExecutionClaimStore:
    """Durable local claims shared by BAGO processes using one SQLite file.

    A material adapter runs inside ``BEGIN IMMEDIATE`` in
    :meth:`execute_if_valid`. SQLite therefore cannot issue a replacement
    fencing generation while that adapter is still running. SQLite has one
    writer per database, so this deliberately serializes material callbacks
    across resources; claim ownership itself remains keyed per resource.
    """

    durability = "durable-local"

    def __init__(self, db_path: str | os.PathLike[str], *, clock: Callable[[], float] = time.time) -> None:
        from pathlib import Path

        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _init_db(self) -> None:
        connection = self._connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_claims (
                    resource_key TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL,
                    claim_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    lease_until REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    renewed_at TEXT NOT NULL,
                    released_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_execution_claims_lease "
                "ON execution_claims(status, lease_until)"
            )
        finally:
            connection.close()

    @staticmethod
    def _row_matches(row: sqlite3.Row | None, claim: ExecutionClaim) -> bool:
        return bool(
            row
            and row["status"] == "ACTIVE"
            and row["resource_key"] == claim.resource_key
            and row["claim_id"] == claim.claim_id
            and row["operation_id"] == claim.operation_id
            and row["owner_id"] == claim.owner_id
            and int(row["generation"]) == claim.fencing_token
        )

    @staticmethod
    def _claim(row: sqlite3.Row) -> ExecutionClaim:
        return ExecutionClaim(
            claim_id=str(row["claim_id"]),
            resource_key=str(row["resource_key"]),
            operation_id=str(row["operation_id"]),
            owner_id=str(row["owner_id"]),
            lease_until=float(row["lease_until"]),
            fencing_token=int(row["generation"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            renewed_at=str(row["renewed_at"]),
            released_at=str(row["released_at"]),
        )

    def try_acquire(
        self, resource_key: str, owner_id: str, operation_id: str, *, lease_seconds: float = 60.0
    ) -> ExecutionClaim | None:
        resource_key, owner_id, operation_id = resource_key.strip(), owner_id.strip(), operation_id.strip()
        if not InMemoryExecutionClaimStore._valid_identity(resource_key, owner_id, operation_id):
            raise ValueError("resource_key, owner_id y operation_id son obligatorios")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser positivo")
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM execution_claims WHERE resource_key=?", (resource_key,)
            ).fetchone()
            if row and row["status"] == "ACTIVE" and float(row["lease_until"]) > now:
                connection.commit()
                return None
            generation = int(row["generation"]) + 1 if row else 1
            claim = ExecutionClaim(
                claim_id=str(uuid.uuid4()),
                resource_key=resource_key,
                operation_id=operation_id,
                owner_id=owner_id,
                lease_until=now + lease_seconds,
                fencing_token=generation,
                created_at=InMemoryExecutionClaimStore._utc(now),
                renewed_at=InMemoryExecutionClaimStore._utc(now),
            )
            connection.execute(
                """INSERT INTO execution_claims
                   (resource_key,generation,claim_id,operation_id,owner_id,lease_until,
                    status,created_at,renewed_at,released_at)
                   VALUES (?,?,?,?,?,?, 'ACTIVE', ?,?, '')
                   ON CONFLICT(resource_key) DO UPDATE SET
                     generation=excluded.generation, claim_id=excluded.claim_id,
                     operation_id=excluded.operation_id, owner_id=excluded.owner_id,
                     lease_until=excluded.lease_until, status='ACTIVE',
                     created_at=excluded.created_at, renewed_at=excluded.renewed_at,
                     released_at=''
                """,
                (
                    claim.resource_key, claim.fencing_token, claim.claim_id,
                    claim.operation_id, claim.owner_id, claim.lease_until,
                    claim.created_at, claim.renewed_at,
                ),
            )
            connection.commit()
            return claim
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def renew(self, claim: ExecutionClaim, *, lease_seconds: float = 60.0) -> ExecutionClaim | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser positivo")
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM execution_claims WHERE resource_key=?", (claim.resource_key,)
            ).fetchone()
            if not self._row_matches(row, claim) or float(row["lease_until"]) <= now:
                connection.commit()
                return None
            renewed = replace(claim, lease_until=now + lease_seconds,
                              renewed_at=InMemoryExecutionClaimStore._utc(now))
            connection.execute(
                "UPDATE execution_claims SET lease_until=?,renewed_at=? WHERE resource_key=?",
                (renewed.lease_until, renewed.renewed_at, renewed.resource_key),
            )
            connection.commit()
            return renewed
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def release(self, claim: ExecutionClaim) -> bool:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM execution_claims WHERE resource_key=?", (claim.resource_key,)
            ).fetchone()
            if not self._row_matches(row, claim):
                connection.commit()
                return False
            connection.execute(
                "UPDATE execution_claims SET status='RELEASED',released_at=? WHERE resource_key=?",
                (InMemoryExecutionClaimStore._utc(self._clock()), claim.resource_key),
            )
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def validate(self, claim: ExecutionClaim) -> bool:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM execution_claims WHERE resource_key=?", (claim.resource_key,)
            ).fetchone()
            return bool(self._row_matches(row, claim) and float(row["lease_until"]) > self._clock())
        finally:
            connection.close()

    def expire(self) -> int:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE execution_claims SET status='EXPIRED',released_at=? "
                "WHERE status='ACTIVE' AND lease_until<=?",
                (InMemoryExecutionClaimStore._utc(now), now),
            )
            connection.commit()
            return int(cursor.rowcount)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute_if_valid(self, claim: ExecutionClaim, operation: Callable[[], _Result]) -> _Result:
        """Fence an effect with the durable lease.

        SQLite permits one writer per database. Holding its write transaction
        across the callback therefore serializes effects using this database,
        including effects on unrelated resource keys. This is a local
        correctness boundary, not the final high-concurrency/distributed design.
        """
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM execution_claims WHERE resource_key=?", (claim.resource_key,)
            ).fetchone()
            if not self._row_matches(row, claim) or float(row["lease_until"]) <= self._clock():
                connection.rollback()
                raise ExecutionClaimError("Execution claim expired or fenced", code="execution_claim_stale")
            result = operation()
            connection.commit()
            return result
        except ExecutionClaimError:
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class PostgresExecutionClaimStore:
    """Distributed claim rows stored in a shared PostgreSQL service.

    A caller may inject a DB-API connector for its configured psycopg runtime.
    Without one, psycopg 3 is loaded lazily. Holding ``SELECT FOR UPDATE``
    across a material callback orders lease transfer for this resource, but a
    distributed sink must still enforce the fencing token itself if a worker
    can continue after losing its database connection.
    """

    durability = "durable-distributed-claims"
    requires_sink_fencing = True

    def __init__(self, dsn: str = "", *, connector: Callable[[], Any] | None = None) -> None:
        if connector is not None:
            self._connector = connector
        else:
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PostgresExecutionClaimStore requiere psycopg 3") from exc
            if not dsn.strip():
                raise ValueError("PostgresExecutionClaimStore requiere DSN")
            self._connector = lambda: psycopg.connect(dsn)
        self._init_db()

    @staticmethod
    def _dict_row(cursor: Any, row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        names = [column.name if hasattr(column, "name") else column[0] for column in cursor.description]
        return dict(zip(names, row))

    @classmethod
    def _claim(cls, cursor: Any, row: Any) -> ExecutionClaim | None:
        values = cls._dict_row(cursor, row)
        if values is None:
            return None
        def timestamp(name: str) -> str:
            value = values.get(name)
            return value.isoformat() if hasattr(value, "isoformat") else str(value or "")
        return ExecutionClaim(
            claim_id=str(values["claim_id"]),
            resource_key=str(values["resource_key"]),
            operation_id=str(values["operation_id"]),
            owner_id=str(values["owner_id"]),
            lease_until=float(values["lease_until_epoch"]),
            fencing_token=int(values["generation"]),
            status=str(values["status"]),
            created_at=timestamp("created_at"),
            renewed_at=timestamp("renewed_at"),
            released_at=timestamp("released_at"),
        )

    def _init_db(self) -> None:
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS bago_execution_claims (
                        resource_key TEXT PRIMARY KEY,
                        generation BIGINT NOT NULL,
                        claim_id UUID NOT NULL,
                        operation_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        lease_until TIMESTAMPTZ NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        renewed_at TIMESTAMPTZ NOT NULL,
                        released_at TIMESTAMPTZ
                    )"""
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bago_execution_claims_lease "
                    "ON bago_execution_claims(status, lease_until)"
                )

    def try_acquire(
        self, resource_key: str, owner_id: str, operation_id: str, *, lease_seconds: float = 60.0
    ) -> ExecutionClaim | None:
        resource_key, owner_id, operation_id = resource_key.strip(), owner_id.strip(), operation_id.strip()
        if not InMemoryExecutionClaimStore._valid_identity(resource_key, owner_id, operation_id):
            raise ValueError("resource_key, owner_id y operation_id son obligatorios")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser positivo")
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO bago_execution_claims
                       (resource_key,generation,claim_id,operation_id,owner_id,lease_until,
                        status,created_at,renewed_at,released_at)
                       VALUES (%s,1,%s,%s,%s,clock_timestamp()+(%s * interval '1 second'),
                               'ACTIVE',clock_timestamp(),clock_timestamp(),NULL)
                       ON CONFLICT(resource_key) DO UPDATE SET
                         generation=bago_execution_claims.generation+1,
                         claim_id=EXCLUDED.claim_id, operation_id=EXCLUDED.operation_id,
                         owner_id=EXCLUDED.owner_id, lease_until=EXCLUDED.lease_until,
                         status='ACTIVE', created_at=clock_timestamp(),
                         renewed_at=clock_timestamp(), released_at=NULL
                       WHERE bago_execution_claims.status <> 'ACTIVE'
                          OR bago_execution_claims.lease_until <= clock_timestamp()
                       RETURNING resource_key,generation,claim_id,operation_id,owner_id,
                         lease_until,extract(epoch from lease_until) AS lease_until_epoch,
                         status,created_at,renewed_at,released_at""",
                    (resource_key, uuid.uuid4(), operation_id, owner_id, lease_seconds),
                )
                return self._claim(cursor, cursor.fetchone())

    def renew(self, claim: ExecutionClaim, *, lease_seconds: float = 60.0) -> ExecutionClaim | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds debe ser positivo")
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE bago_execution_claims SET
                         lease_until=clock_timestamp()+(%s * interval '1 second'),
                         renewed_at=clock_timestamp()
                       WHERE resource_key=%s AND claim_id=%s AND operation_id=%s
                         AND owner_id=%s AND generation=%s AND status='ACTIVE'
                         AND lease_until>clock_timestamp()
                       RETURNING resource_key,generation,claim_id,operation_id,owner_id,
                         lease_until,extract(epoch from lease_until) AS lease_until_epoch,
                         status,created_at,renewed_at,released_at""",
                    (lease_seconds, claim.resource_key, claim.claim_id, claim.operation_id,
                     claim.owner_id, claim.fencing_token),
                )
                return self._claim(cursor, cursor.fetchone())

    def release(self, claim: ExecutionClaim) -> bool:
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE bago_execution_claims SET status='RELEASED',released_at=clock_timestamp()
                       WHERE resource_key=%s AND claim_id=%s AND operation_id=%s AND owner_id=%s
                         AND generation=%s AND status='ACTIVE'""",
                    (claim.resource_key, claim.claim_id, claim.operation_id, claim.owner_id,
                     claim.fencing_token),
                )
                return cursor.rowcount == 1

    def validate(self, claim: ExecutionClaim) -> bool:
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT 1 FROM bago_execution_claims WHERE resource_key=%s AND claim_id=%s
                         AND operation_id=%s AND owner_id=%s AND generation=%s AND status='ACTIVE'
                         AND lease_until>clock_timestamp()""",
                    (claim.resource_key, claim.claim_id, claim.operation_id, claim.owner_id,
                     claim.fencing_token),
                )
                return cursor.fetchone() is not None

    def expire(self) -> int:
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE bago_execution_claims SET status='EXPIRED',released_at=clock_timestamp()
                       WHERE status='ACTIVE' AND lease_until<=clock_timestamp()"""
                )
                return int(cursor.rowcount)

    def execute_if_valid(self, claim: ExecutionClaim, operation: Callable[[], _Result]) -> _Result:
        with self._connector() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT resource_key,generation,claim_id,operation_id,owner_id,
                         lease_until,extract(epoch from lease_until) AS lease_until_epoch,
                         status,created_at,renewed_at,released_at
                       FROM bago_execution_claims WHERE resource_key=%s FOR UPDATE""",
                    (claim.resource_key,),
                )
                row = cursor.fetchone()
                current = self._claim(cursor, row)
                cursor.execute(
                    "SELECT lease_until>clock_timestamp() FROM bago_execution_claims WHERE resource_key=%s",
                    (claim.resource_key,),
                )
                valid_now = cursor.fetchone()
                if (
                    current is None or not self._same_claim(current, claim)
                    or valid_now is None or not valid_now[0]
                ):
                    raise ExecutionClaimError(
                        "Execution claim expired or fenced", code="execution_claim_stale"
                    )
                return operation()

    @staticmethod
    def _same_claim(current: ExecutionClaim, claim: ExecutionClaim) -> bool:
        return (
            current.status == "ACTIVE" and current.claim_id == claim.claim_id
            and current.operation_id == claim.operation_id and current.owner_id == claim.owner_id
            and current.fencing_token == claim.fencing_token
        )


def file_resource_key(path: str, manager: Any = None, *, effect_id: str = "filesystem.write") -> str:
    """Return the exact canonical key used by a governed file adapter."""
    from pathlib import Path

    if manager is None:
        raise ValueError("file resource requires a trusted manager")
    from filesystem_effects import _resolve_target, resolve_plan_read_path

    clean = str(path or "").strip()
    if not clean:
        raise ValueError("file resource path is required")
    if effect_id == "filesystem.write":
        candidate, _, _ = _resolve_target(manager, clean)
    elif effect_id == "filesystem.read":
        candidate = resolve_plan_read_path(manager, clean)
    else:
        raise ValueError(f"unsupported claim resource effect: {effect_id}")
    return "file:" + os.path.normcase(str(candidate.resolve(strict=False)))


def process_working_directory(target: dict[str, Any], manager: Any) -> Path:
    """Resolve a process cwd from the request or the trusted live workspace."""
    roots: list[Path] = []
    for name in ("base_path", "project_root"):
        value = str(getattr(manager, name, "") or "").strip()
        if not value:
            continue
        try:
            root = Path(value).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if root.is_dir() and root not in roots:
            roots.append(root)
    if not roots:
        raise ValueError("process resource requires a trusted workspace root")

    raw_cwd = str(target.get("cwd") or "").strip()
    candidate = Path(raw_cwd).expanduser() if raw_cwd else roots[0]
    if not candidate.is_absolute():
        candidate = roots[0] / candidate
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir() or not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError("process cwd is outside the active workspace")
    return resolved


def process_resource_key(
    target: dict[str, Any],
    arguments: Any,
    manager: Any,
    *,
    session_id: str,
) -> str:
    """Bind concurrent claims to one normalized process operation and cwd."""
    semantic_target = {
        str(key): value for key, value in target.items()
        if str(key) != "_pipeline"
    }
    if not str(semantic_target.get("command") or "").strip() and not str(
        semantic_target.get("executable") or ""
    ).strip():
        raise ValueError("process resource requires a command or executable")
    cwd = process_working_directory(semantic_target, manager)
    payload = json.dumps(
        {"target": semantic_target, "arguments": arguments, "cwd": str(cwd)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"process:{str(session_id).strip()}:{digest}"


def execution_resource_key(
    effect_id: str,
    target: dict[str, Any],
    arguments: Any,
    manager: Any,
    *,
    session_id: str,
) -> str:
    """Canonical concurrency key for effects supported by the claim store."""
    if effect_id in {"filesystem.read", "filesystem.write"}:
        return file_resource_key(
            str(target.get("path") or ""), manager, effect_id=effect_id
        )
    if effect_id == "process.execute":
        return process_resource_key(target, arguments, manager, session_id=session_id)
    raise ValueError(f"unsupported execution claim effect: {effect_id}")


DEFAULT_EXECUTION_CLAIM_STORE = InMemoryExecutionClaimStore()
_SQLITE_CLAIM_STORES: dict[str, ExecutionClaimStore] = {}
_SQLITE_CLAIM_STORES_LOCK = threading.RLock()


def execution_claim_store_for(manager: Any) -> ExecutionClaimStore:
    """Resolve coordination storage from a trusted manager's canonical state root."""
    raw_root = str(getattr(manager, "state_root", "") or "").strip()
    if not raw_root:
        # Lightweight harnesses without durable SessionManager state retain
        # the explicitly scoped process-local adapter.
        return DEFAULT_EXECUTION_CLAIM_STORE
    db_path = str((Path(raw_root).expanduser().resolve() / "execution_claims.sqlite3"))
    with _SQLITE_CLAIM_STORES_LOCK:
        store = _SQLITE_CLAIM_STORES.get(db_path)
        if store is None:
            store = SQLiteExecutionClaimStore(db_path)
            _SQLITE_CLAIM_STORES[db_path] = store
        return store


__all__ = [
    "DEFAULT_EXECUTION_CLAIM_STORE",
    "ExecutionClaim",
    "ExecutionClaimError",
    "ExecutionClaimStore",
    "coerce_execution_claim",
    "execution_claim_store_for",
    "InMemoryExecutionClaimStore",
    "PostgresExecutionClaimStore",
    "SQLiteExecutionClaimStore",
    "file_resource_key",
]
