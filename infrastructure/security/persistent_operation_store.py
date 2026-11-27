from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, unique
from os import PathLike
from types import MappingProxyType
from typing import Any

from infrastructure.security.persistent_store import (
    PersistentEvidenceIntegrityError,
    ReplayClaimError,
    ReplayClaimOwnershipError,
    SQLiteReplayClaimStore,
    _canonical_json,
    _SQLiteDatabase,
    _text,
)

__all__ = [
    "ReplayOperationBusyError",
    "ReplayOperationConflictError",
    "ReplayOperationExecution",
    "ReplayOperationKey",
    "ReplayOperationKind",
    "ReplayOperationParentError",
    "ReplayOperationStatus",
    "SQLiteReplayOperationStore",
]


@unique
class ReplayOperationKind(StrEnum):
    ACTION = "action"
    ROLLBACK = "rollback"


@unique
class ReplayOperationStatus(StrEnum):
    CLAIMED = "claimed"
    COMPLETED = "completed"


class ReplayOperationBusyError(ReplayClaimError):
    """Raised when an operation is already claimed by the active generation."""


class ReplayOperationConflictError(ReplayClaimError):
    """Raised when an operation key is reused with different identity or result."""


class ReplayOperationParentError(ReplayClaimError):
    """Raised when an operation's parent stage or action is missing or invalid."""


def _operation_result_integrity(result_json: str) -> str:
    digest = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _valid_sha256_fingerprint(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        return False
    digest = value[7:]
    return all(character in "0123456789abcdef" for character in digest)


@dataclass(frozen=True, slots=True)
class ReplayOperationKey:
    """Stable, tenant-scoped identity for one optimizer Action or Rollback.

    ``idempotency_key`` is supplied by the caller so P3-1's deterministic
    Action and Rollback key derivation remains authoritative. The input
    fingerprint is stored separately, allowing a reused key with different
    semantic input to be rejected rather than silently becoming a new key.
    ``parent_stage_key`` identifies the optimizer stage in the existing replay
    stage ledger. Rollbacks additionally identify their Action operation.
    """

    idempotency_key: str
    tenant_id: str | None
    cycle_id: str
    cycle_fingerprint: str
    parent_stage_key: str
    operation_kind: ReplayOperationKind
    operation_name: str
    ordinal: int
    input_fingerprint: str
    parent_operation_key: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("idempotency_key", self.idempotency_key),
            ("cycle_id", self.cycle_id),
            ("cycle_fingerprint", self.cycle_fingerprint),
            ("parent_stage_key", self.parent_stage_key),
            ("operation_name", self.operation_name),
        ):
            _text(name, value)
        if self.tenant_id is not None:
            _text("tenant_id", self.tenant_id)
        if not isinstance(self.operation_kind, ReplayOperationKind):
            raise TypeError("operation_kind must be ReplayOperationKind")
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal < 0
        ):
            raise ValueError("ordinal must be a non-negative integer")
        if not _valid_sha256_fingerprint(self.input_fingerprint):
            raise ValueError("input_fingerprint must be a sha256 fingerprint")
        if self.operation_kind is ReplayOperationKind.ACTION:
            if self.parent_operation_key is not None:
                raise ValueError("Action operations must not have a parent operation key")
        else:
            _text("parent_operation_key", self.parent_operation_key)

    @property
    def tenant_scope(self) -> str:
        """Return the non-null SQLite namespace; empty text denotes global scope."""
        return self.tenant_id if self.tenant_id is not None else ""

    @classmethod
    def create(
        cls,
        *,
        idempotency_key: str,
        tenant_id: str | None,
        cycle_id: str,
        cycle_fingerprint: str,
        parent_stage_key: str,
        operation_kind: ReplayOperationKind,
        operation_name: str,
        ordinal: int,
        input_payload: Mapping[str, Any],
        parent_operation_key: str | None = None,
    ) -> ReplayOperationKey:
        if not isinstance(input_payload, Mapping):
            raise TypeError("input_payload must be a mapping")
        encoded = _canonical_json(input_payload)
        fingerprint = "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return cls(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            cycle_id=cycle_id,
            cycle_fingerprint=cycle_fingerprint,
            parent_stage_key=parent_stage_key,
            operation_kind=operation_kind,
            operation_name=operation_name,
            ordinal=ordinal,
            input_fingerprint=fingerprint,
            parent_operation_key=parent_operation_key,
        )


@dataclass(frozen=True, slots=True)
class ReplayOperationExecution:
    key: ReplayOperationKey
    status: ReplayOperationStatus
    generation: int
    attempts: int
    owner_token: str | None
    result: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, ReplayOperationKey):
            raise TypeError("key must be ReplayOperationKey")
        if not isinstance(self.status, ReplayOperationStatus):
            raise TypeError("status must be ReplayOperationStatus")
        for name, value in (("generation", self.generation), ("attempts", self.attempts)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.status is ReplayOperationStatus.CLAIMED:
            _text("owner_token", self.owner_token)
            if self.result is not None:
                raise ValueError("claimed operation must not contain a result")
        else:
            if self.owner_token is not None:
                raise ValueError("completed operation must not retain an owner token")
            if not isinstance(self.result, Mapping):
                raise TypeError("completed operation result must be a mapping")
            object.__setattr__(self, "result", MappingProxyType(dict(self.result)))


def _decode_replay_operation_result(
    result_json: str,
    expected_integrity: str,
) -> Mapping[str, Any]:
    try:
        raw = json.loads(result_json)
        if not isinstance(raw, Mapping):
            raise TypeError("operation result must be a JSON object")
        canonical = _canonical_json(raw)
        if canonical != result_json:
            raise ValueError("operation result is not canonical JSON")
        if _operation_result_integrity(canonical) != expected_integrity:
            raise PersistentEvidenceIntegrityError(
                "persisted replay operation result integrity failed"
            )
        return MappingProxyType(dict(raw))
    except PersistentEvidenceIntegrityError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PersistentEvidenceIntegrityError(
            "persisted replay operation result is malformed"
        ) from exc


_ACTION_CONTRACT_FIELDS = (
    "name",
    "contract_id",
    "implementation_version",
    "rollback_version",
    "replay_policy",
)


def _normalize_action_contracts(
    actions: tuple[str, ...],
    action_contracts: tuple[Mapping[str, str], ...] | list[Mapping[str, str]],
) -> tuple[dict[str, str], ...]:
    if not isinstance(action_contracts, (tuple, list)):
        raise TypeError("action_contracts must be a list or tuple")
    if len(actions) != len(action_contracts):
        raise ValueError("action names and Action contracts must have equal lengths")
    normalized: list[dict[str, str]] = []
    for index, raw_contract in enumerate(action_contracts):
        if not isinstance(raw_contract, Mapping):
            raise TypeError(f"action_contracts[{index}] must be a mapping")
        if set(raw_contract) != set(_ACTION_CONTRACT_FIELDS):
            raise ValueError(f"action_contracts[{index}] has an invalid field set")
        contract = {
            field_name: _text(field_name, raw_contract[field_name])
            for field_name in _ACTION_CONTRACT_FIELDS
        }
        if contract["name"] != actions[index]:
            raise ValueError("Action contract name does not match the ordered Action plan")
        if contract["replay_policy"] not in {"reuse_result", "require_local_state"}:
            raise ValueError("Action contract replay_policy is unsupported")
        normalized.append(contract)
    return tuple(normalized)


def _decode_replay_operation_plan(
    actions_json: str,
    expected_integrity: str,
) -> tuple[dict[str, str], ...]:
    try:
        raw = json.loads(actions_json)
        if not isinstance(raw, Mapping):
            raise TypeError("operation plan must be a JSON object")
        canonical = _canonical_json(raw)
        if canonical != actions_json:
            raise ValueError("operation plan is not canonical JSON")
        if _operation_result_integrity(canonical) != expected_integrity:
            raise PersistentEvidenceIntegrityError(
                "persisted replay operation plan integrity failed"
            )
        version = raw.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version != 2:
            raise ValueError(
                "unsupported optimizer Action plan version; version 1 has no "
                "implementation compatibility metadata and requires explicit reconciliation"
            )
        actions = raw.get("actions")
        if not isinstance(actions, list):
            raise TypeError("operation plan actions must be a JSON array")
        action_names: list[str] = []
        for index, action in enumerate(actions):
            if not isinstance(action, Mapping):
                raise TypeError(f"operation plan action {index} must be an object")
            action_names.append(_text("name", action.get("name")))
        return _normalize_action_contracts(tuple(action_names), actions)
    except PersistentEvidenceIntegrityError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PersistentEvidenceIntegrityError(
            "persisted replay operation plan is malformed"
        ) from exc


class SQLiteReplayOperationStore(_SQLiteDatabase):
    """Durable tenant-scoped Action/Rollback ledger sharing the replay database.

    Every mutation is protected by ``BEGIN IMMEDIATE`` and the active parent
    Replay Claim. Operation generations are fenced by the parent claim
    generation; completed outcomes are reusable by later generations.
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
            required_tables = {
                "sh3_replay_claims",
                "sh3_replay_stage_executions",
            }
            present_tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing = required_tables - present_tables
            if missing:
                raise ValueError(
                    "SQLiteReplayOperationStore requires existing replay tables: "
                    + ", ".join(sorted(missing))
                )
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sh3_replay_operations (
                    tenant_scope TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    cycle_id TEXT NOT NULL,
                    cycle_fingerprint TEXT NOT NULL,
                    parent_stage_key TEXT NOT NULL,
                    operation_kind TEXT NOT NULL
                        CHECK (operation_kind IN ('action', 'rollback')),
                    operation_name TEXT NOT NULL,
                    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                    parent_operation_key TEXT,
                    input_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK (state IN ('claimed', 'completed')),
                    generation INTEGER NOT NULL CHECK (generation >= 1),
                    attempts INTEGER NOT NULL CHECK (attempts >= 1),
                    owner_token TEXT,
                    result_json TEXT,
                    result_integrity TEXT,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (tenant_scope, idempotency_key),
                    FOREIGN KEY (cycle_id)
                        REFERENCES sh3_replay_claims(cycle_id),
                    FOREIGN KEY (parent_stage_key)
                        REFERENCES sh3_replay_stage_executions(idempotency_key),
                    FOREIGN KEY (tenant_scope, parent_operation_key)
                        REFERENCES sh3_replay_operations(tenant_scope, idempotency_key),
                    CHECK (
                        (operation_kind = 'action' AND parent_operation_key IS NULL)
                        OR
                        (operation_kind = 'rollback' AND parent_operation_key IS NOT NULL)
                    ),
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
                "CREATE INDEX IF NOT EXISTS sh3_replay_operations_cycle_state_idx "
                "ON sh3_replay_operations(cycle_id, state)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sh3_replay_operations_parent_stage_idx "
                "ON sh3_replay_operations(parent_stage_key, operation_kind, ordinal)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sh3_replay_operation_plans (
                    tenant_scope TEXT NOT NULL,
                    parent_stage_key TEXT NOT NULL,
                    cycle_id TEXT NOT NULL,
                    cycle_fingerprint TEXT NOT NULL,
                    plan_version INTEGER NOT NULL CHECK (plan_version >= 1),
                    actions_json TEXT NOT NULL,
                    actions_integrity TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK (generation >= 1),
                    owner_token TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (tenant_scope, parent_stage_key),
                    FOREIGN KEY (cycle_id)
                        REFERENCES sh3_replay_claims(cycle_id),
                    FOREIGN KEY (parent_stage_key)
                        REFERENCES sh3_replay_stage_executions(idempotency_key)
                )
                """
            )

    @staticmethod
    def _validate_parent_owner(
        connection: sqlite3.Connection,
        key: ReplayOperationKey,
        owner_token: str,
        generation: int,
        current_time: float,
    ) -> None:
        row = connection.execute(
            "SELECT fingerprint, state, generation, owner_token, lease_expires_at "
            "FROM sh3_replay_claims WHERE cycle_id = ?",
            (key.cycle_id,),
        ).fetchone()
        if row is None:
            raise ReplayClaimOwnershipError(
                f"replay claim is missing for {key.cycle_id}"
            )
        fingerprint, state, stored_generation, stored_owner, lease = row
        if fingerprint != key.cycle_fingerprint:
            raise ReplayOperationConflictError(
                f"replay fingerprint conflicts for {key.cycle_id}"
            )
        if (
            state != "claimed"
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
    def _validate_parent_stage(
        connection: sqlite3.Connection,
        key: ReplayOperationKey,
    ) -> tuple[str, int, str | None]:
        row = connection.execute(
            "SELECT cycle_id, cycle_fingerprint, state, generation, owner_token "
            "FROM sh3_replay_stage_executions WHERE idempotency_key = ?",
            (key.parent_stage_key,),
        ).fetchone()
        if row is None:
            raise ReplayOperationParentError(
                f"parent replay stage is missing: {key.parent_stage_key}"
            )
        if row[0] != key.cycle_id or row[1] != key.cycle_fingerprint:
            raise ReplayOperationConflictError(
                "operation does not match its parent replay stage"
            )
        if (
            row[2] not in {"claimed", "completed"}
            or isinstance(row[3], bool)
            or not isinstance(row[3], int)
            or row[3] < 1
        ):
            raise PersistentEvidenceIntegrityError(
                "persisted parent replay stage state is invalid"
            )
        stage_owner = row[4]
        if row[2] == ReplayOperationStatus.CLAIMED.value:
            if not isinstance(stage_owner, str) or not stage_owner.strip():
                raise PersistentEvidenceIntegrityError(
                    "claimed parent replay stage has no owner token"
                )
        elif stage_owner is not None:
            raise PersistentEvidenceIntegrityError(
                "completed parent replay stage retains an owner token"
            )
        return str(row[2]), int(row[3]), stage_owner

    @staticmethod
    def _validate_parent_operation(
        connection: sqlite3.Connection,
        key: ReplayOperationKey,
    ) -> None:
        if key.operation_kind is ReplayOperationKind.ACTION:
            return
        row = connection.execute(
            "SELECT operation_kind, operation_name, ordinal, cycle_id, "
            "cycle_fingerprint, parent_stage_key, state "
            "FROM sh3_replay_operations "
            "WHERE tenant_scope = ? AND idempotency_key = ?",
            (key.tenant_scope, key.parent_operation_key),
        ).fetchone()
        if row is None:
            raise ReplayOperationParentError(
                f"parent Action operation is missing: {key.parent_operation_key}"
            )
        if (
            row[0] != ReplayOperationKind.ACTION.value
            or row[1] != key.operation_name
            or row[2] != key.ordinal
            or row[3] != key.cycle_id
            or row[4] != key.cycle_fingerprint
            or row[5] != key.parent_stage_key
        ):
            raise ReplayOperationConflictError(
                "Rollback operation does not match its parent Action"
            )
        if row[6] != ReplayOperationStatus.COMPLETED.value:
            raise ReplayOperationParentError(
                "Rollback operation requires a completed parent Action"
            )

    @staticmethod
    def _execution_from_row(
        key: ReplayOperationKey,
        row: tuple[Any, ...],
    ) -> ReplayOperationExecution:
        (
            tenant_scope,
            idempotency_key,
            cycle_id,
            cycle_fingerprint,
            parent_stage_key,
            operation_kind,
            operation_name,
            ordinal,
            parent_operation_key,
            input_fingerprint,
            state,
            generation,
            attempts,
            owner_token,
            result_json,
            result_integrity,
        ) = row
        try:
            stored_key = ReplayOperationKey(
                idempotency_key=idempotency_key,
                tenant_id=tenant_scope or None,
                cycle_id=cycle_id,
                cycle_fingerprint=cycle_fingerprint,
                parent_stage_key=parent_stage_key,
                operation_kind=ReplayOperationKind(operation_kind),
                operation_name=operation_name,
                ordinal=ordinal,
                input_fingerprint=input_fingerprint,
                parent_operation_key=parent_operation_key,
            )
        except (TypeError, ValueError) as exc:
            raise PersistentEvidenceIntegrityError(
                "persisted replay operation identity is malformed"
            ) from exc
        if stored_key != key:
            raise ReplayOperationConflictError(
                f"replay operation identity conflicts for {key.idempotency_key}"
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
                "persisted replay operation ownership metadata is invalid"
            )
        if state == ReplayOperationStatus.CLAIMED.value:
            if (
                not isinstance(owner_token, str)
                or not owner_token.strip()
                or result_json is not None
                or result_integrity is not None
            ):
                raise PersistentEvidenceIntegrityError(
                    "persisted claimed replay operation is inconsistent"
                )
            return ReplayOperationExecution(
                key=key,
                status=ReplayOperationStatus.CLAIMED,
                generation=generation,
                attempts=attempts,
                owner_token=owner_token,
            )
        if state == ReplayOperationStatus.COMPLETED.value:
            if (
                owner_token is not None
                or not isinstance(result_json, str)
                or not isinstance(result_integrity, str)
            ):
                raise PersistentEvidenceIntegrityError(
                    "persisted completed replay operation is inconsistent"
                )
            result = _decode_replay_operation_result(result_json, result_integrity)
            return ReplayOperationExecution(
                key=key,
                status=ReplayOperationStatus.COMPLETED,
                generation=generation,
                attempts=attempts,
                owner_token=None,
                result=result,
            )
        raise PersistentEvidenceIntegrityError(
            f"unknown replay operation state: {state}"
        )

    @staticmethod
    def _select_operation(
        connection: sqlite3.Connection,
        key: ReplayOperationKey,
    ) -> tuple[Any, ...] | None:
        row = connection.execute(
            "SELECT tenant_scope, idempotency_key, cycle_id, cycle_fingerprint, "
            "parent_stage_key, operation_kind, operation_name, ordinal, "
            "parent_operation_key, input_fingerprint, state, generation, "
            "attempts, owner_token, result_json, result_integrity "
            "FROM sh3_replay_operations "
            "WHERE tenant_scope = ? AND idempotency_key = ?",
            (key.tenant_scope, key.idempotency_key),
        ).fetchone()
        return None if row is None else tuple(row)

    def get(self, key: ReplayOperationKey) -> ReplayOperationExecution | None:
        if not isinstance(key, ReplayOperationKey):
            raise TypeError("key must be ReplayOperationKey")
        with self._connection() as connection:
            row = self._select_operation(connection, key)
        if row is None:
            return None
        return self._execution_from_row(key, row)

    def begin(
        self,
        key: ReplayOperationKey,
        owner_token: str,
        generation: int,
        *,
        now: datetime | None = None,
    ) -> ReplayOperationExecution:
        if not isinstance(key, ReplayOperationKey):
            raise TypeError("key must be ReplayOperationKey")
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
                    connection, key, owner_token, generation, current_time
                )
                (
                    parent_stage_state,
                    parent_stage_generation,
                    parent_stage_owner,
                ) = self._validate_parent_stage(connection, key)
                self._validate_parent_operation(connection, key)
                row = self._select_operation(connection, key)
                if parent_stage_state == ReplayOperationStatus.COMPLETED.value:
                    if row is None:
                        raise ReplayOperationParentError(
                            "completed parent replay stage has no persisted operation"
                        )
                    completed = self._execution_from_row(key, row)
                    if completed.status is not ReplayOperationStatus.COMPLETED:
                        raise ReplayOperationParentError(
                            "completed parent replay stage contains an unfinished operation"
                        )
                    self._commit(connection)
                    return completed
                if (
                    parent_stage_state != ReplayOperationStatus.CLAIMED.value
                    or parent_stage_generation != generation
                    or parent_stage_owner != owner_token
                ):
                    raise ReplayClaimOwnershipError(
                        "operation execution requires the active parent stage owner and generation"
                    )
                if row is None:
                    connection.execute(
                        "INSERT INTO sh3_replay_operations "
                        "(tenant_scope, idempotency_key, cycle_id, cycle_fingerprint, "
                        "parent_stage_key, operation_kind, operation_name, ordinal, "
                        "parent_operation_key, input_fingerprint, state, generation, "
                        "attempts, owner_token, result_json, result_integrity, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'claimed', ?, 1, ?, NULL, NULL, ?)",
                        (
                            key.tenant_scope,
                            key.idempotency_key,
                            key.cycle_id,
                            key.cycle_fingerprint,
                            key.parent_stage_key,
                            key.operation_kind.value,
                            key.operation_name,
                            key.ordinal,
                            key.parent_operation_key,
                            key.input_fingerprint,
                            generation,
                            owner_token,
                            current_time,
                        ),
                    )
                    self._commit(connection)
                    return ReplayOperationExecution(
                        key=key,
                        status=ReplayOperationStatus.CLAIMED,
                        generation=generation,
                        attempts=1,
                        owner_token=owner_token,
                    )
                execution = self._execution_from_row(key, row)
                if execution.status is ReplayOperationStatus.COMPLETED:
                    self._commit(connection)
                    return execution
                if (
                    execution.generation == generation
                    and execution.owner_token == owner_token
                ):
                    raise ReplayOperationBusyError(
                        f"replay operation is already claimed: {key.idempotency_key}"
                    )
                if execution.generation >= generation:
                    raise ReplayClaimOwnershipError(
                        f"replay operation generation is newer or conflicts: "
                        f"{key.idempotency_key}"
                    )
                next_attempts = execution.attempts + 1
                cursor = connection.execute(
                    "UPDATE sh3_replay_operations "
                    "SET generation = ?, attempts = ?, owner_token = ?, updated_at = ? "
                    "WHERE tenant_scope = ? AND idempotency_key = ? "
                    "AND state = 'claimed' AND generation = ? AND owner_token = ?",
                    (
                        generation,
                        next_attempts,
                        owner_token,
                        current_time,
                        key.tenant_scope,
                        key.idempotency_key,
                        execution.generation,
                        execution.owner_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ReplayClaimOwnershipError(
                        f"replay operation takeover was lost: {key.idempotency_key}"
                    )
                self._commit(connection)
                return ReplayOperationExecution(
                    key=key,
                    status=ReplayOperationStatus.CLAIMED,
                    generation=generation,
                    attempts=next_attempts,
                    owner_token=owner_token,
                )
            except Exception:
                self._rollback(connection)
                raise

    def complete(
        self,
        key: ReplayOperationKey,
        owner_token: str,
        generation: int,
        result: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> ReplayOperationExecution:
        if not isinstance(key, ReplayOperationKey):
            raise TypeError("key must be ReplayOperationKey")
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
        result_integrity = _operation_result_integrity(result_json)
        current_time = SQLiteReplayClaimStore._now_timestamp(now)
        with self._connection() as connection:
            self._begin(connection)
            try:
                self._validate_parent_owner(
                    connection, key, owner_token, generation, current_time
                )
                (
                    parent_stage_state,
                    parent_stage_generation,
                    parent_stage_owner,
                ) = self._validate_parent_stage(connection, key)
                self._validate_parent_operation(connection, key)
                row = self._select_operation(connection, key)
                if row is None:
                    raise ReplayClaimOwnershipError(
                        f"replay operation claim is missing: {key.idempotency_key}"
                    )
                execution = self._execution_from_row(key, row)
                if parent_stage_state == ReplayOperationStatus.COMPLETED.value:
                    if execution.status is not ReplayOperationStatus.COMPLETED:
                        raise ReplayOperationParentError(
                            "completed parent replay stage contains an unfinished operation"
                        )
                    if row[14] != result_json or row[15] != result_integrity:
                        raise ReplayOperationConflictError(
                            f"completed replay operation result conflicts: "
                            f"{key.idempotency_key}"
                        )
                    self._commit(connection)
                    return execution
                if (
                    parent_stage_state != ReplayOperationStatus.CLAIMED.value
                    or parent_stage_generation != generation
                    or parent_stage_owner != owner_token
                ):
                    raise ReplayClaimOwnershipError(
                        "operation completion requires the active parent stage owner and generation"
                    )
                if execution.status is ReplayOperationStatus.COMPLETED:
                    if row[14] != result_json or row[15] != result_integrity:
                        raise ReplayOperationConflictError(
                            f"completed replay operation result conflicts: "
                            f"{key.idempotency_key}"
                        )
                    self._commit(connection)
                    return execution
                if (
                    execution.generation != generation
                    or execution.owner_token != owner_token
                ):
                    raise ReplayClaimOwnershipError(
                        f"replay operation ownership was lost: {key.idempotency_key}"
                    )
                cursor = connection.execute(
                    "UPDATE sh3_replay_operations "
                    "SET state = 'completed', owner_token = NULL, result_json = ?, "
                    "result_integrity = ?, updated_at = ? "
                    "WHERE tenant_scope = ? AND idempotency_key = ? "
                    "AND state = 'claimed' AND generation = ? AND owner_token = ?",
                    (
                        result_json,
                        result_integrity,
                        current_time,
                        key.tenant_scope,
                        key.idempotency_key,
                        generation,
                        owner_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ReplayClaimOwnershipError(
                        f"replay operation completion was fenced: {key.idempotency_key}"
                    )
                self._commit(connection)
                return ReplayOperationExecution(
                    key=key,
                    status=ReplayOperationStatus.COMPLETED,
                    generation=generation,
                    attempts=execution.attempts,
                    owner_token=None,
                    result=result,
                )
            except Exception:
                self._rollback(connection)
                raise

    def get_or_create_action_plan(
        self,
        *,
        tenant_id: str | None,
        cycle_id: str,
        cycle_fingerprint: str,
        parent_stage_key: str,
        owner_token: str,
        generation: int,
        actions: tuple[str, ...] | list[str],
        action_contracts: tuple[Mapping[str, str], ...] | list[Mapping[str, str]],
        registered_action_contracts: Mapping[str, Mapping[str, str]] | None = None,
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        """Persist the ordered Action plan and its explicit compatibility contract.

        The first plan for a tenant-scoped parent Stage is immutable. On replay,
        the persisted Action names and order are authoritative; current optimizer
        proposals may differ because earlier Actions changed runtime state. Every
        persisted Action must still be registered with the same contract identifier,
        implementation version, rollback version, and replay policy. Version-1
        name-only plans are rejected because their implementation compatibility
        cannot be established. Owner/generation fencing remains transactional.
        """
        if tenant_id is not None:
            _text("tenant_id", tenant_id)
        _text("cycle_id", cycle_id)
        _text("cycle_fingerprint", cycle_fingerprint)
        _text("parent_stage_key", parent_stage_key)
        _text("owner_token", owner_token)
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise ValueError("generation must be a positive integer")
        if not isinstance(actions, (tuple, list)):
            raise TypeError("actions must be a list or tuple")
        normalized_actions = tuple(_text("action", item) for item in actions)
        normalized_contracts = _normalize_action_contracts(
            normalized_actions,
            action_contracts,
        )
        normalized_registered_contracts: dict[str, dict[str, str]]
        if registered_action_contracts is None:
            normalized_registered_contracts = {
                contract["name"]: contract for contract in normalized_contracts
            }
        else:
            if not isinstance(registered_action_contracts, Mapping):
                raise TypeError("registered_action_contracts must be a mapping")
            normalized_registered_contracts = {}
            for raw_name, raw_contract in registered_action_contracts.items():
                registered_name = _text("registered_action", raw_name)
                normalized_registered_contracts[registered_name] = (
                    _normalize_action_contracts((registered_name,), (raw_contract,))[0]
                )
        encoded = _canonical_json(
            {"version": 2, "actions": list(normalized_contracts)}
        )
        integrity = _operation_result_integrity(encoded)
        tenant_scope = tenant_id if tenant_id is not None else ""
        current_time = SQLiteReplayClaimStore._now_timestamp(now)

        with self._connection() as connection:
            self._begin(connection)
            try:
                claim = connection.execute(
                    "SELECT fingerprint, state, generation, owner_token, lease_expires_at "
                    "FROM sh3_replay_claims WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if claim is None:
                    raise ReplayClaimOwnershipError(
                        f"replay claim is missing for {cycle_id}"
                    )
                if claim[0] != cycle_fingerprint:
                    raise ReplayOperationConflictError(
                        f"replay fingerprint conflicts for {cycle_id}"
                    )
                if (
                    claim[1] != "claimed"
                    or claim[2] != generation
                    or claim[3] != owner_token
                    or claim[4] is None
                    or float(claim[4]) <= current_time
                ):
                    raise ReplayClaimOwnershipError(
                        f"replay claim ownership was lost for {cycle_id}"
                    )

                stage = connection.execute(
                    "SELECT cycle_id, cycle_fingerprint, state, generation, owner_token "
                    "FROM sh3_replay_stage_executions WHERE idempotency_key = ?",
                    (parent_stage_key,),
                ).fetchone()
                if (
                    stage is None
                    or stage[0] != cycle_id
                    or stage[1] != cycle_fingerprint
                    or stage[2] != ReplayOperationStatus.CLAIMED.value
                    or stage[3] != generation
                    or stage[4] != owner_token
                ):
                    raise ReplayClaimOwnershipError(
                        "optimizer action plan requires the active parent Stage owner and generation"
                    )

                existing = connection.execute(
                    "SELECT cycle_id, cycle_fingerprint, plan_version, actions_json, "
                    "actions_integrity, generation, owner_token "
                    "FROM sh3_replay_operation_plans "
                    "WHERE tenant_scope = ? AND parent_stage_key = ?",
                    (tenant_scope, parent_stage_key),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO sh3_replay_operation_plans "
                        "(tenant_scope, parent_stage_key, cycle_id, cycle_fingerprint, "
                        "plan_version, actions_json, actions_integrity, generation, "
                        "owner_token, updated_at) VALUES (?, ?, ?, ?, 2, ?, ?, ?, ?, ?)",
                        (
                            tenant_scope,
                            parent_stage_key,
                            cycle_id,
                            cycle_fingerprint,
                            encoded,
                            integrity,
                            generation,
                            owner_token,
                            current_time,
                        ),
                    )
                    result = normalized_actions
                else:
                    if (
                        existing[0] != cycle_id
                        or existing[1] != cycle_fingerprint
                        or isinstance(existing[2], bool)
                        or not isinstance(existing[2], int)
                        or existing[2] != 2
                    ):
                        raise ReplayOperationConflictError(
                            "optimizer action plan identity or version conflicts"
                        )
                    stored_contracts = _decode_replay_operation_plan(existing[3], existing[4])
                    for stored_contract in stored_contracts:
                        registered_contract = normalized_registered_contracts.get(
                            stored_contract["name"]
                        )
                        if registered_contract is None:
                            raise ReplayOperationConflictError(
                                "persisted optimizer Action is no longer registered: "
                                + stored_contract["name"]
                            )
                        if registered_contract != stored_contract:
                            raise ReplayOperationConflictError(
                                "persisted optimizer Action plan is incompatible with the "
                                "registered Action contracts"
                            )
                    result = tuple(contract["name"] for contract in stored_contracts)
                    stored_generation = existing[5]
                    stored_owner = existing[6]
                    if (
                        isinstance(stored_generation, bool)
                        or not isinstance(stored_generation, int)
                        or stored_generation < 1
                    ):
                        raise PersistentEvidenceIntegrityError(
                            "persisted optimizer action plan generation is invalid"
                        )
                    if stored_generation > generation:
                        raise ReplayClaimOwnershipError(
                            "optimizer action plan is owned by a newer generation"
                        )
                    if stored_generation == generation and stored_owner != owner_token:
                        raise ReplayClaimOwnershipError(
                            "optimizer action plan is owned by another worker"
                        )
                    if stored_generation < generation:
                        cursor = connection.execute(
                            "UPDATE sh3_replay_operation_plans "
                            "SET generation = ?, owner_token = ?, updated_at = ? "
                            "WHERE tenant_scope = ? AND parent_stage_key = ? "
                            "AND generation = ? AND owner_token = ?",
                            (
                                generation,
                                owner_token,
                                current_time,
                                tenant_scope,
                                parent_stage_key,
                                stored_generation,
                                stored_owner,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise ReplayClaimOwnershipError(
                                "optimizer action plan ownership takeover was lost"
                            )
                self._commit(connection)
                return result
            except Exception:
                self._rollback(connection)
                raise

    def count_plans(self, *, cycle_id: str | None = None) -> int:
        if cycle_id is not None:
            _text("cycle_id", cycle_id)
        with self._connection() as connection:
            if cycle_id is None:
                row = connection.execute(
                    "SELECT COUNT(*) FROM sh3_replay_operation_plans"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) FROM sh3_replay_operation_plans WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
        return int(row[0])

    def count(self, *, cycle_id: str | None = None) -> int:
        if cycle_id is not None:
            _text("cycle_id", cycle_id)
        with self._connection() as connection:
            if cycle_id is None:
                row = connection.execute(
                    "SELECT COUNT(*) FROM sh3_replay_operations"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) FROM sh3_replay_operations WHERE cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
        return int(row[0])
