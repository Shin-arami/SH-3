from __future__ import annotations

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
from typing import Any

from infrastructure.security import EvidenceRecord, EvidenceStore

__all__ = [
    "PersistentEvidenceIntegrityError",
    "ReplayClaim",
    "ReplayClaimBusyError",
    "ReplayClaimCompletedError",
    "ReplayClaimConflictError",
    "ReplayClaimOwnershipError",
    "ReplayClaimStatus",
    "SQLiteEvidenceStore",
    "SQLiteReplayClaimStore",
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
