from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_operation_store import (
    ReplayOperationKey,
    ReplayOperationKind,
    ReplayOperationStatus,
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_replay_ops import (
    PersistentReplayReadinessError,
    backup_database,
    check_database,
    restore_database,
)
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel.core import SH3Kernel
from kernel.learning_optimizer_boundary import LearningOptimizerBoundary
from kernel.optimizer_update_boundary import OptimizationUpdateBoundary
from kernel.replay_execution_context import (
    DurableOperationPersistenceError,
    ReplayExecutionContext,
)
from kernel.system_optimizer import (
    OptimizationAction,
    OptimizationActionReplayPolicy,
    _action_idempotency_key,
    _rollback_idempotency_key,
)

NOW = datetime.now(UTC)
CYCLE_ID = "learning-cycle:p3-2b-action-ledger"
CYCLE_FINGERPRINT = "sha256:" + "2b" * 32
TENANT_ID = "tenant:p3-2b-action-ledger"


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


def _claim(
    claims: SQLiteReplayClaimStore,
) -> Any:
    result = claims.claim(
        CYCLE_ID,
        CYCLE_FINGERPRINT,
        lease_seconds=3600.0,
        now=NOW,
    )
    assert result.status is ReplayClaimStatus.CLAIMED
    assert result.owner_token is not None
    return result


def _context(causation_id: str) -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="p3-2b-correlation",
        causation_id=causation_id,
        trace_id="p3-2b-trace",
        tenant_id=TENANT_ID,
    )


def _learning_result() -> dict[str, Any]:
    return {
        "record_id": "learning-record:p3-2b-action-ledger",
        "domain": "cognition.result",
        "success": True,
        "score": 0.75,
        "details": {"strategy": "durable-action-replay", "source": "p3-2b-test"},
        "metadata": {"tenant_scope": TENANT_ID},
    }


def _new_boundary(
    kernel: SH3Kernel,
    stages: SQLiteReplayStageStore,
) -> LearningOptimizerBoundary:
    update_boundary = OptimizationUpdateBoundary(kernel.system_optimizer)
    return LearningOptimizerBoundary(
        kernel.system_optimizer,
        update_boundary=update_boundary,
        replay_stage_store=stages,
    )


def _request(
    boundary: LearningOptimizerBoundary,
    claim: Any,
    *,
    causation_id: str,
) -> Any:
    return boundary.request(
        _learning_result(),
        context=_context(causation_id),
        created_at=NOW,
        replay_cycle_id=CYCLE_ID,
        replay_cycle_fingerprint=CYCLE_FINGERPRINT,
        replay_claim_owner_token=claim.owner_token,
        replay_claim_generation=claim.generation,
    )


def _kernel(
    evidence: SQLiteEvidenceStore,
    claims: SQLiteReplayClaimStore,
    stages: SQLiteReplayStageStore,
    operations: SQLiteReplayOperationStore,
) -> SH3Kernel:
    return SH3Kernel(
        evidence_store=evidence,
        replay_claim_store=claims,
        replay_stage_store=stages,
        replay_operation_store=operations,
    )


def test_completed_runtime_action_is_reused_after_stage_finalize_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "action-local-retry.sqlite3"
    evidence, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    kernel = _kernel(evidence, claims, stages, operations)
    for index in range(7):
        kernel.context_manager.push(f"context-{index}")

    original_action = kernel.system_optimizer.get_action("reduce_context_depth")
    assert original_action is not None
    action_calls = 0

    def counted_apply(context: Any) -> Any:
        nonlocal action_calls
        action_calls += 1
        return original_action.apply(context)

    kernel.system_optimizer.register_action(
        OptimizationAction(
            original_action.name,
            counted_apply,
            original_action.rollback,
            original_action.description,
            original_action.replay_policy,
        ),
        replace=True,
    )

    original_complete = SQLiteReplayStageStore.complete
    fail_once = True

    def fail_first_stage_finalize(
        store: SQLiteReplayStageStore,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise RuntimeError("injected parent Stage finalization failure")
        return original_complete(
            store,
            key,
            owner_token,
            generation,
            result,
            now=now,
        )

    monkeypatch.setattr(SQLiteReplayStageStore, "complete", fail_first_stage_finalize)
    with pytest.raises(RuntimeError, match="injected parent Stage finalization failure"):
        _request(_new_boundary(kernel, stages), first_claim, causation_id="first-attempt")

    assert action_calls == 1
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1

    # The operation result and immutable plan survive an online backup/restore.
    backup_path = tmp_path / "action-local-retry.backup.sqlite3"
    restored_path = tmp_path / "action-local-retry.restored.sqlite3"
    backup_database(database, backup_path)
    restore_database(backup_path, restored_path)
    restored_readiness = check_database(restored_path)
    assert restored_readiness.replay_operation_execution_count == 1
    assert restored_readiness.replay_operation_plan_count == 1

    # Same Runtime, new claim generation: local state and the cached Python result
    # remain available, so the callback must not run again.
    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)
    second_claim = _claim(claims)
    assert second_claim.generation == first_claim.generation + 1
    retried = _request(
        _new_boundary(kernel, stages),
        second_claim,
        causation_id="same-runtime-retry",
    )

    assert retried.success is True
    assert action_calls == 1
    assert kernel.context_manager.snapshot()["depth"] == 6
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1
    stage_key_count = check_database(database)
    assert stage_key_count.replay_operation_execution_count == 1
    assert stage_key_count.replay_operation_plan_count == 1


def test_operation_commit_failure_propagates_and_same_runtime_retry_finalizes_cached_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "action-ledger-completion-write-failure.sqlite3"
    evidence, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    kernel = _kernel(evidence, claims, stages, operations)
    for index in range(7):
        kernel.context_manager.push(f"context-{index}")

    original_action = kernel.system_optimizer.get_action("reduce_context_depth")
    assert original_action is not None
    action_calls = 0

    def counted_apply(context: Any) -> Any:
        nonlocal action_calls
        action_calls += 1
        return original_action.apply(context)

    kernel.system_optimizer.register_action(
        OptimizationAction(
            original_action.name,
            counted_apply,
            original_action.rollback,
            original_action.description,
            original_action.replay_policy,
        ),
        replace=True,
    )

    original_operation_complete = SQLiteReplayOperationStore.complete
    fail_once = True

    def fail_first_operation_complete(
        store: SQLiteReplayOperationStore,
        key: ReplayOperationKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise RuntimeError("injected Operation Ledger completion failure")
        return original_operation_complete(
            store,
            key,
            owner_token,
            generation,
            result,
            now=now,
        )

    monkeypatch.setattr(
        SQLiteReplayOperationStore,
        "complete",
        fail_first_operation_complete,
    )
    with pytest.raises(DurableOperationPersistenceError, match="persist optimizer Action"):
        _request(_new_boundary(kernel, stages), first_claim, causation_id="ledger-write-failure")

    assert action_calls == 1
    assert operations.count(cycle_id=CYCLE_ID) == 1

    # The Action callback returned in this Runtime, but its completed ledger write
    # failed. A newer claim generation can finalize the same cached Python result.
    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)
    second_claim = _claim(claims)
    retried = _request(
        _new_boundary(kernel, stages),
        second_claim,
        causation_id="ledger-write-retry",
    )

    assert retried.success is True
    assert action_calls == 1
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1
    report = check_database(database)
    assert report.replay_operation_execution_count == 1
    assert report.replay_operation_plan_count == 1


def test_stateful_completed_action_fails_closed_after_runtime_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "action-restart-local-state.sqlite3"
    evidence, claims, stages, operations = _stores(database)
    first_claim = _claim(claims)
    first_kernel = _kernel(evidence, claims, stages, operations)
    for index in range(7):
        first_kernel.context_manager.push(f"context-{index}")

    original_action = first_kernel.system_optimizer.get_action("reduce_context_depth")
    assert original_action is not None
    first_action_calls = 0

    def counted_apply(context: Any) -> Any:
        nonlocal first_action_calls
        first_action_calls += 1
        return original_action.apply(context)

    first_kernel.system_optimizer.register_action(
        OptimizationAction(
            original_action.name,
            counted_apply,
            original_action.rollback,
            original_action.description,
            original_action.replay_policy,
        ),
        replace=True,
    )

    original_complete = SQLiteReplayStageStore.complete
    fail_once = True

    def fail_first_stage_finalize(
        store: SQLiteReplayStageStore,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise RuntimeError("injected Stage completion interruption")
        return original_complete(store, key, owner_token, generation, result, now=now)

    monkeypatch.setattr(SQLiteReplayStageStore, "complete", fail_first_stage_finalize)
    with pytest.raises(RuntimeError, match="injected Stage completion interruption"):
        _request(_new_boundary(first_kernel, stages), first_claim, causation_id="before-restart")
    assert first_action_calls == 1

    # Create a new Kernel over the same DB-backed stores. Its ContextManager is
    # intentionally empty; the original in-memory pop is not fabricated again.
    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)
    second_claim = _claim(claims)
    second_kernel = _kernel(evidence, claims, stages, operations)
    restored_action = second_kernel.system_optimizer.get_action("reduce_context_depth")
    assert restored_action is not None
    restarted_callback_calls = 0

    def should_not_run(context: Any) -> Any:
        nonlocal restarted_callback_calls
        restarted_callback_calls += 1
        return restored_action.apply(context)

    second_kernel.system_optimizer.register_action(
        OptimizationAction(
            restored_action.name,
            should_not_run,
            restored_action.rollback,
            restored_action.description,
            restored_action.replay_policy,
        ),
        replace=True,
    )

    replayed = _request(
        _new_boundary(second_kernel, stages),
        second_claim,
        causation_id="after-restart",
    )

    assert replayed.success is False
    update = replayed.optimization.get("update")
    assert isinstance(update, dict)
    assert update["state_uncertain"] is True
    assert second_kernel.context_manager.snapshot()["depth"] == 0
    assert first_action_calls == 1
    assert restarted_callback_calls == 0
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1


def _manual_replay_scope(
    tmp_path: Path,
    database_name: str,
) -> tuple[
    SH3Kernel,
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
    SQLiteReplayOperationStore,
    Any,
    ReplayStageKey,
    ReplayExecutionContext,
]:
    database = tmp_path / database_name
    evidence, claims, stages, operations = _stores(database)
    claim = _claim(claims)
    stage_key = ReplayStageKey.create(
        CYCLE_ID,
        CYCLE_FINGERPRINT,
        "optimizer.manual-actions.v1",
        {"scenario": database_name},
    )
    stage = stages.begin(stage_key, claim.owner_token, claim.generation, now=NOW)
    assert stage.status is ReplayStageStatus.CLAIMED
    kernel = _kernel(evidence, claims, stages, operations)
    scope = ReplayExecutionContext(
        cycle_id=CYCLE_ID,
        cycle_fingerprint=CYCLE_FINGERPRINT,
        parent_stage_key=stage_key.idempotency_key,
        owner_token=claim.owner_token,
        generation=claim.generation,
        tenant_id=TENANT_ID,
    )
    return kernel, evidence, claims, stages, operations, claim, stage_key, scope


def test_action_and_failed_rollback_results_are_durable_and_not_repeated(
    tmp_path: Path,
) -> None:
    kernel, _, _, _, operations, _, stage_key, scope = _manual_replay_scope(
        tmp_path, "action-rollback-results.sqlite3"
    )
    calls = {"first": 0, "second": 0, "rollback": 0}

    def apply_first(context: Any) -> dict[str, Any]:
        calls["first"] += 1
        return {"changed": True, "token": "first-action"}

    def fail_rollback(result: Any, *, idempotency_key: str) -> None:
        calls["rollback"] += 1
        raise RuntimeError("compensation outcome is uncertain")

    def fail_second(context: Any) -> Any:
        calls["second"] += 1
        raise RuntimeError("second Action failed")

    kernel.system_optimizer.register_action(
        OptimizationAction("first", apply_first, fail_rollback),
    )
    kernel.system_optimizer.register_action(
        OptimizationAction("second", fail_second, lambda result: None),
    )

    action_context = {"idempotency_key": stage_key.idempotency_key}
    with kernel.system_optimizer.replay_execution_scope(scope):
        first = kernel.system_optimizer.execute_actions(("first", "second"), action_context)
        again = kernel.system_optimizer.execute_actions(("first", "second"), action_context)

    assert first[0].success is False
    assert first[0].rolled_back is False
    assert first[0].state_uncertain is True
    assert first[1].success is False
    assert first[1].state_uncertain is True
    assert again == first
    assert calls == {"first": 1, "second": 1, "rollback": 1}
    assert operations.count(cycle_id=CYCLE_ID) == 3
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1

    action_key = _action_idempotency_key(stage_key.idempotency_key, "first", 0)
    rollback_key = _rollback_idempotency_key(action_key, "first")
    rollback_operation_key = ReplayOperationKey.create(
        idempotency_key=rollback_key,
        tenant_id=TENANT_ID,
        cycle_id=CYCLE_ID,
        cycle_fingerprint=CYCLE_FINGERPRINT,
        parent_stage_key=stage_key.idempotency_key,
        operation_kind=ReplayOperationKind.ROLLBACK,
        operation_name="first",
        ordinal=0,
        parent_operation_key=action_key,
        input_payload={
            "action": "first",
            "ordinal": 0,
            "action_result": {"changed": True, "token": "first-action"},
        },
    )
    stored_rollback = operations.get(rollback_operation_key)
    assert stored_rollback is not None
    assert stored_rollback.status is ReplayOperationStatus.COMPLETED
    assert stored_rollback.result is not None
    assert stored_rollback.result["success"] is False
    assert stored_rollback.result["state_uncertain"] is True


def test_result_only_action_can_reuse_completed_result_after_runtime_restart(
    tmp_path: Path,
) -> None:
    kernel, evidence, claims, stages, operations, first_claim, stage_key, first_scope = (
        _manual_replay_scope(tmp_path, "action-result-reuse.sqlite3")
    )
    callback_calls = 0

    def report_only(context: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        return {"changed": False, "report": "stable-derived-view"}

    kernel.system_optimizer.register_action(
        OptimizationAction(
            "safe_report",
            report_only,
            lambda result, *, idempotency_key: None,
            replay_policy=OptimizationActionReplayPolicy.REUSE_RESULT,
        )
    )
    parent_context = {"idempotency_key": stage_key.idempotency_key}
    with kernel.system_optimizer.replay_execution_scope(first_scope):
        first = kernel.system_optimizer.execute_actions(("safe_report",), parent_context)
    assert first[0].success is True
    assert callback_calls == 1

    assert claims.release(CYCLE_ID, first_claim.owner_token, first_claim.generation)
    next_claim = _claim(claims)
    next_stage = stages.begin(
        stage_key,
        next_claim.owner_token,
        next_claim.generation,
        now=NOW,
    )
    assert next_stage.status is ReplayStageStatus.CLAIMED
    restarted_kernel = _kernel(
        # The evidence store is shared by the original kernel's persistent
        # stores; retrieve it through the same database path.
        evidence,
        claims,
        stages,
        operations,
    )
    restarted_kernel.system_optimizer.register_action(
        OptimizationAction(
            "safe_report",
            report_only,
            lambda result, *, idempotency_key: None,
            replay_policy=OptimizationActionReplayPolicy.REUSE_RESULT,
        )
    )
    next_scope = ReplayExecutionContext(
        cycle_id=CYCLE_ID,
        cycle_fingerprint=CYCLE_FINGERPRINT,
        parent_stage_key=stage_key.idempotency_key,
        owner_token=next_claim.owner_token,
        generation=next_claim.generation,
        tenant_id=TENANT_ID,
    )
    with restarted_kernel.system_optimizer.replay_execution_scope(next_scope):
        restored = restarted_kernel.system_optimizer.execute_actions(
            ("safe_report",), parent_context
        )

    assert restored[0].success is True
    assert restored[0].result == first[0].result
    assert callback_calls == 1
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1



def test_persisted_action_plan_rejects_unregistered_action_after_restart(
    tmp_path: Path,
) -> None:
    (
        kernel,
        evidence,
        claims,
        stages,
        operations,
        claim,
        stage_key,
        scope,
    ) = _manual_replay_scope(tmp_path, "action-plan-missing-registration.sqlite3")
    assert claim.owner_token is not None
    kernel.system_optimizer.register_action(
        OptimizationAction(
            "custom_action",
            lambda context: {"changed": False},
            lambda result, *, idempotency_key: None,
            replay_policy=OptimizationActionReplayPolicy.REUSE_RESULT,
        )
    )
    parent_context = {"idempotency_key": stage_key.idempotency_key}
    with kernel.system_optimizer.replay_execution_scope(scope):
        first = kernel.system_optimizer.execute_actions(
            ("custom_action",), parent_context
        )
    assert first[0].success is True

    assert claims.release(CYCLE_ID, claim.owner_token, claim.generation)
    restarted_kernel = _kernel(evidence, claims, stages, operations)
    next_claim = claims.claim(
        CYCLE_ID, CYCLE_FINGERPRINT, lease_seconds=3600.0, now=NOW
    )
    assert next_claim.owner_token is not None
    stages.begin(stage_key, next_claim.owner_token, next_claim.generation, now=NOW)
    next_scope = ReplayExecutionContext(
        cycle_id=CYCLE_ID,
        cycle_fingerprint=CYCLE_FINGERPRINT,
        parent_stage_key=stage_key.idempotency_key,
        owner_token=next_claim.owner_token,
        generation=next_claim.generation,
        tenant_id=TENANT_ID,
    )
    with restarted_kernel.system_optimizer.replay_execution_scope(next_scope), pytest.raises(
        DurableOperationPersistenceError,
        match="contains unregistered Actions",
    ):
        restarted_kernel.system_optimizer.execute_actions(
            ("custom_action",), parent_context
        )
    assert operations.count(cycle_id=CYCLE_ID) == 1
    assert operations.count_plans(cycle_id=CYCLE_ID) == 1

def test_action_plan_readiness_rejects_tampered_manifest(tmp_path: Path) -> None:
    database_name = "action-plan-integrity.sqlite3"
    database = tmp_path / database_name
    kernel, _, _, _, operations, _, stage_key, scope = _manual_replay_scope(
        tmp_path, database_name
    )
    kernel.system_optimizer.register_action(
        OptimizationAction(
            "safe_report",
            lambda context: {"changed": False},
            lambda result, *, idempotency_key: None,
            replay_policy=OptimizationActionReplayPolicy.REUSE_RESULT,
        )
    )
    with kernel.system_optimizer.replay_execution_scope(scope):
        kernel.system_optimizer.execute_actions(
            ("safe_report",),
            {"idempotency_key": stage_key.idempotency_key},
        )

    assert operations.count_plans(cycle_id=CYCLE_ID) == 1
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sh3_replay_operation_plans SET actions_json = ? "
            "WHERE tenant_scope = ? AND parent_stage_key = ?",
            (
                '{"actions":[],"version":1}',
                TENANT_ID,
                stage_key.idempotency_key,
            ),
        )

    with pytest.raises(
        PersistentReplayReadinessError,
        match="operation plan identity, integrity, or ownership verification failed",
    ):
        check_database(database)
