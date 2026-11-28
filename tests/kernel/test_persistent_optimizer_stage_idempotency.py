from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel.learning_optimizer_boundary import LearningOptimizerBoundary
from kernel.persistent_factory import create_persistent_sh3_kernel
from kernel.system_optimizer import SystemOptimizer

NOW = datetime(2026, 11, 1, 1, 0, tzinfo=UTC)
CYCLE_ID = "learning-cycle:optimizer-stage"
FINGERPRINT = "optimizer-stage-parent-fingerprint"


def _learning_result() -> dict[str, Any]:
    return {
        "record_id": "learning-record:optimizer-stage",
        "domain": "cognition.result",
        "success": True,
        "score": 0.75,
        "details": {"strategy": "stable", "source": "p1-3-test"},
        "metadata": {"tenant_scope": "optimizer-stage-test"},
    }


def _context(causation_id: str) -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="optimizer-stage-correlation",
        causation_id=causation_id,
        trace_id="optimizer-stage-trace",
        tenant_id="optimizer-stage-tenant",
    )


class IdempotentRecordingOptimizer:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def optimize(
        self,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        assert idempotency_key is not None
        self.keys.append(idempotency_key)
        return {
            "optimizer_id": "optimizer:recording",
            "execution": (),
            "execute": execute,
            "rebalance": {"actions": []},
        }


def _new_claim(
    claims: SQLiteReplayClaimStore,
) -> Any:
    claim = claims.claim(CYCLE_ID, FINGERPRINT, lease_seconds=120.0)
    assert claim.status is ReplayClaimStatus.CLAIMED
    assert claim.owner_token is not None
    return claim


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
        replay_cycle_fingerprint=FINGERPRINT,
        replay_claim_owner_token=claim.owner_token,
        replay_claim_generation=claim.generation,
    )


def _stage_key() -> ReplayStageKey:
    learning = _learning_result()
    details = learning["details"]
    return ReplayStageKey.create(
        CYCLE_ID,
        FINGERPRINT,
        "learning_optimizer.request.v1",
        {
            "contract": "learning-optimizer-v1",
            "learning_input": {
                "learning_record_id": learning["record_id"],
                "domain": learning["domain"],
                "success": learning["success"],
                "score": learning["score"],
                "strategy": details["strategy"],
                "metadata": learning["metadata"],
            },
        },
    )


def test_completed_optimizer_stage_is_restored_without_reoptimizing(
    tmp_path: Path,
) -> None:
    database = tmp_path / "optimizer-stage.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    claim = _new_claim(claims)
    optimizer = IdempotentRecordingOptimizer()

    first = _request(
        LearningOptimizerBoundary(optimizer, replay_stage_store=stages),
        claim,
        causation_id="optimizer-stage-cause:first",
    )
    stored = stages.get(_stage_key())
    assert stored is not None
    assert stored.status is ReplayStageStatus.COMPLETED
    assert len(optimizer.keys) == 1

    # Simulate a fresh boundary and changed event causation after Runtime restart.
    restored = _request(
        LearningOptimizerBoundary(optimizer, replay_stage_store=stages),
        claim,
        causation_id="optimizer-stage-cause:restarted",
    )

    assert len(optimizer.keys) == 1
    assert optimizer.keys[0] == _stage_key().idempotency_key
    assert restored.request_id != first.request_id
    assert restored.optimization == first.optimization
    assert restored.optimizer_id == first.optimizer_id
    assert restored.causation_id == "optimizer-stage-cause:restarted"


def test_optimizer_stage_retry_after_completion_write_crash_reuses_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "optimizer-stage-crash-window.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    first_claim = _new_claim(claims)
    optimizer = IdempotentRecordingOptimizer()
    original_complete = SQLiteReplayStageStore.complete
    failed_once = False

    def fail_first_completion(
        store: SQLiteReplayStageStore,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Any,
        *,
        now: datetime | None = None,
    ) -> Any:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise RuntimeError("injected optimizer stage completion crash")
        return original_complete(
            store,
            key,
            owner_token,
            generation,
            result,
            now=now,
        )

    monkeypatch.setattr(SQLiteReplayStageStore, "complete", fail_first_completion)
    first_boundary = LearningOptimizerBoundary(
        optimizer,
        replay_stage_store=stages,
    )
    with pytest.raises(RuntimeError, match="injected optimizer stage completion crash"):
        _request(
            first_boundary,
            first_claim,
            causation_id="optimizer-stage-crash:first",
        )

    key = _stage_key()
    interrupted = stages.get(key)
    assert interrupted is not None
    assert interrupted.status is ReplayStageStatus.CLAIMED
    assert interrupted.generation == first_claim.generation
    assert len(optimizer.keys) == 1

    assert claims.release(
        CYCLE_ID,
        first_claim.owner_token,
        first_claim.generation,
    )
    second_claim = _new_claim(claims)
    assert second_claim.generation > first_claim.generation

    # A new boundary has no process-local result cache. The Backend receives
    # the identical key so it can deduplicate an external side effect.
    second_boundary = LearningOptimizerBoundary(
        optimizer,
        replay_stage_store=stages,
    )
    retried = _request(
        second_boundary,
        second_claim,
        causation_id="optimizer-stage-crash:retry",
    )

    completed = stages.get(key)
    assert completed is not None
    assert completed.status is ReplayStageStatus.COMPLETED
    assert completed.generation == second_claim.generation
    assert len(optimizer.keys) == 2
    assert optimizer.keys[0] == optimizer.keys[1] == key.idempotency_key
    assert retried.success is True


def test_optimizer_update_actions_receive_the_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = create_persistent_sh3_kernel(
        tmp_path / "optimizer-update-key.sqlite3",
        create_if_missing=True,
    )
    claim = _new_claim(runtime.stores.replay_claim_store)
    for index in range(7):
        runtime.kernel.context_manager.push(f"optimizer-context-{index}")

    optimizer_type = type(runtime.kernel.system_optimizer)
    original_execute_actions = optimizer_type.execute_actions
    action_contexts: list[dict[str, Any]] = []

    def capture_action_context(
        optimizer: SystemOptimizer,
        actions: list[str] | tuple[str, ...],
        context: Any = None,
        *,
        rollback_on_failure: bool = True,
    ) -> Any:
        action_contexts.append(dict(context or {}))
        return original_execute_actions(
            optimizer,
            actions,
            context,
            rollback_on_failure=rollback_on_failure,
        )

    monkeypatch.setattr(optimizer_type, "execute_actions", capture_action_context)
    result = _request(
        runtime.kernel.learning_optimizer_boundary,
        claim,
        causation_id="optimizer-update-key:cause",
    )

    assert result.success is True
    assert action_contexts
    assert action_contexts[0]["idempotency_key"] == _stage_key().idempotency_key
    assert runtime.kernel.context_manager.snapshot()["depth"] == 6


def test_persistent_optimizer_requires_claim_metadata_and_idempotent_backend(
    tmp_path: Path,
) -> None:
    database = tmp_path / "optimizer-stage-validation.sqlite3"
    SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)

    class LegacyOptimizer:
        def optimize(
            self,
            *,
            context: EventPropagationContext | None = None,
            execute: bool = False,
        ) -> dict[str, Any]:
            return {"optimizer_id": "legacy", "execution": ()}

    with pytest.raises(TypeError, match="must accept idempotency_key"):
        LearningOptimizerBoundary(LegacyOptimizer(), replay_stage_store=stages)

    optimizer = IdempotentRecordingOptimizer()
    boundary = LearningOptimizerBoundary(optimizer, replay_stage_store=stages)
    with pytest.raises(ValueError, match="complete replay claim metadata"):
        boundary.request(
            _learning_result(),
            context=_context("optimizer-stage-cause:missing"),
            created_at=NOW,
        )
