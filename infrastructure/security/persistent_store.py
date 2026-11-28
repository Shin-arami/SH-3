from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, unique
from os import PathLike
from pathlib import Path
from secrets import token_hex
from types import MappingProxyType
from typing import Any

from infrastructure.security import EvidenceRecord, EvidenceStore
from infrastructure.security.persistent_schema import ensure_schema_for_store

__all__ = [
    "PersistentEvidenceIntegrityError",
    "ReplayClaim",
    "ReplayClaimBusyError",
    "ReplayClaimCompletedError",
    "ReplayClaimConflictError",
    "ReplayClaimOwnershipError",
    "ReplayClaimStatus",
    "ReplayStageBusyError",
    "ReplayStageConflictError",
    "ReplayStageExecution",
    "ReplayStageKey",
    "ReplayStageStatus",
    "SQLiteEvidenceStore",
    "SQLiteReplayClaimStore",
    "SQLiteReplayStageStore",
]


class PersistentEvidenceIntegrityError(ValueError):
    """Raised when persisted evidence is malformed or fails integrity checks."""


class ReplayClaimError(RuntimeError):
    """Base exception for persistent replay claim coordination errors."""


class ReplayClaimBusyError(ReplayClaimError):
    """Raised when another owner currently holds a replay claim."""


class ReplayClaimCompletedError(ReplayClaimError):
    """Raised when a completed claim has no recoverable terminal evidence."""


class ReplayClaimConflictError(ReplayClaimError):
    """Raised when an idempotency key is reused for different cycle inputs."""


class ReplayClaimOwnershipError(ReplayClaimError):
    """Raised when a stale or non-owning worker tries to finalize a claim."""


@unique
class ReplayClaimStatus(StrEnum):
    CLAIMED = "claimed"
    BUSY = "busy"
    COMPLETED = "completed"
    RELEASED = "released"


@dataclass(frozen=True, slots=True)
class ReplayClaim:
    cycle_id: str
    fingerprint: str
    status: ReplayClaimStatus
    generation: int
    attempts: int
    owner_token: str | None
    lease_expires_at: float | None
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ValueError("cycle_id must not be empty")
        if not self.fingerprint.strip():
            raise ValueError("fingerprint must not be empty")
        if not isinstance(self.status, ReplayClaimStatus):
            raise TypeError("status must be ReplayClaimStatus")
        if self.generation < 1 or self.attempts < 0:
            raise ValueError("generation and attempts are invalid")
        if self.status is ReplayClaimStatus.CLAIMED and not self.owner_token:
            raise ValueError("claimed status requires an owner token")
        if self.status is ReplayClaimStatus.COMPLETED and not self.evidence_id:
            raise ValueError("completed status requires an evidence id")


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("evidence JSON object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("evidence datetimes must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if hasattr(value, "value") and isinstance(value.value, (str, int, float)):
        return value.value
    raise TypeError(f"unsupported evidence JSON value: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _database_settings(
    database_path: str | PathLike[str],
    timeout_seconds: float,
) -> tuple[Path, float]:
    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds, (int, float)
    ):
        raise TypeError("timeout_seconds must be a real number")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and greater than zero")
    raw_path = str(database_path)
    if not raw_path.strip() or raw_path == ":memory:":
        raise ValueError("database_path must be a persistent file path")
    resolved_path = Path(raw_path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    return resolved_path, float(timeout_seconds)


class _SQLiteDatabase:
    __slots__ = ("_database_path", "_timeout_seconds")

    def __init__(
        self,
        database_path: str | PathLike[str],
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._database_path, self._timeout_seconds = _database_settings(
            database_path, timeout_seconds
        )
        ensure_schema_for_store(
            self._database_path, timeout_seconds=self._timeout_seconds
        )

    @property
    def database_path(self) -> Path:
        return self._database_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self._database_path,
            timeout=self._timeout_seconds,
            isolation_level=None,
        )
        try:
            connection.execute(
                f"PRAGMA busy_timeout = {int(self._timeout_seconds * 1000)}"
            )
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _begin(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN IMMEDIATE")

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.execute("COMMIT")

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")


class SQLiteEvidenceStore(EvidenceStore):
    """SQLite-backed EvidenceStore compatible with existing SH-3 boundaries.

    Each operation uses a short SQLite transaction and a fresh connection. The
    database file is the persistence boundary, so multiple store instances and
    processes can share the same evidence records safely.
    """

    __slots__ = ("_database_path", "_timeout_seconds")

    def __init__(
        self,
        database_path: str | PathLike[str],
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        EvidenceStore.__init__(self)
        self._database_path, self._timeout_seconds = _database_settings(
            database_path, timeout_seconds
        )
        ensure_schema_for_store(
            self._database_path, timeout_seconds=self._timeout_seconds
        )
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sh3_evidence_records (
                    evidence_id TEXT PRIMARY KEY NOT NULL,
                    record_json TEXT NOT NULL,
                    integrity TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @property
    def database_path(self) -> Path:
        """Return the resolved path shared with replay-claim storage."""
        return self._database_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self._database_path,
            timeout=self._timeout_seconds,
            isolation_level=None,
        )
        try:
            connection.execute(
                f"PRAGMA busy_timeout = {int(self._timeout_seconds * 1000)}"
            )
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _begin(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN IMMEDIATE")

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.execute("COMMIT")

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")

    @staticmethod
    def _record_json(record: EvidenceRecord) -> str:
        if not record.verify():
            raise PersistentEvidenceIntegrityError(
                f"evidence integrity verification failed: {record.evidence_id}"
            )
        data = record.to_dict()
        if not isinstance(data, Mapping):
            raise TypeError("EvidenceRecord.to_dict() must return a mapping")
        encoded = _canonical_json(data)
        return encoded

    @staticmethod
    def _decode_record(record_json: str, expected_integrity: str) -> EvidenceRecord:
        try:
            raw = json.loads(record_json)
            if not isinstance(raw, Mapping):
                raise TypeError("stored evidence must be a JSON object")
            stored_integrity = _text("integrity", raw.get("integrity"))
            if stored_integrity != expected_integrity:
                raise PersistentEvidenceIntegrityError(
                    "evidence row integrity does not match its stored document"
                )
            payload = raw.get("payload")
            if not isinstance(payload, Mapping):
                raise TypeError("stored evidence payload must be a JSON object")
            record = EvidenceRecord.create(
                evidence_id=_text("evidence_id", raw.get("evidence_id")),
                kind=_text("kind", raw.get("kind")),
                source=_text("source", raw.get("source")),
                subject_id=_text("subject_id", raw.get("subject_id")),
                version=_text("version", raw.get("version")),
                trace_id=raw.get("trace_id"),
                collected_at=_text("collected_at", raw.get("collected_at")),
                payload=payload,
            )
            if record.integrity != stored_integrity or not record.verify():
                raise PersistentEvidenceIntegrityError(
                    f"persisted evidence integrity failed: {record.evidence_id}"
                )
            return record
        except PersistentEvidenceIntegrityError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PersistentEvidenceIntegrityError(
                "persisted evidence record is malformed"
            ) from exc

    def register(self, record: EvidenceRecord) -> EvidenceRecord:
        if not isinstance(record, EvidenceRecord):
            raise TypeError("record must be EvidenceRecord")
        record_json = self._record_json(record)
        integrity = _text("integrity", record.integrity)
        with self._connection() as connection:
            self._begin(connection)
            try:
                existing = connection.execute(
                    "SELECT record_json, integrity FROM sh3_evidence_records "
                    "WHERE evidence_id = ?",
                    (record.evidence_id,),
                ).fetchone()
                if existing is not None:
                    current = self._decode_record(existing[0], existing[1])
                    if current.integrity != integrity:
                        raise ValueError(
                            "evidence identifier conflicts with an existing record: "
                            f"{record.evidence_id}"
                        )
                    self._commit(connection)
                    return current
                connection.execute(
                    "INSERT INTO sh3_evidence_records "
                    "(evidence_id, record_json, integrity) VALUES (?, ?, ?)",
                    (record.evidence_id, record_json, integrity),
                )
                self._commit(connection)
                return record
            except Exception:
                self._rollback(connection)
                raise

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        _text("evidence_id", evidence_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT record_json, integrity FROM sh3_evidence_records "
                "WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decode_record(row[0], row[1])

    def records(self) -> tuple[EvidenceRecord, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT record_json, integrity FROM sh3_evidence_records ORDER BY rowid"
            ).fetchall()
        return tuple(self._decode_record(row[0], row[1]) for row in rows)

    def contains(self, evidence_id: str) -> bool:
        _text("evidence_id", evidence_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM sh3_evidence_records WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
        return row is not None

    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM sh3_evidence_records"
            ).fetchone()
        return int(row[0])

    def size(self) -> int:
        return self.count()

    def empty(self) -> bool:
        return self.count() == 0

    def clear(self) -> None:
        with self._connection() as connection:
            self._begin(connection)
            try:
                connection.execute("DELETE FROM sh3_evidence_records")
                self._commit(connection)
            except Exception:
                self._rollback(connection)
                raise


class SQLiteReplayClaimStore(_SQLiteDatabase):
    """Atomic, cross-process claims for idempotent learning-cycle execution.

    A lease permits recovery after an owner disappears. The monotonically
    increasing generation fences off stale owners at finalization time. A cycle
    is considered completed only after its terminal evidence identifier is
    committed to this table.
    """

    __slots__ = ()

    def __init__(
        self,
        database_path: str | PathLike[str],
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(database_path, timeout_seconds=timeout_seconds)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sh3_replay_claims (
                    cycle_id TEXT PRIMARY KEY NOT NULL,
                    fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('claimed', 'completed', 'released')),
                    generation INTEGER NOT NULL,
                    attempts INTEGER NOT NULL,
                    owner_token TEXT,
                    lease_expires_at REAL,
                    evidence_id TEXT,
                    updated_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sh3_replay_claims_state_idx "
                "ON sh3_replay_claims(state, lease_expires_at)"
            )

    @staticmethod
    def _now_timestamp(now: datetime | None) -> float:
        if now is None:
            return datetime.now(UTC).timestamp()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("now must be a timezone-aware datetime")
        return now.astimezone(UTC).timestamp()

    @staticmethod
    def _claim_from_row(row: tuple[Any, ...]) -> ReplayClaim:
        (
            cycle_id,
            fingerprint,
            state,
            generation,
            attempts,
            owner_token,
            lease_expires_at,
            evidence_id,
        ) = row
        status = (
            ReplayClaimStatus.BUSY
            if state == ReplayClaimStatus.CLAIMED.value and owner_token is None
            else ReplayClaimStatus(state)
        )
        return ReplayClaim(
            cycle_id=cycle_id,
            fingerprint=fingerprint,
            status=status,
            generation=generation,
            attempts=attempts,
            owner_token=owner_token,
            lease_expires_at=lease_expires_at,
            evidence_id=evidence_id,
        )

    def claim(
        self,
        cycle_id: str,
        fingerprint: str,
        *,
        lease_seconds: float = 3600.0,
        now: datetime | None = None,
    ) -> ReplayClaim:
        _text("cycle_id", cycle_id)
        _text("fingerprint", fingerprint)
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, (int, float)
        ):
            raise TypeError("lease_seconds must be a real number")
        if not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError("lease_seconds must be finite and greater than zero")
        current_time = self._now_timestamp(now)
        lease_until = current_time + float(lease_seconds)
        owner_token = token_hex(24)
        with self._connection() as connection:
            self._begin(connection)
            try:
                row = connection.execute(
                    "SELECT cycle_id, fingerprint, state, generation, attempts, "
                    "owner_token, lease_expires_at, evidence_id "
                    "FROM sh3_replay_claims WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO sh3_replay_claims "
                        "(cycle_id, fingerprint, state, generation, attempts, "
                        "owner_token, lease_expires_at, evidence_id, updated_at) "
                        "VALUES (?, ?, 'claimed', 1, 1, ?, ?, NULL, ?)",
                        (cycle_id, fingerprint, owner_token, lease_until, current_time),
                    )
                    self._commit(connection)
                    return ReplayClaim(
                        cycle_id=cycle_id,
                        fingerprint=fingerprint,
                        status=ReplayClaimStatus.CLAIMED,
                        generation=1,
                        attempts=1,
                        owner_token=owner_token,
                        lease_expires_at=lease_until,
                    )

                (
                    _,
                    existing_fingerprint,
                    state,
                    generation,
                    attempts,
                    _existing_owner,
                    existing_lease,
                    evidence_id,
                ) = row
                if existing_fingerprint != fingerprint:
                    raise ReplayClaimConflictError(
                        f"replay fingerprint conflicts for {cycle_id}"
                    )
                if state == ReplayClaimStatus.COMPLETED.value:
                    self._commit(connection)
                    return ReplayClaim(
                        cycle_id=cycle_id,
                        fingerprint=fingerprint,
                        status=ReplayClaimStatus.COMPLETED,
                        generation=generation,
                        attempts=attempts,
                        owner_token=None,
                        lease_expires_at=None,
                        evidence_id=evidence_id,
                    )
                active = (
                    state == ReplayClaimStatus.CLAIMED.value
                    and existing_lease is not None
                    and float(existing_lease) > current_time
                )
                if active:
                    self._commit(connection)
                    return ReplayClaim(
                        cycle_id=cycle_id,
                        fingerprint=fingerprint,
                        status=ReplayClaimStatus.BUSY,
                        generation=generation,
                        attempts=attempts,
                        owner_token=None,
                        lease_expires_at=float(existing_lease),
                    )
                next_generation = int(generation) + 1
                next_attempts = int(attempts) + 1
                connection.execute(
                    "UPDATE sh3_replay_claims SET state = 'claimed', generation = ?, "
                    "attempts = ?, owner_token = ?, lease_expires_at = ?, evidence_id = NULL, "
                    "updated_at = ? WHERE cycle_id = ?",
                    (
                        next_generation,
                        next_attempts,
                        owner_token,
                        lease_until,
                        current_time,
                        cycle_id,
                    ),
                )
                self._commit(connection)
                return ReplayClaim(
                    cycle_id=cycle_id,
                    fingerprint=fingerprint,
                    status=ReplayClaimStatus.CLAIMED,
                    generation=next_generation,
                    attempts=next_attempts,
                    owner_token=owner_token,
                    lease_expires_at=lease_until,
                )
            except Exception:
                self._rollback(connection)
                raise

    def renew(
        self,
        cycle_id: str,
        fingerprint: str,
        owner_token: str,
        generation: int,
        *,
        lease_seconds: float = 3600.0,
        now: datetime | None = None,
    ) -> ReplayClaim:
        """Atomically extend an active lease without changing its fencing generation.

        Renewal is only permitted before the current lease expires. Once expired,
        the owner must not revive its claim; a new claim increments the generation.
        """
        _text("cycle_id", cycle_id)
        _text("fingerprint", fingerprint)
        _text("owner_token", owner_token)
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("generation must be a positive integer")
        if isinstance(lease_seconds, bool) or not isinstance(
            lease_seconds, (int, float)
        ):
            raise TypeError("lease_seconds must be a real number")
        if not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError("lease_seconds must be finite and greater than zero")
        current_time = self._now_timestamp(now)
        requested_lease_until = current_time + float(lease_seconds)
        with self._connection() as connection:
            self._begin(connection)
            try:
                row = connection.execute(
                    "SELECT fingerprint, state, generation, attempts, owner_token, "
                    "lease_expires_at, evidence_id FROM sh3_replay_claims "
                    "WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if row is None:
                    raise ReplayClaimOwnershipError(
                        f"replay claim is missing for {cycle_id}"
                    )
                (
                    stored_fingerprint,
                    state,
                    stored_generation,
                    attempts,
                    stored_owner,
                    stored_lease,
                    evidence_id,
                ) = row
                if stored_fingerprint != fingerprint:
                    raise ReplayClaimConflictError(
                        f"replay fingerprint conflicts for {cycle_id}"
                    )
                if (
                    state != ReplayClaimStatus.CLAIMED.value
                    or stored_owner != owner_token
                    or stored_generation != generation
                ):
                    raise ReplayClaimOwnershipError(
                        f"replay claim ownership was lost for {cycle_id}"
                    )
                if stored_lease is None or float(stored_lease) <= current_time:
                    raise ReplayClaimOwnershipError(
                        f"replay claim lease expired for {cycle_id}"
                    )
                lease_until = max(float(stored_lease), requested_lease_until)
                cursor = connection.execute(
                    "UPDATE sh3_replay_claims SET lease_expires_at = ?, updated_at = ? "
                    "WHERE cycle_id = ? AND fingerprint = ? AND state = 'claimed' "
                    "AND owner_token = ? AND generation = ? AND lease_expires_at > ?",
                    (
                        lease_until,
                        current_time,
                        cycle_id,
                        fingerprint,
                        owner_token,
                        generation,
                        current_time,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ReplayClaimOwnershipError(
                        f"replay claim ownership was lost for {cycle_id}"
                    )
                self._commit(connection)
                return ReplayClaim(
                    cycle_id=cycle_id,
                    fingerprint=fingerprint,
                    status=ReplayClaimStatus.CLAIMED,
                    generation=generation,
                    attempts=attempts,
                    owner_token=owner_token,
                    lease_expires_at=lease_until,
                    evidence_id=evidence_id,
                )
            except Exception:
                self._rollback(connection)
                raise

    def complete(
        self,
        cycle_id: str,
        fingerprint: str,
        owner_token: str,
        generation: int,
        evidence_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        _text("cycle_id", cycle_id)
        _text("fingerprint", fingerprint)
        _text("owner_token", owner_token)
        _text("evidence_id", evidence_id)
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("generation must be a positive integer")
        current_time = self._now_timestamp(now)
        with self._connection() as connection:
            self._begin(connection)
            try:
                row = connection.execute(
                    "SELECT fingerprint, state, generation, owner_token, evidence_id, "
                    "lease_expires_at FROM sh3_replay_claims WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if row is None:
                    raise ReplayClaimOwnershipError(
                        f"replay claim is missing for {cycle_id}"
                    )
                (
                    stored_fingerprint,
                    state,
                    stored_generation,
                    stored_owner,
                    stored_evidence,
                    stored_lease,
                ) = row
                if stored_fingerprint != fingerprint:
                    raise ReplayClaimConflictError(
                        f"replay fingerprint conflicts for {cycle_id}"
                    )
                if state == ReplayClaimStatus.COMPLETED.value:
                    if stored_evidence == evidence_id:
                        if stored_generation == generation:
                            self._commit(connection)
                            return
                        raise ReplayClaimOwnershipError(
                            f"replay claim ownership was lost for {cycle_id}"
                        )
                    raise ReplayClaimConflictError(
                        f"completed replay evidence conflicts for {cycle_id}"
                    )
                if (
                    state != ReplayClaimStatus.CLAIMED.value
                    or stored_owner != owner_token
                    or stored_generation != generation
                ):
                    raise ReplayClaimOwnershipError(
                        f"replay claim ownership was lost for {cycle_id}"
                    )
                if stored_lease is None or float(stored_lease) <= current_time:
                    raise ReplayClaimOwnershipError(
                        f"replay claim lease expired for {cycle_id}"
                    )
                connection.execute(
                    "UPDATE sh3_replay_claims SET state = 'completed', owner_token = NULL, "
                    "lease_expires_at = NULL, evidence_id = ?, updated_at = ? "
                    "WHERE cycle_id = ?",
                    (evidence_id, current_time, cycle_id),
                )
                self._commit(connection)
            except Exception:
                self._rollback(connection)
                raise

    def release(
        self,
        cycle_id: str,
        owner_token: str,
        generation: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        _text("cycle_id", cycle_id)
        _text("owner_token", owner_token)
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("generation must be a positive integer")
        current_time = self._now_timestamp(now)
        with self._connection() as connection:
            self._begin(connection)
            try:
                cursor = connection.execute(
                    "UPDATE sh3_replay_claims SET state = 'released', owner_token = NULL, "
                    "lease_expires_at = NULL, updated_at = ? WHERE cycle_id = ? "
                    "AND state = 'claimed' AND owner_token = ? AND generation = ? "
                    "AND lease_expires_at > ?",
                    (current_time, cycle_id, owner_token, generation, current_time),
                )
                self._commit(connection)
                return cursor.rowcount == 1
            except Exception:
                self._rollback(connection)
                raise

    def reconcile_completed(
        self,
        cycle_id: str,
        fingerprint: str,
        evidence_id: str,
        *,
        generation: int | None = None,
    ) -> None:
        """Reconcile terminal evidence only for the generation that produced it."""
        _text("cycle_id", cycle_id)
        _text("fingerprint", fingerprint)
        _text("evidence_id", evidence_id)
        if generation is not None and (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise ValueError("generation must be a positive integer or None")
        now = datetime.now(UTC).timestamp()
        with self._connection() as connection:
            self._begin(connection)
            try:
                row = connection.execute(
                    "SELECT fingerprint, state, generation, attempts, evidence_id "
                    "FROM sh3_replay_claims WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if row is None:
                    reconciled_generation = 1 if generation is None else generation
                    connection.execute(
                        "INSERT INTO sh3_replay_claims "
                        "(cycle_id, fingerprint, state, generation, attempts, owner_token, "
                        "lease_expires_at, evidence_id, updated_at) "
                        "VALUES (?, ?, 'completed', ?, 0, NULL, NULL, ?, ?)",
                        (
                            cycle_id,
                            fingerprint,
                            reconciled_generation,
                            evidence_id,
                            now,
                        ),
                    )
                else:
                    (
                        stored_fingerprint,
                        state,
                        stored_generation,
                        _attempts,
                        stored_evidence,
                    ) = row
                    if stored_fingerprint != fingerprint:
                        raise ReplayClaimConflictError(
                            f"replay fingerprint conflicts for {cycle_id}"
                        )
                    if state == ReplayClaimStatus.COMPLETED.value:
                        if stored_evidence != evidence_id:
                            raise ReplayClaimConflictError(
                                f"completed replay evidence conflicts for {cycle_id}"
                            )
                        if generation is None:
                            if stored_generation != 1:
                                raise ReplayClaimOwnershipError(
                                    f"replay claim generation is required after takeover for {cycle_id}"
                                )
                        elif stored_generation != generation:
                            raise ReplayClaimOwnershipError(
                                f"replay claim ownership was lost for {cycle_id}"
                            )
                    else:
                        if generation is None:
                            if stored_generation != 1:
                                raise ReplayClaimOwnershipError(
                                    f"replay claim generation is required after takeover for {cycle_id}"
                                )
                        elif stored_generation != generation:
                            raise ReplayClaimOwnershipError(
                                f"replay claim ownership was lost for {cycle_id}"
                            )
                        connection.execute(
                            "UPDATE sh3_replay_claims SET state = 'completed', "
                            "owner_token = NULL, lease_expires_at = NULL, evidence_id = ?, "
                            "updated_at = ? WHERE cycle_id = ? AND fingerprint = ? "
                            "AND generation = ?",
                            (
                                evidence_id,
                                now,
                                cycle_id,
                                fingerprint,
                                stored_generation,
                            ),
                        )
                self._commit(connection)
            except Exception:
                self._rollback(connection)
                raise

    def get(self, cycle_id: str) -> ReplayClaim | None:
        _text("cycle_id", cycle_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT cycle_id, fingerprint, state, generation, attempts, owner_token, "
                "lease_expires_at, evidence_id FROM sh3_replay_claims WHERE cycle_id = ?",
                (cycle_id,),
            ).fetchone()
        if row is None:
            return None
        return self._claim_from_row(row)

def _replay_stage_key_digest(
    cycle_id: str,
    cycle_fingerprint: str,
    stage_name: str,
    input_fingerprint: str,
) -> str:
    identity = {
        "contract_version": 1,
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "stage_name": stage_name,
        "input_fingerprint": input_fingerprint,
    }
    digest = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
    return f"sh3-stage-v1:{digest}"


def _replay_stage_result_integrity(result_json: str) -> str:
    digest = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@unique
class ReplayStageStatus(StrEnum):
    CLAIMED = "claimed"
    COMPLETED = "completed"


class ReplayStageBusyError(ReplayClaimError):
    """Raised when the same generation already owns an unfinished stage."""


class ReplayStageConflictError(ReplayClaimError):
    """Raised when a stage identity or its completed result conflicts."""


@dataclass(frozen=True, slots=True)
class ReplayStageKey:
    """Stable idempotency identity for one logical stage execution.

    The key deliberately excludes the replay-claim generation and owner token.
    """

    idempotency_key: str
    cycle_id: str
    cycle_fingerprint: str
    stage_name: str
    input_fingerprint: str

    def __post_init__(self) -> None:
        _text("idempotency_key", self.idempotency_key)
        _text("cycle_id", self.cycle_id)
        _text("cycle_fingerprint", self.cycle_fingerprint)
        _text("stage_name", self.stage_name)
        _text("input_fingerprint", self.input_fingerprint)

        expected = _replay_stage_key_digest(
            self.cycle_id,
            self.cycle_fingerprint,
            self.stage_name,
            self.input_fingerprint,
        )
        if self.idempotency_key != expected:
            raise ValueError("idempotency_key does not match stage identity")

    @classmethod
    def create(
        cls,
        cycle_id: str,
        cycle_fingerprint: str,
        stage_name: str,
        input_payload: Mapping[str, Any],
    ) -> ReplayStageKey:
        if not isinstance(input_payload, Mapping):
            raise TypeError("input_payload must be a mapping")

        input_json = _canonical_json(input_payload)
        input_fingerprint = (
            "sha256:"
            + hashlib.sha256(input_json.encode("utf-8")).hexdigest()
        )
        return cls.from_fingerprints(
            cycle_id,
            cycle_fingerprint,
            stage_name,
            input_fingerprint,
        )

    @classmethod
    def from_fingerprints(
        cls,
        cycle_id: str,
        cycle_fingerprint: str,
        stage_name: str,
        input_fingerprint: str,
    ) -> ReplayStageKey:
        return cls(
            idempotency_key=_replay_stage_key_digest(
                cycle_id,
                cycle_fingerprint,
                stage_name,
                input_fingerprint,
            ),
            cycle_id=cycle_id,
            cycle_fingerprint=cycle_fingerprint,
            stage_name=stage_name,
            input_fingerprint=input_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class ReplayStageExecution:
    key: ReplayStageKey
    status: ReplayStageStatus
    generation: int
    attempts: int
    owner_token: str | None
    result: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, ReplayStageKey):
            raise TypeError("key must be ReplayStageKey")
        if not isinstance(self.status, ReplayStageStatus):
            raise TypeError("status must be ReplayStageStatus")

        for name, value in (
            ("generation", self.generation),
            ("attempts", self.attempts),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")

        if self.status is ReplayStageStatus.CLAIMED:
            _text("owner_token", self.owner_token)
            if self.result is not None:
                raise ValueError("claimed stage must not contain a result")
        else:
            if self.owner_token is not None:
                raise ValueError("completed stage must not retain an owner token")
            if not isinstance(self.result, Mapping):
                raise TypeError("completed stage result must be a mapping")
            object.__setattr__(
                self,
                "result",
                MappingProxyType(dict(self.result)),
            )


def _decode_replay_stage_result(
    result_json: str,
    expected_integrity: str,
) -> Mapping[str, Any]:
    try:
        raw = json.loads(result_json)
        if not isinstance(raw, Mapping):
            raise TypeError("stage result must be a JSON object")

        canonical = _canonical_json(raw)
        if canonical != result_json:
            raise ValueError("stage result is not canonical JSON")

        if _replay_stage_result_integrity(canonical) != expected_integrity:
            raise PersistentEvidenceIntegrityError(
                "persisted replay stage result integrity failed"
            )
        return MappingProxyType(dict(raw))
    except PersistentEvidenceIntegrityError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PersistentEvidenceIntegrityError(
            "persisted replay stage result is malformed"
        ) from exc


class SQLiteReplayStageStore(_SQLiteDatabase):
    """Durable stage execution ledger fenced by the parent replay claim.

    Stage rows share the replay-claim database. A completed result can be
    replayed by a newer generation. An unfinished row can be taken over only
    after the parent claim has moved to a newer generation.
    """

    __slots__ = ()

    def __init__(
        self,
        database_path: str | PathLike[str],
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(database_path, timeout_seconds=timeout_seconds)
        with self._connection() as connection:
            parent = connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'sh3_replay_claims'"
            ).fetchone()
            if parent is None:
                raise ValueError(
                    "SQLiteReplayStageStore requires sh3_replay_claims"
                )

            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sh3_replay_stage_executions (
                    idempotency_key TEXT PRIMARY KEY NOT NULL,
                    cycle_id TEXT NOT NULL,
                    cycle_fingerprint TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK (state IN ('claimed', 'completed')),
                    generation INTEGER NOT NULL CHECK (generation >= 1),
                    attempts INTEGER NOT NULL CHECK (attempts >= 1),
                    owner_token TEXT,
                    result_json TEXT,
                    result_integrity TEXT,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (cycle_id)
                        REFERENCES sh3_replay_claims(cycle_id),
                    CHECK (
                        (
                            state = 'claimed'
                            AND owner_token IS NOT NULL
                            AND result_json IS NULL
                            AND result_integrity IS NULL
                        )
                        OR
                        (
                            state = 'completed'
                            AND owner_token IS NULL
                            AND result_json IS NOT NULL
                            AND result_integrity IS NOT NULL
                        )
                    )
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS "
                "sh3_replay_stage_cycle_state_idx "
                "ON sh3_replay_stage_executions(cycle_id, state)"
            )

    @staticmethod
    def _validate_parent_owner(
        connection: sqlite3.Connection,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        current_time: float,
    ) -> None:
        row = connection.execute(
            "SELECT fingerprint, state, generation, owner_token, "
            "lease_expires_at FROM sh3_replay_claims WHERE cycle_id = ?",
            (key.cycle_id,),
        ).fetchone()

        if row is None:
            raise ReplayClaimOwnershipError(
                f"replay claim is missing for {key.cycle_id}"
            )

        fingerprint, state, stored_generation, stored_owner, lease = row
        if fingerprint != key.cycle_fingerprint:
            raise ReplayClaimConflictError(
                f"replay fingerprint conflicts for {key.cycle_id}"
            )
        if (
            state != ReplayClaimStatus.CLAIMED.value
            or stored_generation != generation
            or stored_owner != owner_token
        ):
            raise ReplayClaimOwnershipError(
                f"replay claim ownership was lost for {key.cycle_id}"
            )
        if lease is None or float(lease) <= current_time:
            raise ReplayClaimOwnershipError(
                f"replay claim lease expired for {key.cycle_id}"
            )

    @staticmethod
    def _execution_from_row(
        key: ReplayStageKey,
        row: tuple[Any, ...],
    ) -> ReplayStageExecution:
        (
            cycle_fingerprint,
            stage_name,
            input_fingerprint,
            state,
            generation,
            attempts,
            owner_token,
            result_json,
            result_integrity,
            cycle_id,
        ) = row

        if (
            cycle_id != key.cycle_id
            or cycle_fingerprint != key.cycle_fingerprint
            or stage_name != key.stage_name
            or input_fingerprint != key.input_fingerprint
        ):
            raise ReplayStageConflictError(
                f"replay stage identity conflicts for {key.idempotency_key}"
            )

        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
            or isinstance(attempts, bool)
            or not isinstance(attempts, int)
            or attempts < 1
        ):
            raise PersistentEvidenceIntegrityError(
                "persisted replay stage ownership metadata is invalid"
            )

        if state == ReplayStageStatus.CLAIMED.value:
            if (
                not isinstance(owner_token, str)
                or not owner_token.strip()
                or result_json is not None
                or result_integrity is not None
            ):
                raise PersistentEvidenceIntegrityError(
                    "persisted claimed replay stage is inconsistent"
                )
            return ReplayStageExecution(
                key=key,
                status=ReplayStageStatus.CLAIMED,
                generation=generation,
                attempts=attempts,
                owner_token=owner_token,
            )

        if state == ReplayStageStatus.COMPLETED.value:
            if (
                owner_token is not None
                or not isinstance(result_json, str)
                or not isinstance(result_integrity, str)
            ):
                raise PersistentEvidenceIntegrityError(
                    "persisted completed replay stage is inconsistent"
                )
            result = _decode_replay_stage_result(
                result_json,
                result_integrity,
            )
            return ReplayStageExecution(
                key=key,
                status=ReplayStageStatus.COMPLETED,
                generation=generation,
                attempts=attempts,
                owner_token=None,
                result=result,
            )

        raise PersistentEvidenceIntegrityError(
            f"unknown replay stage state: {state}"
        )

    def get(self, key: ReplayStageKey) -> ReplayStageExecution | None:
        if not isinstance(key, ReplayStageKey):
            raise TypeError("key must be ReplayStageKey")

        with self._connection() as connection:
            row = connection.execute(
                "SELECT cycle_fingerprint, stage_name, input_fingerprint, "
                "state, generation, attempts, owner_token, result_json, "
                "result_integrity, cycle_id FROM sh3_replay_stage_executions "
                "WHERE idempotency_key = ?",
                (key.idempotency_key,),
            ).fetchone()

        if row is None:
            return None
        return self._execution_from_row(key, row)

    def begin(
        self,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        *,
        now: datetime | None = None,
    ) -> ReplayStageExecution:
        if not isinstance(key, ReplayStageKey):
            raise TypeError("key must be ReplayStageKey")
        _text("owner_token", owner_token)
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise ValueError("generation must be a positive integer")

        current_time = SQLiteReplayClaimStore._now_timestamp(now)
        with self._connection() as connection:
            self._begin(connection)
            try:
                self._validate_parent_owner(
                    connection,
                    key,
                    owner_token,
                    generation,
                    current_time,
                )
                row = connection.execute(
                    "SELECT cycle_fingerprint, stage_name, input_fingerprint, "
                    "state, generation, attempts, owner_token, result_json, "
                    "result_integrity, cycle_id FROM sh3_replay_stage_executions "
                    "WHERE idempotency_key = ?",
                    (key.idempotency_key,),
                ).fetchone()

                if row is None:
                    connection.execute(
                        "INSERT INTO sh3_replay_stage_executions "
                        "(idempotency_key, cycle_id, cycle_fingerprint, "
                        "stage_name, input_fingerprint, state, generation, "
                        "attempts, owner_token, result_json, result_integrity, "
                        "updated_at) "
                        "VALUES (?, ?, ?, ?, ?, 'claimed', ?, 1, ?, NULL, "
                        "NULL, ?)",
                        (
                            key.idempotency_key,
                            key.cycle_id,
                            key.cycle_fingerprint,
                            key.stage_name,
                            key.input_fingerprint,
                            generation,
                            owner_token,
                            current_time,
                        ),
                    )
                    self._commit(connection)
                    return ReplayStageExecution(
                        key=key,
                        status=ReplayStageStatus.CLAIMED,
                        generation=generation,
                        attempts=1,
                        owner_token=owner_token,
                    )

                execution = self._execution_from_row(key, row)
                if execution.status is ReplayStageStatus.COMPLETED:
                    self._commit(connection)
                    return execution

                if (
                    execution.generation == generation
                    and execution.owner_token == owner_token
                ):
                    raise ReplayStageBusyError(
                        f"replay stage is already claimed: {key.idempotency_key}"
                    )

                if execution.generation >= generation:
                    raise ReplayClaimOwnershipError(
                        f"replay stage generation is newer or conflicts: "
                        f"{key.idempotency_key}"
                    )

                next_attempts = execution.attempts + 1
                cursor = connection.execute(
                    "UPDATE sh3_replay_stage_executions "
                    "SET generation = ?, attempts = ?, owner_token = ?, "
                    "updated_at = ? WHERE idempotency_key = ? "
                    "AND state = 'claimed' AND generation = ?",
                    (
                        generation,
                        next_attempts,
                        owner_token,
                        current_time,
                        key.idempotency_key,
                        execution.generation,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ReplayClaimOwnershipError(
                        f"replay stage takeover was lost: {key.idempotency_key}"
                    )

                self._commit(connection)
                return ReplayStageExecution(
                    key=key,
                    status=ReplayStageStatus.CLAIMED,
                    generation=generation,
                    attempts=next_attempts,
                    owner_token=owner_token,
                )
            except Exception:
                self._rollback(connection)
                raise

    def complete(
        self,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> ReplayStageExecution:
        if not isinstance(key, ReplayStageKey):
            raise TypeError("key must be ReplayStageKey")
        _text("owner_token", owner_token)
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise ValueError("generation must be a positive integer")
        if not isinstance(result, Mapping):
            raise TypeError("result must be a mapping")

        result_json = _canonical_json(result)
        result_integrity = _replay_stage_result_integrity(result_json)
        current_time = SQLiteReplayClaimStore._now_timestamp(now)

        with self._connection() as connection:
            self._begin(connection)
            try:
                self._validate_parent_owner(
                    connection,
                    key,
                    owner_token,
                    generation,
                    current_time,
                )
                row = connection.execute(
                    "SELECT cycle_fingerprint, stage_name, input_fingerprint, "
                    "state, generation, attempts, owner_token, result_json, "
                    "result_integrity, cycle_id FROM sh3_replay_stage_executions "
                    "WHERE idempotency_key = ?",
                    (key.idempotency_key,),
                ).fetchone()

                if row is None:
                    raise ReplayClaimOwnershipError(
                        f"replay stage claim is missing: {key.idempotency_key}"
                    )

                execution = self._execution_from_row(key, row)
                if execution.status is ReplayStageStatus.COMPLETED:
                    if (
                        row[7] != result_json
                        or row[8] != result_integrity
                    ):
                        raise ReplayStageConflictError(
                            f"completed replay stage result conflicts: "
                            f"{key.idempotency_key}"
                        )
                    self._commit(connection)
                    return execution

                if (
                    execution.generation != generation
                    or execution.owner_token != owner_token
                ):
                    raise ReplayClaimOwnershipError(
                        f"replay stage ownership was lost: {key.idempotency_key}"
                    )

                cursor = connection.execute(
                    "UPDATE sh3_replay_stage_executions "
                    "SET state = 'completed', owner_token = NULL, "
                    "result_json = ?, result_integrity = ?, updated_at = ? "
                    "WHERE idempotency_key = ? AND state = 'claimed' "
                    "AND generation = ? AND owner_token = ?",
                    (
                        result_json,
                        result_integrity,
                        current_time,
                        key.idempotency_key,
                        generation,
                        owner_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ReplayClaimOwnershipError(
                        f"replay stage completion was fenced: {key.idempotency_key}"
                    )

                self._commit(connection)
                return ReplayStageExecution(
                    key=key,
                    status=ReplayStageStatus.COMPLETED,
                    generation=generation,
                    attempts=execution.attempts,
                    owner_token=None,
                    result=result,
                )
            except Exception:
                self._rollback(connection)
                raise
