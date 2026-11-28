from __future__ import annotations

import hashlib
import multiprocessing as mp
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from infrastructure.security.persistent_operation_store import (
    ReplayOperationBusyError,
    ReplayOperationConflictError,
    ReplayOperationKey,
    ReplayOperationKind,
    ReplayOperationParentError,
    ReplayOperationStatus,
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    backup_database,
    check_database,
    restore_database,
)
from infrastructure.security.persistent_replay_provision import (
    provision_persistent_replay_database,
)
from infrastructure.security.persistent_replay_runtime import (
    create_persistent_replay_stores,
)
from infrastructure.security.persistent_schema import (
    PersistentSchemaMigrationRequiredError,
)
from infrastructure.security.persistent_store import (
    PersistentEvidenceIntegrityError,
    ReplayClaimOwnershipError,
    ReplayClaimStatus,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)

_NOW = datetime.now(UTC)
_CYCLE_ID = "learning-cycle:p3-2a-operation-store"
_CYCLE_FINGERPRINT = "sha256:p3-2a-operation-store-cycle"


def _prepared_database(
    database: Path,
) -> tuple[
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
    SQLiteReplayOperationStore,
    Any,
    ReplayStageKey,
]:
    SQLiteEvidenceStore(database)
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    claim = claims.claim(
        _CYCLE_ID,
        _CYCLE_FINGERPRINT,
        lease_seconds=600.0,
        now=_NOW,
    )
    assert claim.status is ReplayClaimStatus.CLAIMED
    assert claim.owner_token is not None
    parent_stage_key = ReplayStageKey.create(
        _CYCLE_ID,
        _CYCLE_FINGERPRINT,
        "learning_optimizer.request.v1",
        {"contract": "p3-2a-test", "learning_record_id": "learning-record:p3-2a"},
    )
    parent_stage = stages.begin(
        parent_stage_key,
        claim.owner_token,
        claim.generation,
        now=_NOW,
    )
    assert parent_stage.status is ReplayStageStatus.CLAIMED
    operations = SQLiteReplayOperationStore(database)
    return claims, stages, operations, claim, parent_stage_key


def _action_key(
    parent_stage_key: ReplayStageKey,
    *,
    tenant_id: str | None = "tenant:p3-2a",
    idempotency_key: str = "optimizer-action:p3-2a:0",
    input_payload: dict[str, Any] | None = None,
) -> ReplayOperationKey:
    return ReplayOperationKey.create(
        idempotency_key=idempotency_key,
        tenant_id=tenant_id,
        cycle_id=_CYCLE_ID,
        cycle_fingerprint=_CYCLE_FINGERPRINT,
        parent_stage_key=parent_stage_key.idempotency_key,
        operation_kind=ReplayOperationKind.ACTION,
        operation_name="reduce_context_depth",
        ordinal=0,
        input_payload=input_payload or {"context_depth": 8, "mode": "reduce-one"},
    )


def test_operation_result_is_durable_and_restored_after_reopen(tmp_path: Path) -> None:
    database = tmp_path / "operation-store.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)

    claimed = operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    assert claimed.status is ReplayOperationStatus.CLAIMED
    assert claimed.attempts == 1
    assert claimed.owner_token == claim.owner_token

    result = {"success": True, "changed": True, "removed_context": "ctx-7"}
    completed = operations.complete(
        key,
        claim.owner_token,
        claim.generation,
        result,
        now=_NOW,
    )
    assert completed.status is ReplayOperationStatus.COMPLETED
    assert completed.result == result
    assert operations.count(cycle_id=_CYCLE_ID) == 1

    reopened = SQLiteReplayOperationStore(database)
    restored = reopened.get(key)
    assert restored is not None
    assert restored.status is ReplayOperationStatus.COMPLETED
    assert restored.result == result
    assert restored.generation == claim.generation


def test_completed_operation_is_reused_and_conflicting_result_is_rejected(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-result-conflict.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)
    operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    result = {"success": True, "changed": False}
    first = operations.complete(key, claim.owner_token, claim.generation, result, now=_NOW)
    duplicate = operations.begin(key, claim.owner_token, claim.generation, now=_NOW)

    assert duplicate.status is ReplayOperationStatus.COMPLETED
    assert duplicate.result == first.result
    with pytest.raises(ReplayOperationConflictError, match="result conflicts"):
        operations.complete(
            key,
            claim.owner_token,
            claim.generation,
            {"success": True, "changed": True},
            now=_NOW,
        )


def test_completed_result_can_be_completed_again_after_parent_stage_completion(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-complete-after-stage.sqlite3"
    _, _stages, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)
    operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    result = {"success": True, "changed": False}
    first = operations.complete(
        key, claim.owner_token, claim.generation, result, now=_NOW
    )
    parent_stage_result = '{"success":true}'
    parent_stage_integrity = "sha256:" + hashlib.sha256(
        parent_stage_result.encode("utf-8")
    ).hexdigest()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_stage_executions "
            "SET state = 'completed', owner_token = NULL, "
            "result_json = ?, result_integrity = ? "
            "WHERE idempotency_key = ?",
            (
                parent_stage_result,
                parent_stage_integrity,
                parent_stage_key.idempotency_key,
            ),
        )

    repeated = operations.complete(
        key, claim.owner_token, claim.generation, result, now=_NOW
    )
    assert repeated.status is ReplayOperationStatus.COMPLETED
    assert repeated.result == first.result

    with pytest.raises(ReplayOperationConflictError, match="result conflicts"):
        operations.complete(
            key,
            claim.owner_token,
            claim.generation,
            {"success": True, "changed": True},
            now=_NOW,
        )


def test_parent_stage_owner_mismatch_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "operation-parent-stage-owner.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_stage_executions SET owner_token = ? "
            "WHERE idempotency_key = ?",
            ("different-stage-owner", parent_stage_key.idempotency_key),
        )

    with pytest.raises(ReplayClaimOwnershipError, match="parent stage owner"):
        operations.begin(
            _action_key(parent_stage_key),
            claim.owner_token,
            claim.generation,
            now=_NOW,
        )


def test_reusing_tenant_scoped_key_with_different_input_is_rejected(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-key-collision.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    original = _action_key(parent_stage_key)
    operations.begin(original, claim.owner_token, claim.generation, now=_NOW)
    conflicting = _action_key(
        parent_stage_key,
        input_payload={"context_depth": 99, "mode": "different"},
    )

    with pytest.raises(ReplayOperationConflictError, match="identity conflicts"):
        operations.begin(conflicting, claim.owner_token, claim.generation, now=_NOW)


def test_same_key_is_isolated_between_tenant_namespaces(tmp_path: Path) -> None:
    database = tmp_path / "operation-tenant-scope.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    tenant_a = _action_key(parent_stage_key, tenant_id="tenant-A")
    tenant_b = _action_key(parent_stage_key, tenant_id="tenant-B")

    first = operations.begin(tenant_a, claim.owner_token, claim.generation, now=_NOW)
    second = operations.begin(tenant_b, claim.owner_token, claim.generation, now=_NOW)

    assert first.status is ReplayOperationStatus.CLAIMED
    assert second.status is ReplayOperationStatus.CLAIMED
    assert operations.count(cycle_id=_CYCLE_ID) == 2


def test_global_scope_is_distinct_from_named_tenant_scope(tmp_path: Path) -> None:
    database = tmp_path / "operation-global-scope.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    global_key = _action_key(parent_stage_key, tenant_id=None)
    tenant_key = _action_key(parent_stage_key, tenant_id="tenant-global-test")

    operations.begin(global_key, claim.owner_token, claim.generation, now=_NOW)
    operations.begin(tenant_key, claim.owner_token, claim.generation, now=_NOW)

    assert operations.get(global_key) is not None
    assert operations.get(tenant_key) is not None
    assert operations.count(cycle_id=_CYCLE_ID) == 2


def test_duplicate_claim_is_busy_and_concurrent_claim_is_atomic(tmp_path: Path) -> None:
    database = tmp_path / "operation-concurrent.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)

    first = operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    assert first.status is ReplayOperationStatus.CLAIMED
    with pytest.raises(ReplayOperationBusyError):
        SQLiteReplayOperationStore(database).begin(
            key, claim.owner_token, claim.generation, now=_NOW
        )

    database_race = tmp_path / "operation-concurrent-first-claim.sqlite3"
    _, _, race_store, race_claim, race_parent_key = _prepared_database(database_race)
    assert race_claim.owner_token is not None
    race_key = _action_key(race_parent_key)
    stores = [SQLiteReplayOperationStore(database_race) for _ in range(8)]

    def attempt(store: SQLiteReplayOperationStore) -> str:
        try:
            store.begin(
                race_key,
                race_claim.owner_token,
                race_claim.generation,
                now=_NOW,
            )
        except ReplayOperationBusyError:
            return "busy"
        return "claimed"

    with ThreadPoolExecutor(max_workers=len(stores)) as executor:
        outcomes = tuple(executor.map(attempt, stores))
    assert outcomes.count("claimed") == 1
    assert outcomes.count("busy") == len(stores) - 1
    assert race_store.count(cycle_id=_CYCLE_ID) == 1


def test_new_generation_takes_over_unfinished_operation_and_fences_old_owner(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-generation-fencing.sqlite3"
    claims, stages, operations, first_claim, parent_stage_key = _prepared_database(database)
    assert first_claim.owner_token is not None
    key = _action_key(parent_stage_key)
    first = operations.begin(
        key,
        first_claim.owner_token,
        first_claim.generation,
        now=_NOW,
    )
    assert first.status is ReplayOperationStatus.CLAIMED

    assert claims.release(_CYCLE_ID, first_claim.owner_token, first_claim.generation)
    second_claim = claims.claim(
        _CYCLE_ID,
        _CYCLE_FINGERPRINT,
        lease_seconds=600.0,
        now=_NOW,
    )
    assert second_claim.owner_token is not None
    assert second_claim.generation == first_claim.generation + 1
    stages.begin(
        parent_stage_key,
        second_claim.owner_token,
        second_claim.generation,
        now=_NOW,
    )

    taken_over = operations.begin(
        key,
        second_claim.owner_token,
        second_claim.generation,
        now=_NOW,
    )
    assert taken_over.status is ReplayOperationStatus.CLAIMED
    assert taken_over.generation == second_claim.generation
    assert taken_over.attempts == 2

    with pytest.raises(ReplayClaimOwnershipError):
        operations.complete(
            key,
            first_claim.owner_token,
            first_claim.generation,
            {"success": True},
            now=_NOW,
        )
    completed = operations.complete(
        key,
        second_claim.owner_token,
        second_claim.generation,
        {"success": True, "changed": False},
        now=_NOW,
    )
    assert completed.status is ReplayOperationStatus.COMPLETED


def test_rollback_requires_completed_parent_action_and_uses_separate_key(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-rollback-parent.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    action_key = _action_key(parent_stage_key)
    rollback_key = ReplayOperationKey.create(
        idempotency_key="optimizer-action-rollback:p3-2a:0",
        tenant_id="tenant:p3-2a",
        cycle_id=_CYCLE_ID,
        cycle_fingerprint=_CYCLE_FINGERPRINT,
        parent_stage_key=parent_stage_key.idempotency_key,
        operation_kind=ReplayOperationKind.ROLLBACK,
        operation_name="reduce_context_depth",
        ordinal=0,
        parent_operation_key=action_key.idempotency_key,
        input_payload={"undo": "removed-context:ctx-7"},
    )
    with pytest.raises(ReplayOperationParentError, match="parent Action operation is missing"):
        operations.begin(
            rollback_key,
            claim.owner_token,
            claim.generation,
            now=_NOW,
        )

    operations.begin(action_key, claim.owner_token, claim.generation, now=_NOW)
    operations.complete(
        action_key,
        claim.owner_token,
        claim.generation,
        {"success": True, "changed": True},
        now=_NOW,
    )
    rollback_claim = operations.begin(
        rollback_key,
        claim.owner_token,
        claim.generation,
        now=_NOW,
    )
    assert rollback_claim.status is ReplayOperationStatus.CLAIMED
    rollback_result = operations.complete(
        rollback_key,
        claim.owner_token,
        claim.generation,
        {"success": True, "rolled_back": True},
        now=_NOW,
    )
    assert rollback_result.status is ReplayOperationStatus.COMPLETED
    assert operations.count(cycle_id=_CYCLE_ID) == 2


def test_tampered_result_fails_closed_on_get_and_readiness_check(tmp_path: Path) -> None:
    database = tmp_path / "operation-result-integrity.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)
    operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    operations.complete(
        key,
        claim.owner_token,
        claim.generation,
        {"success": True, "changed": True},
        now=_NOW,
    )

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_operations SET result_json = ? "
            "WHERE tenant_scope = ? AND idempotency_key = ?",
            ('{"changed":false,"success":true}', key.tenant_scope, key.idempotency_key),
        )
    with pytest.raises(PersistentEvidenceIntegrityError):
        operations.get(key)
    with pytest.raises(PersistentReplayReadinessError, match="operation result"):
        check_database(database)


def _create_unversioned_legacy_database(database: Path) -> None:
    """Create the pre-G-C Evidence/Claim/Stage schema without migration metadata."""
    with sqlite3.connect(database, isolation_level=None) as connection:
        connection.executescript(
            """
            CREATE TABLE sh3_evidence_records (
                evidence_id TEXT PRIMARY KEY NOT NULL,
                record_json TEXT NOT NULL,
                integrity TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE sh3_replay_claims (
                cycle_id TEXT PRIMARY KEY NOT NULL,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('claimed', 'completed', 'released')),
                generation INTEGER NOT NULL,
                attempts INTEGER NOT NULL,
                owner_token TEXT,
                lease_expires_at REAL,
                evidence_id TEXT,
                updated_at REAL NOT NULL
            );
            CREATE INDEX sh3_replay_claims_state_idx
                ON sh3_replay_claims(state, lease_expires_at);
            CREATE TABLE sh3_replay_stage_executions (
                idempotency_key TEXT PRIMARY KEY NOT NULL,
                cycle_id TEXT NOT NULL,
                cycle_fingerprint TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('claimed', 'completed')),
                generation INTEGER NOT NULL CHECK (generation >= 1),
                attempts INTEGER NOT NULL CHECK (attempts >= 1),
                owner_token TEXT,
                result_json TEXT,
                result_integrity TEXT,
                updated_at REAL NOT NULL,
                FOREIGN KEY (cycle_id) REFERENCES sh3_replay_claims(cycle_id),
                CHECK (
                    (state = 'claimed' AND owner_token IS NOT NULL
                        AND result_json IS NULL AND result_integrity IS NULL)
                    OR
                    (state = 'completed' AND owner_token IS NULL
                        AND result_json IS NOT NULL AND result_integrity IS NOT NULL)
                )
            );
            CREATE INDEX sh3_replay_stage_cycle_state_idx
                ON sh3_replay_stage_executions(cycle_id, state);
            """
        )


def test_unversioned_legacy_database_requires_explicit_migration_and_validates_operation_table(
    tmp_path: Path,
) -> None:
    legacy_database = tmp_path / "legacy-without-operation-table.sqlite3"
    _create_unversioned_legacy_database(legacy_database)

    with sqlite3.connect(legacy_database) as connection:
        original_tables = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        )
        assert "sh3_schema_metadata" not in original_tables
        assert "sh3_replay_operations" not in original_tables
        assert "sh3_replay_operation_plans" not in original_tables
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)

    with pytest.raises(PersistentReplayReadinessError):
        check_database(legacy_database)
    with pytest.raises(PersistentSchemaMigrationRequiredError):
        SQLiteEvidenceStore(legacy_database)
    with pytest.raises(PersistentSchemaMigrationRequiredError):
        SQLiteReplayClaimStore(legacy_database)
    with pytest.raises(PersistentReplayReadinessError):
        create_persistent_replay_stores(legacy_database)

    # Rejected normal access must not auto-create metadata or missing tables.
    with sqlite3.connect(legacy_database) as connection:
        resulting_tables = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        )
        assert resulting_tables == original_tables
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)

    operations_database = tmp_path / "with-operation-table.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(operations_database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)
    operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    operations.complete(
        key,
        claim.owner_token,
        claim.generation,
        {"success": True, "changed": False},
        now=_NOW,
    )

    report = check_database(operations_database)
    assert report.replay_operation_execution_count == 1


def test_runtime_factory_and_explicit_provisioning_wire_operation_store(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runtime-operation-store.sqlite3"
    stores = create_persistent_replay_stores(database, create_if_missing=True)
    assert isinstance(stores.replay_operation_store, SQLiteReplayOperationStore)
    assert stores.replay_operation_store.database_path == stores.database_path
    assert check_database(database).replay_operation_execution_count == 0

    provisioned_database = tmp_path / "explicit-provisioned-operation-store.sqlite3"
    report = provision_persistent_replay_database(
        provisioned_database,
        confirm_first_use=True,
    )
    assert report.replay_operation_execution_count == 0
    reopened = create_persistent_replay_stores(provisioned_database)
    assert isinstance(reopened.replay_operation_store, SQLiteReplayOperationStore)


def test_readiness_rejects_active_operation_owned_by_wrong_claim_owner(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-readiness-owner-mismatch.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)
    operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_operations SET owner_token = ? "
            "WHERE tenant_scope = ? AND idempotency_key = ?",
            ("wrong-owner", key.tenant_scope, key.idempotency_key),
        )

    with pytest.raises(PersistentReplayReadinessError, match="operation result or row identity"):
        check_database(database)


@pytest.mark.parametrize(
    ("original_constraint", "replacement_constraint"),
    [
        (
            "ordinal INTEGER NOT NULL CHECK (ordinal >= 0)",
            "ordinal INTEGER NOT NULL",
        ),
        (
            "generation INTEGER NOT NULL CHECK (generation >= 1)",
            "generation INTEGER NOT NULL",
        ),
        (
            "attempts INTEGER NOT NULL CHECK (attempts >= 1)",
            "attempts INTEGER NOT NULL",
        ),
    ],
)
def test_readiness_rejects_missing_operation_numeric_check_constraints(
    tmp_path: Path,
    original_constraint: str,
    replacement_constraint: str,
) -> None:
    database = tmp_path / "operation-missing-numeric-check.sqlite3"
    _prepared_database(database)

    with sqlite3.connect(database) as connection:
        schema_row = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'sh3_replay_operations'"
        ).fetchone()
    assert schema_row is not None
    schema_sql = str(schema_row[0])
    assert schema_sql.count(original_constraint) == 1
    schema_sql = schema_sql.replace(
        original_constraint,
        replacement_constraint,
        1,
    )

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE sh3_replay_operations")
        connection.execute(schema_sql)
        connection.execute(
            "CREATE INDEX sh3_replay_operations_cycle_state_idx "
            "ON sh3_replay_operations(cycle_id, state)"
        )
        connection.execute(
            "CREATE INDEX sh3_replay_operations_parent_stage_idx "
            "ON sh3_replay_operations(parent_stage_key, operation_kind, ordinal)"
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="does not enforce the required operation checks",
    ):
        check_database(database)


def test_operation_ledger_survives_online_backup_and_restore(tmp_path: Path) -> None:
    database = tmp_path / "operation-backup-source.sqlite3"
    backup = tmp_path / "operation-backup.sqlite3"
    restored_database = tmp_path / "operation-restored.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)
    operations.begin(key, claim.owner_token, claim.generation, now=_NOW)
    expected_result = {
        "success": True,
        "changed": True,
        "operation": "reduce_context_depth",
    }
    operations.complete(
        key,
        claim.owner_token,
        claim.generation,
        expected_result,
        now=_NOW,
    )

    backup_report = backup_database(database, backup)
    assert backup_report.replay_operation_execution_count == 1

    restore_report = restore_database(backup, restored_database)
    assert restore_report.replay_operation_execution_count == 1

    restored_store = SQLiteReplayOperationStore(restored_database)
    restored = restored_store.get(key)
    assert restored is not None
    assert restored.status is ReplayOperationStatus.COMPLETED
    assert restored.result == expected_result
    assert restored.generation == claim.generation
def test_readiness_rejects_missing_operation_state_index(tmp_path: Path) -> None:
    database = tmp_path / "operation-missing-index.sqlite3"
    _, _, _, _, _ = _prepared_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX sh3_replay_operations_cycle_state_idx")

    with pytest.raises(
        PersistentReplayReadinessError,
        match="missing required index sh3_replay_operations_cycle_state_idx",
    ):
        check_database(database)

def _p3_2f_stop_processes(processes: list[Any]) -> None:
    """Terminate and reap test child processes without leaving orphans."""
    for process in processes:
        if process.pid is None:
            continue
        if process.is_alive():
            process.terminate()
        process.join(timeout=5.0)


def _p3_2f_operation_begin_worker(
    database_path: str,
    key: ReplayOperationKey,
    owner_token: str,
    generation: int,
    now: datetime,
    timeout_seconds: float,
    ready_event: Any,
    start_event: Any,
    result_queue: Any,
) -> None:
    """Attempt one Operation begin from an independently spawned process."""
    try:
        store = SQLiteReplayOperationStore(
            database_path,
            timeout_seconds=timeout_seconds,
        )
        ready_event.set()
        if not start_event.wait(timeout=20.0):
            result_queue.put(("error", "start barrier timed out", ""))
            return
        execution = store.begin(
            key,
            owner_token,
            generation,
            now=now,
        )
        result_queue.put(
            ("claimed", execution.generation, execution.attempts)
        )
    except ReplayOperationBusyError:
        ready_event.set()
        result_queue.put(("busy", 0, 0))
    except Exception as exc:
        ready_event.set()
        result_queue.put(
            ("error", type(exc).__name__, str(exc))
        )


def _p3_2f_operation_lock_timeout_worker(
    database_path: str,
    key: ReplayOperationKey,
    owner_token: str,
    generation: int,
    now: datetime,
    ready_event: Any,
    start_event: Any,
    result_queue: Any,
) -> None:
    """Attempt begin after another process has acquired the SQLite write lock."""
    try:
        store = SQLiteReplayOperationStore(
            database_path,
            timeout_seconds=0.15,
        )
        ready_event.set()
        if not start_event.wait(timeout=20.0):
            result_queue.put(("error", "start barrier timed out", None))
            return
        try:
            store.begin(
                key,
                owner_token,
                generation,
                now=now,
            )
        except sqlite3.OperationalError as exc:
            result_queue.put(
                (
                    "locked",
                    str(exc),
                    getattr(exc, "sqlite_errorcode", None),
                )
            )
        else:
            result_queue.put(("unexpected_success", "", None))
    except Exception as exc:
        ready_event.set()
        result_queue.put(
            ("error", f"{type(exc).__name__}: {exc}", None)
        )


def _p3_2f_operation_takeover_worker(
    database_path: str,
    key: ReplayOperationKey,
    owner_token: str,
    generation: int,
    now: datetime,
    result_queue: Any,
) -> None:
    """Take over an unfinished Operation using the new parent generation."""
    try:
        execution = SQLiteReplayOperationStore(
            database_path,
            timeout_seconds=5.0,
        ).begin(
            key,
            owner_token,
            generation,
            now=now,
        )
        result_queue.put(
            ("claimed", execution.generation, execution.attempts)
        )
    except Exception as exc:
        result_queue.put(
            ("error", type(exc).__name__, str(exc))
        )


def _p3_2f_operation_stale_complete_worker(
    database_path: str,
    key: ReplayOperationKey,
    old_owner_token: str,
    old_generation: int,
    now: datetime,
    result_queue: Any,
) -> None:
    """Attempt completion with a stale owner from another process."""
    try:
        SQLiteReplayOperationStore(
            database_path,
            timeout_seconds=5.0,
        ).complete(
            key,
            old_owner_token,
            old_generation,
            {"success": True, "stale_owner": True},
            now=now,
        )
    except ReplayClaimOwnershipError:
        result_queue.put(("fenced",))
    except Exception as exc:
        result_queue.put(
            ("error", type(exc).__name__, str(exc))
        )
    else:
        result_queue.put(("completed",))


def test_operation_begin_is_atomic_across_processes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-multiprocess-begin.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)

    worker_count = 4
    context = mp.get_context("spawn")
    start_event = context.Event()
    ready_events = [context.Event() for _ in range(worker_count)]
    result_queue = context.Queue()
    processes: list[Any] = []

    try:
        for ready_event in ready_events:
            process = context.Process(
                target=_p3_2f_operation_begin_worker,
                args=(
                    str(database),
                    key,
                    claim.owner_token,
                    claim.generation,
                    _NOW,
                    10.0,
                    ready_event,
                    start_event,
                    result_queue,
                ),
            )
            process.start()
            processes.append(process)

        for ready_event in ready_events:
            assert ready_event.wait(timeout=20.0), (
                "A worker did not finish initialization before the start gate."
            )

        # All workers are initialized before any worker enters begin().
        start_event.set()

        outcomes = [
            result_queue.get(timeout=20.0)
            for _ in range(worker_count)
        ]

        for process in processes:
            process.join(timeout=20.0)
            assert not process.is_alive(), "A worker process did not exit."
            assert process.exitcode == 0

    finally:
        start_event.set()
        _p3_2f_stop_processes(processes)
        result_queue.close()
        result_queue.join_thread()

    statuses = [outcome[0] for outcome in outcomes]
    assert statuses.count("claimed") == 1, outcomes
    assert statuses.count("busy") == worker_count - 1, outcomes
    assert all(status in {"claimed", "busy"} for status in statuses), outcomes

    claimed_outcome = next(
        outcome for outcome in outcomes if outcome[0] == "claimed"
    )
    assert claimed_outcome[1:] == (claim.generation, 1)
    assert operations.count(cycle_id=_CYCLE_ID) == 1


def test_operation_begin_observes_cross_process_sqlite_writer_lock_timeout(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-multiprocess-lock-timeout.sqlite3"
    _, _, operations, claim, parent_stage_key = _prepared_database(database)
    assert claim.owner_token is not None
    key = _action_key(parent_stage_key)

    context = mp.get_context("spawn")
    ready_event = context.Event()
    start_event = context.Event()
    result_queue = context.Queue()
    process = context.Process(
        target=_p3_2f_operation_lock_timeout_worker,
        args=(
            str(database),
            key,
            claim.owner_token,
            claim.generation,
            _NOW,
            ready_event,
            start_event,
            result_queue,
        ),
    )
    processes: list[Any] = []
    lock_connection: sqlite3.Connection | None = None

    try:
        process.start()
        processes.append(process)

        # The child constructs its store before the parent takes the write lock.
        assert ready_event.wait(timeout=20.0), (
            "The child did not initialize its Operation Store."
        )

        lock_connection = sqlite3.connect(
            str(database),
            timeout=5.0,
            isolation_level=None,
        )
        lock_connection.execute("BEGIN IMMEDIATE")

        # The child now attempts BEGIN IMMEDIATE while this process holds it.
        start_event.set()
        outcome = result_queue.get(timeout=10.0)

        process.join(timeout=10.0)
        assert not process.is_alive(), "The lock-timeout worker did not exit."
        assert process.exitcode == 0

    finally:
        start_event.set()
        _p3_2f_stop_processes(processes)

        if lock_connection is not None:
            if lock_connection.in_transaction:
                lock_connection.execute("ROLLBACK")
            lock_connection.close()

        result_queue.close()
        result_queue.join_thread()

    assert outcome[0] == "locked", outcome
    assert "locked" in outcome[1].lower(), outcome
    assert isinstance(outcome[2], int), outcome
    assert (outcome[2] & 0xFF) == sqlite3.SQLITE_BUSY, outcome

    # The failed begin must not leave an Operation row behind.
    assert operations.count(cycle_id=_CYCLE_ID) == 0


def test_operation_generation_fences_old_process_owner(
    tmp_path: Path,
) -> None:
    database = tmp_path / "operation-multiprocess-generation-fencing.sqlite3"
    claims, stages, operations, first_claim, parent_stage_key = (
        _prepared_database(database)
    )
    assert first_claim.owner_token is not None
    key = _action_key(parent_stage_key)

    original = operations.begin(
        key,
        first_claim.owner_token,
        first_claim.generation,
        now=_NOW,
    )
    assert original.status is ReplayOperationStatus.CLAIMED
    assert original.generation == first_claim.generation

    # Release the first parent generation and acquire a newer generation.
    assert claims.release(
        _CYCLE_ID,
        first_claim.owner_token,
        first_claim.generation,
        now=_NOW,
    )

    second_claim = claims.claim(
        _CYCLE_ID,
        _CYCLE_FINGERPRINT,
        lease_seconds=600.0,
        now=_NOW,
    )
    assert second_claim.status is ReplayClaimStatus.CLAIMED
    assert second_claim.owner_token is not None
    assert second_claim.generation == first_claim.generation + 1

    second_stage = stages.begin(
        parent_stage_key,
        second_claim.owner_token,
        second_claim.generation,
        now=_NOW,
    )
    assert second_stage.status is ReplayStageStatus.CLAIMED

    context = mp.get_context("spawn")
    result_queue = context.Queue()
    processes: list[Any] = []

    try:
        # Process 1 takes over the unfinished Operation in the new generation.
        takeover_process = context.Process(
            target=_p3_2f_operation_takeover_worker,
            args=(
                str(database),
                key,
                second_claim.owner_token,
                second_claim.generation,
                _NOW,
                result_queue,
            ),
        )
        takeover_process.start()
        processes.append(takeover_process)

        takeover_outcome = result_queue.get(timeout=15.0)
        takeover_process.join(timeout=15.0)
        assert not takeover_process.is_alive()
        assert takeover_process.exitcode == 0
        assert takeover_outcome == (
            "claimed",
            second_claim.generation,
            2,
        )

        # Process 2 tries to complete using the previous owner's credentials.
        stale_process = context.Process(
            target=_p3_2f_operation_stale_complete_worker,
            args=(
                str(database),
                key,
                first_claim.owner_token,
                first_claim.generation,
                _NOW,
                result_queue,
            ),
        )
        stale_process.start()
        processes.append(stale_process)

        stale_outcome = result_queue.get(timeout=15.0)
        stale_process.join(timeout=15.0)
        assert not stale_process.is_alive()
        assert stale_process.exitcode == 0
        assert stale_outcome == ("fenced",)

    finally:
        _p3_2f_stop_processes(processes)
        result_queue.close()
        result_queue.join_thread()

    restored = operations.get(key)
    assert restored is not None
    assert restored.status is ReplayOperationStatus.CLAIMED
    assert restored.generation == second_claim.generation
    assert restored.attempts == 2
    assert restored.owner_token == second_claim.owner_token
