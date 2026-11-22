from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security.persistent_operation_store import (
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_replay_ops import (
    backup_database,
    check_database,
    restore_database,
)
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    ReplayStageKey,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel.recovery_execution_boundary import RecoveryExecutionBoundary
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary
from kernel.replay_execution_context import DurableOperationPersistenceError
from self_healing.core import FailureSnapshot, SelfHealingCore

NOW = datetime.now(UTC)
CYCLE_ID = "learning-cycle:p3-2d-recovery-failure-matrix"
CYCLE_FINGERPRINT = "sha256:" + "2d" * 32
TENANT_ID = "tenant:p3-2d-recovery-failure-matrix"
RECOVERY_STAGE_NAME = "recovery_execution.execute.v1"
TERMINAL_EVENT_NAMES = (
    "RecoveryExecutionCompleted",
    "RecoveryExecutionFailed",
)


def _stores(database: Path) -> tuple[
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
    SQLiteReplayOperationStore,
]:
    evidence = SQLiteEvidenceStore(database)
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    operations = SQLiteReplayOperationStore(database)
    return evidence, claims, stages, operations


def _claim(claims: SQLiteReplayClaimStore) -> Any:
    claim = claims.claim(
        CYCLE_ID,
        CYCLE_FINGERPRINT,
        lease_seconds=3600.0,
        now=datetime.now(UTC),
    )
    assert claim.status is ReplayClaimStatus.CLAIMED
    assert claim.owner_token is not None
    return claim


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="p3-2d-correlation",
        causation_id="p3-2d-causation",
        trace_id="p3-2d-trace",
        tenant_id=TENANT_ID,
    )


class _RecoveryBackend(SelfHealingCore):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.calls = 0
        self.keys: list[str | None] = []
        self.fail = fail

    def recover_with_strategy(
        self,
        snapshot: FailureSnapshot,
        strategy: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        self.keys.append(idempotency_key)
        if self.fail:
            raise RuntimeError("injected P3-2D Recovery backend failure")
        return {
            "success": True,
            "strategy": strategy,
            "idempotency_key": idempotency_key,
        }


class _DurableDeduplicatingRecoveryBackend(SelfHealingCore):
    """Fake downstream system that durably deduplicates the P3-1A key."""

    def __init__(self, database: Path) -> None:
        super().__init__()
        self.database = database
        self.calls = 0
        self.keys: list[str | None] = []
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS external_recovery_effects ("
                "idempotency_key TEXT PRIMARY KEY, "
                "strategy TEXT NOT NULL, effect_id TEXT NOT NULL)"
            )

    def recover_with_strategy(
        self,
        snapshot: FailureSnapshot,
        strategy: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _ = snapshot
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("persistent Recovery requires an idempotency key")
        self.calls += 1
        self.keys.append(idempotency_key)
        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                "SELECT strategy, effect_id FROM external_recovery_effects "
                "WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                effect_id = f"external-effect:{idempotency_key}"
                connection.execute(
                    "INSERT INTO external_recovery_effects "
                    "(idempotency_key, strategy, effect_id) VALUES (?, ?, ?)",
                    (idempotency_key, strategy, effect_id),
                )
            else:
                if row[0] != strategy:
                    raise ValueError(
                        "downstream idempotency key was reused with conflicting input"
                    )
                effect_id = str(row[1])
        return {
            "effect_id": effect_id,
            "idempotency_key": idempotency_key,
            "strategy": strategy,
        }


def _request(
    boundary: RecoveryExecutionBoundary,
    backend: SelfHealingCore,
    claim: Any,
) -> Any:
    context = _context()
    snapshot = FailureSnapshot.create(
        RuntimeError("stable P3-2D Recovery input"),
        {"source": "p3-2d-failure-matrix"},
    )
    strategy_result = RecoveryStrategyBoundary(backend).request(
        snapshot,
        context=context,
        created_at=NOW,
    )
    return boundary.request(
        strategy_result,
        snapshot,
        context=context,
        created_at=NOW,
        replay_cycle_id=CYCLE_ID,
        replay_cycle_fingerprint=CYCLE_FINGERPRINT,
        replay_claim_owner_token=claim.owner_token,
        replay_claim_generation=claim.generation,
        replay_stage_input={
            "source": "p3-2d-failure-matrix",
            "result_id": "stable-result:p3-2d",
            "error_type": "RuntimeError",
            "error_message": "stable P3-2D Recovery input",
        },
    )


def _observe_terminal_events(
    bus: EventBus,
    handler: Callable[[Event], None],
) -> None:
    for event_name in TERMINAL_EVENT_NAMES:
        bus.subscribe(
            EventSubscription(
                subscriber_id=f"p3-2d-observer:{event_name}",
                handler=handler,
                event_name=event_name,
            )
        )


def _read_replay_states(database: Path) -> tuple[str | None, str | None]:
    with sqlite3.connect(database) as connection:
        operation = connection.execute(
            "SELECT state FROM sh3_replay_operations "
            "WHERE cycle_id = ? AND operation_name = 'recovery_execution'",
            (CYCLE_ID,),
        ).fetchone()
        stage = connection.execute(
            "SELECT state FROM sh3_replay_stage_executions "
            "WHERE cycle_id = ? AND stage_name = ?",
            (CYCLE_ID, RECOVERY_STAGE_NAME),
        ).fetchone()
    return (
        None if operation is None else str(operation[0]),
        None if stage is None else str(stage[0]),
    )


@pytest.mark.parametrize(
    ("backend_fails", "expected_event"),
    [
        (False, "RecoveryExecutionCompleted"),
        (True, "RecoveryExecutionFailed"),
    ],
)
def test_terminal_event_observes_committed_operation_and_stage(
    tmp_path: Path,
    backend_fails: bool,
    expected_event: str,
) -> None:
    database = tmp_path / f"terminal-event-{backend_fails}.sqlite3"
    _, claims, stages, operations = _stores(database)
    claim = _claim(claims)
    bus = EventBus()
    observed: list[tuple[str, str | None, str | None]] = []

    def observe(event: Event) -> None:
        operation_state, stage_state = _read_replay_states(database)
        observed.append((event.name, operation_state, stage_state))

    _observe_terminal_events(bus, observe)
    backend = _RecoveryBackend(fail=backend_fails)
    boundary = RecoveryExecutionBoundary(
        backend,
        event_publisher=EventBusPublisher(bus),
        replay_stage_store=stages,
        replay_operation_store=operations,
    )

    result = _request(boundary, backend, claim)

    assert result.success is (not backend_fails)
    assert observed == [(expected_event, "completed", "completed")]


@pytest.mark.parametrize(
    "fault",
    ["operation_claim", "operation_complete", "sqlite_lock", "stage_complete"],
)
def test_persistence_faults_do_not_publish_recovery_terminal_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fault: str,
) -> None:
    database = tmp_path / f"terminal-event-suppressed-{fault}.sqlite3"
    _, claims, stages, operations = _stores(database)
    claim = _claim(claims)
    bus = EventBus()
    observed: list[str] = []
    _observe_terminal_events(bus, lambda event: observed.append(event.name))
    backend = _RecoveryBackend()
    boundary = RecoveryExecutionBoundary(
        backend,
        event_publisher=EventBusPublisher(bus),
        replay_stage_store=stages,
        replay_operation_store=operations,
    )

    if fault == "operation_claim":
        original_begin = SQLiteReplayOperationStore.begin

        def fail_operation_claim(
            store: SQLiteReplayOperationStore,
            key: Any,
            owner_token: str,
            generation: int,
            *,
            now: datetime | None = None,
        ) -> Any:
            if key.operation_name == "recovery_execution":
                raise OSError("injected Operation claim failure")
            return original_begin(
                store, key, owner_token, generation, now=now
            )

        monkeypatch.setattr(SQLiteReplayOperationStore, "begin", fail_operation_claim)
    elif fault in {"operation_complete", "sqlite_lock"}:
        original_complete = SQLiteReplayOperationStore.complete

        def fail_operation_complete(
            store: SQLiteReplayOperationStore,
            key: Any,
            owner_token: str,
            generation: int,
            result: Any,
            *,
            now: datetime | None = None,
        ) -> Any:
            if key.operation_name == "recovery_execution":
                if fault == "sqlite_lock":
                    raise sqlite3.OperationalError("database is locked")
                raise OSError("injected Operation completion failure")
            return original_complete(
                store, key, owner_token, generation, result, now=now
            )

        monkeypatch.setattr(
            SQLiteReplayOperationStore, "complete", fail_operation_complete
        )
    else:
        original_stage_complete = SQLiteReplayStageStore.complete

        def fail_stage_complete(
            store: SQLiteReplayStageStore,
            key: ReplayStageKey,
            owner_token: str,
            generation: int,
            result: Any,
            *,
            now: datetime | None = None,
        ) -> Any:
            if key.stage_name == RECOVERY_STAGE_NAME:
                raise OSError("injected Recovery Stage completion failure")
            return original_stage_complete(
                store, key, owner_token, generation, result, now=now
            )

        monkeypatch.setattr(
            SQLiteReplayStageStore, "complete", fail_stage_complete
        )

    with pytest.raises(DurableOperationPersistenceError):
        _request(boundary, backend, claim)

    assert observed == []
    if fault == "operation_claim":
        assert backend.calls == 0
        assert _read_replay_states(database) == (None, "claimed")
    elif fault in {"operation_complete", "sqlite_lock"}:
        assert backend.calls == 1
        assert _read_replay_states(database) == ("claimed", "claimed")
    else:
        assert backend.calls == 1
        assert _read_replay_states(database) == ("completed", "claimed")


def test_external_effect_is_deduplicated_when_operation_commit_is_retried(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-operation-retry.sqlite3"
    effects_database = tmp_path / "external-effects.sqlite3"
    _, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    first_backend = _DurableDeduplicatingRecoveryBackend(effects_database)
    first_boundary = RecoveryExecutionBoundary(
        first_backend,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )
    original_complete = SQLiteReplayOperationStore.complete
    fail_once = True

    def fail_first_operation_complete(
        store: SQLiteReplayOperationStore,
        key: Any,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        nonlocal fail_once
        if key.operation_name == "recovery_execution" and fail_once:
            fail_once = False
            raise OSError("injected crash-window Operation completion failure")
        return original_complete(
            store, key, owner_token, generation, result, now=now
        )

    monkeypatch.setattr(
        SQLiteReplayOperationStore,
        "complete",
        fail_first_operation_complete,
    )

    with pytest.raises(DurableOperationPersistenceError):
        _request(first_boundary, first_backend, first_claim)

    assert first_backend.calls == 1
    assert _read_replay_states(database) == ("claimed", "claimed")
    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)

    second_claim = _claim(claims)
    second_backend = _DurableDeduplicatingRecoveryBackend(effects_database)
    second_boundary = RecoveryExecutionBoundary(
        second_backend,
        replay_stage_store=SQLiteReplayStageStore(database),
        replay_operation_store=SQLiteReplayOperationStore(database),
    )
    restored = _request(second_boundary, second_backend, second_claim)

    assert restored.success is True
    assert first_backend.calls == 1
    assert second_backend.calls == 1
    assert first_backend.keys == second_backend.keys
    assert first_backend.keys[0] is not None
    assert restored.result["effect_id"] == f"external-effect:{first_backend.keys[0]}"
    with sqlite3.connect(effects_database) as connection:
        effect_count = connection.execute(
            "SELECT COUNT(*) FROM external_recovery_effects"
        ).fetchone()[0]
    assert effect_count == 1
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT state, attempts FROM sh3_replay_operations "
            "WHERE operation_name = 'recovery_execution'"
        ).fetchone()
    assert row == ("completed", 2)


def test_backup_restore_recovers_completed_operation_without_backend_reexecution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-backup-source.sqlite3"
    backup = tmp_path / "recovery-backup.sqlite3"
    restored_database = tmp_path / "recovery-restored.sqlite3"
    _, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    first_backend = _RecoveryBackend()
    first_boundary = RecoveryExecutionBoundary(
        first_backend,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )
    original_stage_complete = SQLiteReplayStageStore.complete

    def fail_stage_finalize(
        store: SQLiteReplayStageStore,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        if key.stage_name == RECOVERY_STAGE_NAME:
            raise OSError("injected interruption after Operation commit")
        return original_stage_complete(
            store, key, owner_token, generation, result, now=now
        )

    with monkeypatch.context() as patcher:
        patcher.setattr(SQLiteReplayStageStore, "complete", fail_stage_finalize)
        with pytest.raises(DurableOperationPersistenceError):
            _request(first_boundary, first_backend, first_claim)

    assert first_backend.calls == 1
    assert _read_replay_states(database) == ("completed", "claimed")

    backup_report = backup_database(database, backup)
    restore_report = restore_database(backup, restored_database)
    readiness = check_database(restored_database)
    assert backup_report.replay_operation_execution_count == 1
    assert restore_report.replay_operation_execution_count == 1
    assert readiness.replay_operation_execution_count == 1

    _, restored_claims, restored_stages, restored_operations = _stores(
        restored_database
    )
    assert restored_claims.release(
        CYCLE_ID, first_claim.owner_token, first_claim.generation
    )
    next_claim = _claim(restored_claims)
    bus = EventBus()
    restored_events: list[str] = []
    _observe_terminal_events(
        bus, lambda event: restored_events.append(event.name)
    )
    second_backend = _RecoveryBackend()
    second_boundary = RecoveryExecutionBoundary(
        second_backend,
        event_publisher=EventBusPublisher(bus),
        replay_stage_store=restored_stages,
        replay_operation_store=restored_operations,
    )

    restored = _request(second_boundary, second_backend, next_claim)

    assert restored.success is True
    assert restored.result == {
        "success": True,
        "strategy": restored.strategy,
        "idempotency_key": first_backend.keys[0],
    }
    assert second_backend.calls == 0
    assert restored_events == []
    assert _read_replay_states(restored_database) == ("completed", "completed")


def test_tampered_completed_operation_fails_closed_without_backend_or_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-operation-tampered.sqlite3"
    _, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    first_backend = _RecoveryBackend()
    first_boundary = RecoveryExecutionBoundary(
        first_backend,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )
    original_stage_complete = SQLiteReplayStageStore.complete

    def fail_stage_finalize(
        store: SQLiteReplayStageStore,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        if key.stage_name == RECOVERY_STAGE_NAME:
            raise OSError("injected interruption after Operation commit")
        return original_stage_complete(
            store, key, owner_token, generation, result, now=now
        )

    with monkeypatch.context() as patcher:
        patcher.setattr(SQLiteReplayStageStore, "complete", fail_stage_finalize)
        with pytest.raises(DurableOperationPersistenceError):
            _request(first_boundary, first_backend, first_claim)

    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_operations SET result_json = ? "
            "WHERE cycle_id = ? AND operation_name = 'recovery_execution'",
            ('{"schema_version":1,"success":true,"result":{"tampered":true}}', CYCLE_ID),
        )

    next_claim = _claim(claims)
    bus = EventBus()
    observed: list[str] = []
    _observe_terminal_events(bus, lambda event: observed.append(event.name))
    second_backend = _RecoveryBackend()
    second_boundary = RecoveryExecutionBoundary(
        second_backend,
        event_publisher=EventBusPublisher(bus),
        replay_stage_store=SQLiteReplayStageStore(database),
        replay_operation_store=SQLiteReplayOperationStore(database),
    )

    with pytest.raises(DurableOperationPersistenceError):
        _request(second_boundary, second_backend, next_claim)

    assert second_backend.calls == 0
    assert observed == []
    assert _read_replay_states(database) == ("completed", "claimed")
