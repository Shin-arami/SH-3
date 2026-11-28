from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from infrastructure.event_bus import EventBus, EventBusPublisher
from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_operation_store import (
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    ReplayStageKey,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel.learning_optimizer_boundary import LearningOptimizationResult
from kernel.recovery_execution_boundary import RecoveryExecutionBoundary
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary
from kernel.replay_execution_context import DurableOperationPersistenceError
from kernel.system_optimizer import SystemOptimizer
from self_healing.core import FailureSnapshot, SelfHealingCore
from tests.kernel.test_persistent_learning_closed_loop_restart import _result

NOW = datetime.now(UTC)
CYCLE_ID = "learning-cycle:p3-2c-recovery-ledger"
CYCLE_FINGERPRINT = "sha256:" + "2c" * 32
TENANT_ID = "tenant:p3-2c-recovery-ledger"


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


def _claim(claims: SQLiteReplayClaimStore, cycle_id: str = CYCLE_ID) -> Any:
    claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=3600.0,
        now=datetime.now(UTC),
    )
    assert claim.status is ReplayClaimStatus.CLAIMED
    assert claim.owner_token is not None
    return claim


def _context(causation_id: str = "p3-2c-recovery") -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="p3-2c-correlation",
        causation_id=causation_id,
        trace_id="p3-2c-trace",
        tenant_id=TENANT_ID,
    )


class _CountingRecoveryBackend(SelfHealingCore):
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
            raise RuntimeError("injected durable recovery failure")
        return {
            "success": True,
            "strategy": strategy,
            "backend_call": self.calls,
            "idempotency_key": idempotency_key,
        }


def _strategy(
    backend: SelfHealingCore,
    *,
    message: str = "stable recovery input",
    context: EventPropagationContext | None = None,
) -> tuple[Any, FailureSnapshot]:
    snapshot = FailureSnapshot.create(
        RuntimeError(message),
        {"source": "p3-2c-test"},
    )
    strategy_result = RecoveryStrategyBoundary(backend).request(
        snapshot,
        context=context or _context(),
        created_at=NOW,
    )
    return strategy_result, snapshot


def _request(
    boundary: RecoveryExecutionBoundary,
    backend: SelfHealingCore,
    claim: Any,
    *,
    cycle_id: str = CYCLE_ID,
    context: EventPropagationContext | None = None,
) -> Any:
    propagation = context or _context()
    strategy_result, snapshot = _strategy(backend, context=propagation)
    return boundary.request(
        strategy_result,
        snapshot,
        context=propagation,
        created_at=NOW,
        replay_cycle_id=cycle_id,
        replay_cycle_fingerprint=CYCLE_FINGERPRINT,
        replay_claim_owner_token=claim.owner_token,
        replay_claim_generation=claim.generation,
        replay_stage_input={
            "source": "optimizer",
            "result_id": "stable-result:p3-2c",
            "error_type": "RuntimeError",
            "error_message": "stable recovery input",
        },
    )


def test_recovery_execution_persists_successful_operation_outcome(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-operation-success.sqlite3"
    _, claims, stages, operations = _stores(database)
    claim = _claim(claims)
    backend = _CountingRecoveryBackend()
    boundary = RecoveryExecutionBoundary(
        backend,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )

    result = _request(boundary, backend, claim)

    assert result.success is True
    assert backend.calls == 1
    assert backend.keys and backend.keys[0]
    assert operations.count(cycle_id=CYCLE_ID) == 1
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT operation_kind, operation_name, state, ordinal "
            "FROM sh3_replay_operations WHERE cycle_id = ?",
            (CYCLE_ID,),
        ).fetchone()
    assert row == ("action", "recovery_execution", "completed", 0)


def test_completed_operation_restores_stage_after_stage_finalize_interruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-operation-stage-retry.sqlite3"
    _, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    first_backend = _CountingRecoveryBackend()
    first_boundary = RecoveryExecutionBoundary(
        first_backend,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )

    original_complete = SQLiteReplayStageStore.complete
    fail_once = True

    def fail_first_recovery_stage_finalize(
        store: SQLiteReplayStageStore,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        nonlocal fail_once
        if key.stage_name == "recovery_execution.execute.v1" and fail_once:
            fail_once = False
            raise OSError("injected Stage finalization interruption")
        return original_complete(
            store, key, owner_token, generation, result, now=now
        )

    monkeypatch.setattr(
        SQLiteReplayStageStore,
        "complete",
        fail_first_recovery_stage_finalize,
    )

    with pytest.raises(DurableOperationPersistenceError):
        _request(first_boundary, first_backend, first_claim)

    assert first_backend.calls == 1
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)

    second_claim = _claim(claims)
    assert second_claim.generation == first_claim.generation + 1
    second_stages = SQLiteReplayStageStore(database)
    second_operations = SQLiteReplayOperationStore(database)
    second_backend = _CountingRecoveryBackend()
    second_boundary = RecoveryExecutionBoundary(
        second_backend,
        replay_stage_store=second_stages,
        replay_operation_store=second_operations,
    )

    restored = _request(second_boundary, second_backend, second_claim)

    assert restored.success is True
    assert restored.result["backend_call"] == 1
    assert first_backend.calls == 1
    assert second_backend.calls == 0
    assert second_operations.count(cycle_id=CYCLE_ID) == 1
    with sqlite3.connect(database) as connection:
        stage_state = connection.execute(
            "SELECT state FROM sh3_replay_stage_executions "
            "WHERE stage_name = 'recovery_execution.execute.v1'"
        ).fetchone()
    assert stage_state == ("completed",)


def test_failed_recovery_outcome_is_a_terminal_durable_operation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-operation-failure.sqlite3"
    _, claims, stages, operations = _stores(database)
    claim = _claim(claims)
    backend = _CountingRecoveryBackend(fail=True)
    boundary = RecoveryExecutionBoundary(
        backend,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )

    result = _request(boundary, backend, claim)

    assert result.success is False
    assert result.error == "injected durable recovery failure"
    assert backend.calls == 1
    assert operations.count(cycle_id=CYCLE_ID) == 1
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT state, result_json FROM sh3_replay_operations "
            "WHERE cycle_id = ?",
            (CYCLE_ID,),
        ).fetchone()
    assert row is not None
    assert row[0] == "completed"
    assert '"success":false' in row[1]


def test_durable_recovery_error_is_not_swallowed_by_optimizer_healing_event_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "healing-boundary-durable-error.sqlite3"
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    from kernel.persistent_factory import create_persistent_sh3_kernel

    runtime = create_persistent_sh3_kernel(
        database,
        event_publisher=publisher,
        create_if_missing=True,
    )
    claim = _claim(runtime.stores.replay_claim_store)
    optimization = LearningOptimizationResult(
        request_id="p3-2c-optimization-request",
        learning_record_id="p3-2c-learning-record",
        optimizer_id="p3-2c-optimizer",
        success=False,
        optimization={},
        created_at=NOW,
        correlation_id="p3-2c-correlation",
        trace_id="p3-2c-trace",
        tenant_id=TENANT_ID,
        error="injected optimizer failure",
    )
    original_complete = SQLiteReplayOperationStore.complete

    def fail_recovery_operation_complete(
        store: SQLiteReplayOperationStore,
        key: Any,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        if key.operation_name == "recovery_execution":
            raise OSError("injected Recovery operation ledger write failure")
        return original_complete(
            store, key, owner_token, generation, result, now=now
        )

    monkeypatch.setattr(
        SQLiteReplayOperationStore,
        "complete",
        fail_recovery_operation_complete,
    )

    with pytest.raises(DurableOperationPersistenceError):
        runtime.kernel.optimizer_healing_boundary.request(
            optimization,
            context=_context(),
            created_at=NOW,
            replay_cycle_id=CYCLE_ID,
            replay_cycle_fingerprint=CYCLE_FINGERPRINT,
            replay_claim_owner_token=claim.owner_token,
            replay_claim_generation=claim.generation,
            replay_stage_input={
                "source": "optimizer",
                "result_id": "stable-result:p3-2c",
                "optimizer_id": optimization.optimizer_id,
                "learning_record_id": optimization.learning_record_id,
                "optimization_request_id": optimization.request_id,
                "error_type": "OptimizerExecutionFailure",
                "error_message": "injected optimizer failure",
            },
        )

    replay_operation_store = runtime.stores.replay_operation_store
    assert replay_operation_store is not None
    assert replay_operation_store.count(cycle_id=CYCLE_ID) == 1


def test_operation_ledger_failure_propagates_through_optimizer_healing_and_coordinator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-operation-fail-closed.sqlite3"
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    from kernel.persistent_factory import create_persistent_sh3_kernel

    runtime = create_persistent_sh3_kernel(
        database,
        event_publisher=publisher,
        create_if_missing=True,
    )

    def fail_optimizer(
        optimizer: SystemOptimizer,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _ = (optimizer, context, execute, idempotency_key)
        raise RuntimeError("injected optimizer failure for Recovery replay")

    original_complete = SQLiteReplayOperationStore.complete

    def fail_recovery_operation_complete(
        store: SQLiteReplayOperationStore,
        key: Any,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        if key.operation_name == "recovery_execution":
            raise OSError("injected Recovery operation ledger write failure")
        return original_complete(
            store, key, owner_token, generation, result, now=now
        )

    monkeypatch.setattr(SystemOptimizer, "optimize", fail_optimizer)
    monkeypatch.setattr(
        SQLiteReplayOperationStore,
        "complete",
        fail_recovery_operation_complete,
    )

    with pytest.raises(DurableOperationPersistenceError):
        runtime.kernel.learning_feedback_loop.run(
            _result(),
            optimize=True,
            recover=True,
        )

    replay_operation_store = runtime.stores.replay_operation_store
    assert replay_operation_store is not None
    assert replay_operation_store.count() == 1
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT state FROM sh3_replay_operations "
            "WHERE operation_name = 'recovery_execution'"
        ).fetchone()
    assert row == ("claimed",)
    cycle_claims = runtime.stores.replay_claim_store
    assert cycle_claims.get(f"learning-cycle:{_result().result_id}") is not None


def test_recovery_execution_without_operation_store_keeps_legacy_stage_replay(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-stage-legacy.sqlite3"
    _, claims, stages, _ = _stores(database)
    claim = _claim(claims)
    backend = _CountingRecoveryBackend()
    boundary = RecoveryExecutionBoundary(
        backend,
        replay_stage_store=stages,
    )

    result = _request(boundary, backend, claim)

    assert result.success is True
    assert backend.calls == 1
