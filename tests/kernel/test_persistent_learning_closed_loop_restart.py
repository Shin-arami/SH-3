from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any

import pytest

from cognition.contracts import (
    CognitiveLifecycleState,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.feedback import CognitiveFeedbackKind
from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_store import (
    ReplayClaimOwnershipError,
    ReplayClaimStatus,
    SQLiteReplayClaimStore,
)
from kernel.cognitive_learning_boundary import CognitiveLearningBoundary
from kernel.learning_feedback_loop import (
    ClosedLoopStatus,
    LearningClosedLoopCoordinator,
    LearningClosedLoopReport,
)
from kernel.persistent_factory import create_persistent_sh3_kernel


def _result() -> CognitiveResult:
    created_at = datetime(2026, 11, 1, 1, 0, tzinfo=UTC)
    correlation_id = "correlation:persistent-restart"
    trace_id = "trace:persistent-restart"
    tenant_id = "tenant:persistent-restart"
    goal = {
        "intent": "verify persistent closed-loop replay after kernel restart",
        "owner": "tests",
        "goal_type": "general",
        "version": "1.0.0",
        "created_at": created_at.isoformat(),
        "lifecycle_state": "completed",
        "success_criteria": [],
        "constraints": {},
        "priority": 0.0,
        "time_horizon": None,
        "goal_id": "goal:persistent-restart",
        "correlation_id": correlation_id,
        "causation_id": None,
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "metadata": {},
    }
    payload: dict[str, Any] = {
        "status": "success",
        "result_type": "cognitive",
        "owner": "tests",
        "version": "1.0.0",
        "created_at": created_at.isoformat(),
        "lifecycle_state": "completed",
        "correlation_id": correlation_id,
        "causation_id": None,
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "metadata": {},
        "result_id": "result:persistent-restart",
        "output": {"goal": goal, "value": "stable"},
    }
    result = LearningClosedLoopCoordinator._result_from_dict(payload)
    assert result is not None
    return result


def test_kernel_restart_restores_completed_report_without_reexecuting_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay.sqlite3"
    first_runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"

    def persist_terminal_report(
        coordinator: LearningClosedLoopCoordinator,
        cognitive_result: CognitiveResult,
        requested_cycle_id: str,
        *,
        context: EventPropagationContext | None,
        optimize: bool,
        recover: bool,
    ) -> LearningClosedLoopReport:
        assert context is None
        assert optimize is False
        assert recover is False
        report = LearningClosedLoopReport(
            cycle_id=requested_cycle_id,
            result_id=cognitive_result.result_id,
            goal_id=cognitive_result.goal_id,
            status=ClosedLoopStatus.COMPLETED,
            created_at=cognitive_result.created_at,
            correlation_id=cognitive_result.correlation_id,
            causation_id=cognitive_result.causation_id,
            trace_id=cognitive_result.trace_id,
            tenant_id=cognitive_result.tenant_id,
            optimize=optimize,
            recover=recover,
        )
        coordinator._cycles[requested_cycle_id] = report
        propagation = EventPropagationContext.create(
            correlation_id=report.correlation_id,
            causation_id=report.causation_id,
            trace_id=report.trace_id,
            tenant_id=report.tenant_id,
        )
        persisted = coordinator._closed_loop_evidence_boundary.record(
            report,
            context=propagation,
            created_at=report.created_at,
        )
        assert persisted.recorded, persisted.error
        return report

    monkeypatch.setattr(
        LearningClosedLoopCoordinator,
        "_run_cycle",
        persist_terminal_report,
    )
    first_report = first_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=False,
    )
    first_claim = first_runtime.stores.replay_claim_store.get(cycle_id)
    assert first_claim is not None
    assert first_claim.status is ReplayClaimStatus.COMPLETED
    assert first_claim.evidence_id is not None
    evidence_count = first_runtime.stores.evidence_store.count()

    def reject_reexecution(
        coordinator: LearningClosedLoopCoordinator,
        cognitive_result: CognitiveResult,
        requested_cycle_id: str,
        *,
        context: EventPropagationContext | None,
        optimize: bool,
        recover: bool,
    ) -> LearningClosedLoopReport:
        pytest.fail(
            "a completed persistent cycle was re-executed after kernel restart: "
            f"{requested_cycle_id}"
        )

    monkeypatch.setattr(
        LearningClosedLoopCoordinator,
        "_run_cycle",
        reject_reexecution,
    )
    second_runtime = create_persistent_sh3_kernel(database)
    restored_report = second_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=False,
    )

    assert restored_report == first_report
    assert second_runtime.kernel.learning_feedback_loop.get(cycle_id) == first_report
    assert second_runtime.stores.evidence_store.count() == evidence_count
    restored_claim = second_runtime.stores.replay_claim_store.get(cycle_id)
    assert restored_claim is not None
    assert restored_claim.status is ReplayClaimStatus.COMPLETED
    assert restored_claim.evidence_id == first_claim.evidence_id


def test_kernel_restart_replays_real_learning_pipeline_without_relearning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay-learning-e2e.sqlite3"
    first_runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"
    original_record = CognitiveLearningBoundary.record
    learning_calls = 0

    def count_learning_call(
        boundary: CognitiveLearningBoundary,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal learning_calls
        learning_calls += 1
        return original_record(boundary, *args, **kwargs)

    monkeypatch.setattr(
        CognitiveLearningBoundary,
        "record",
        count_learning_call,
    )

    first_report = first_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=False,
    )

    assert learning_calls == 1
    assert first_report.status is ClosedLoopStatus.COMPLETED
    assert first_report.learning_result
    assert any(
        item.kind is CognitiveFeedbackKind.LEARNING
        for item in first_report.feedback
    )
    assert any(
        item.kind is CognitiveFeedbackKind.CLOSED_LOOP
        for item in first_report.feedback
    )

    first_claim = first_runtime.stores.replay_claim_store.get(cycle_id)
    assert first_claim is not None
    assert first_claim.status is ReplayClaimStatus.COMPLETED
    assert first_claim.evidence_id is not None
    assert first_report.replay_claim_generation == first_claim.generation
    evidence_count = first_runtime.stores.evidence_store.count()

    second_runtime = create_persistent_sh3_kernel(database)
    restored_report = second_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=False,
    )

    assert learning_calls == 1
    assert restored_report == first_report
    assert restored_report.replay_claim_generation == first_claim.generation
    assert second_runtime.kernel.learning_feedback_loop.get(cycle_id) == first_report
    assert second_runtime.stores.evidence_store.count() == evidence_count
    restored_claim = second_runtime.stores.replay_claim_store.get(cycle_id)
    assert restored_claim is not None
    assert restored_claim.status is ReplayClaimStatus.COMPLETED


def test_kernel_restart_replays_optimizer_pipeline_without_reoptimizing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay-optimizer-e2e.sqlite3"
    first_runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"
    original_record = CognitiveLearningBoundary.record
    optimizer_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.optimizer_boundary
    )
    original_request = optimizer_boundary_type.request
    learning_calls = 0
    optimizer_calls = 0

    def count_learning_call(
        boundary: CognitiveLearningBoundary,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal learning_calls
        learning_calls += 1
        return original_record(boundary, *args, **kwargs)

    def count_optimizer_call(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal optimizer_calls
        optimizer_calls += 1
        return original_request(boundary, *args, **kwargs)

    monkeypatch.setattr(
        CognitiveLearningBoundary,
        "record",
        count_learning_call,
    )
    monkeypatch.setattr(
        optimizer_boundary_type,
        "request",
        count_optimizer_call,
    )

    first_report = first_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=True,
        recover=False,
    )

    assert learning_calls == 1
    assert optimizer_calls == 1
    assert first_report.status is ClosedLoopStatus.COMPLETED
    assert first_report.learning_result
    assert first_report.optimization_result is not None
    optimization_feedback = tuple(
        item
        for item in first_report.feedback
        if item.kind is CognitiveFeedbackKind.OPTIMIZATION
    )
    assert len(optimization_feedback) == 1
    assert optimization_feedback[0].success
    assert any(
        item.kind is CognitiveFeedbackKind.LEARNING
        for item in first_report.feedback
    )
    assert any(
        item.kind is CognitiveFeedbackKind.CLOSED_LOOP
        for item in first_report.feedback
    )

    first_claim = first_runtime.stores.replay_claim_store.get(cycle_id)
    assert first_claim is not None
    assert first_claim.status is ReplayClaimStatus.COMPLETED
    assert first_claim.evidence_id is not None
    evidence_count = first_runtime.stores.evidence_store.count()

    second_runtime = create_persistent_sh3_kernel(database)
    restored_report = second_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=True,
        recover=False,
    )

    assert learning_calls == 1
    assert optimizer_calls == 1
    assert restored_report == first_report
    assert second_runtime.kernel.learning_feedback_loop.get(cycle_id) == first_report
    assert second_runtime.stores.evidence_store.count() == evidence_count
    restored_claim = second_runtime.stores.replay_claim_store.get(cycle_id)
    assert restored_claim is not None
    assert restored_claim.status is ReplayClaimStatus.COMPLETED
    assert restored_claim.evidence_id == first_claim.evidence_id


def test_kernel_restart_replays_recovery_without_recovering_again(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay-recovery-e2e.sqlite3"
    first_runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    result = replace(
        _result(),
        status=CognitiveResultStatus.FAILURE,
        lifecycle_state=CognitiveLifecycleState.FAILED,
    )
    cycle_id = f"learning-cycle:{result.result_id}"
    original_record = CognitiveLearningBoundary.record
    strategy_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.recovery_strategy_boundary
    )
    execution_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.recovery_execution_boundary
    )
    original_strategy_request = strategy_boundary_type.request
    original_execution_request = execution_boundary_type.request
    learning_calls = 0
    strategy_calls = 0
    execution_calls = 0

    def count_learning_call(
        boundary: CognitiveLearningBoundary,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal learning_calls
        learning_calls += 1
        return original_record(boundary, *args, **kwargs)

    def count_strategy_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal strategy_calls
        strategy_calls += 1
        return original_strategy_request(boundary, *args, **kwargs)

    def count_execution_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal execution_calls
        execution_calls += 1
        return original_execution_request(boundary, *args, **kwargs)

    monkeypatch.setattr(
        CognitiveLearningBoundary,
        "record",
        count_learning_call,
    )
    monkeypatch.setattr(
        strategy_boundary_type,
        "request",
        count_strategy_request,
    )
    monkeypatch.setattr(
        execution_boundary_type,
        "request",
        count_execution_request,
    )

    first_report = first_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=True,
    )

    assert learning_calls == 1
    assert strategy_calls == 1
    assert execution_calls == 1
    assert first_report.status is ClosedLoopStatus.RECOVERED
    assert first_report.recover is True
    assert first_report.healing_result is not None
    assert first_report.healing_result["success"] is True
    assert first_report.healing_result["status"] == "recovered"
    self_healing_feedback = tuple(
        item
        for item in first_report.feedback
        if item.kind is CognitiveFeedbackKind.SELF_HEALING
    )
    assert len(self_healing_feedback) == 1
    assert self_healing_feedback[0].success is True

    first_claim = first_runtime.stores.replay_claim_store.get(cycle_id)
    assert first_claim is not None
    assert first_claim.status is ReplayClaimStatus.COMPLETED
    assert first_claim.evidence_id is not None
    evidence_count = first_runtime.stores.evidence_store.count()

    second_runtime = create_persistent_sh3_kernel(database)
    restored_report = second_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=True,
    )

    assert learning_calls == 1
    assert strategy_calls == 1
    assert execution_calls == 1
    assert restored_report == first_report
    assert second_runtime.kernel.learning_feedback_loop.get(cycle_id) == first_report
    assert second_runtime.stores.evidence_store.count() == evidence_count
    restored_claim = second_runtime.stores.replay_claim_store.get(cycle_id)
    assert restored_claim is not None
    assert restored_claim.status is ReplayClaimStatus.COMPLETED
    assert restored_claim.evidence_id == first_claim.evidence_id

def test_replay_claim_lease_is_renewed_while_closed_loop_is_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay-heartbeat.sqlite3"
    runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    coordinator = runtime.kernel.learning_feedback_loop
    coordinator._replay_claim_lease_seconds = 0.3
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"
    entered = Event()
    finish = Event()
    heartbeat_renewed = Event()
    renewal_count = 0
    initial_expiries: list[float] = []
    original_claim = SQLiteReplayClaimStore.claim
    original_renew = SQLiteReplayClaimStore.renew

    def track_claim(
        store: SQLiteReplayClaimStore,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        claim = original_claim(store, *args, **kwargs)
        if claim.lease_expires_at is not None:
            initial_expiries.append(claim.lease_expires_at)
        return claim

    def track_renewal(
        store: SQLiteReplayClaimStore,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal renewal_count
        renewed = original_renew(store, *args, **kwargs)
        renewal_count += 1
        if renewal_count >= 2:
            heartbeat_renewed.set()
        return renewed

    def block_cycle(
        current: LearningClosedLoopCoordinator,
        cognitive_result: CognitiveResult,
        requested_cycle_id: str,
        *,
        context: EventPropagationContext | None,
        optimize: bool,
        recover: bool,
    ) -> Any:
        assert requested_cycle_id == cycle_id
        entered.set()
        if not finish.wait(timeout=5.0):
            raise TimeoutError("test did not release the blocked closed loop")
        return SimpleNamespace(status=ClosedLoopStatus.COMPLETED)

    monkeypatch.setattr(SQLiteReplayClaimStore, "claim", track_claim)
    monkeypatch.setattr(SQLiteReplayClaimStore, "renew", track_renewal)
    monkeypatch.setattr(LearningClosedLoopCoordinator, "_run_cycle", block_cycle)

    failures: list[BaseException] = []

    def run_cycle() -> None:
        try:
            coordinator.run(result, optimize=False, recover=False)
        except BaseException as exc:
            failures.append(exc)

    worker = Thread(target=run_cycle, daemon=True)
    worker.start()
    try:
        assert entered.wait(timeout=3.0)
        assert len(initial_expiries) == 1
        initial_expiry = initial_expiries[0]

        assert heartbeat_renewed.wait(timeout=3.0)
        renewed_claim = runtime.stores.replay_claim_store.get(cycle_id)
        assert renewed_claim is not None
        assert renewed_claim.lease_expires_at is not None
        assert renewed_claim.lease_expires_at > initial_expiry
    finally:
        finish.set()
        worker.join(timeout=5.0)

    assert not worker.is_alive()
    assert failures == []
    completed_renewal_count = renewal_count
    Event().wait(timeout=0.15)
    assert renewal_count == completed_renewal_count


def test_lost_replay_claim_stops_closed_loop_before_optimizer_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay-heartbeat-takeover.sqlite3"
    runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    coordinator = runtime.kernel.learning_feedback_loop
    coordinator._replay_claim_lease_seconds = 0.3
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"
    learning_entered = Event()
    finish_learning = Event()
    takeover_enabled = Event()
    heartbeat_rejected = Event()
    optimizer_calls = 0
    original_learning_record = CognitiveLearningBoundary.record
    original_renew = SQLiteReplayClaimStore.renew
    optimizer_boundary_type = type(coordinator.optimizer_boundary)
    original_optimizer_request = optimizer_boundary_type.request

    def block_learning(
        boundary: CognitiveLearningBoundary,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        learning_entered.set()
        if not finish_learning.wait(timeout=5.0):
            raise TimeoutError("test did not release learning stage")
        return original_learning_record(boundary, *args, **kwargs)

    def reject_renewal_after_takeover(
        store: SQLiteReplayClaimStore,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if takeover_enabled.is_set():
            heartbeat_rejected.set()
            raise ReplayClaimOwnershipError("simulated stale generation")
        return original_renew(store, *args, **kwargs)

    def count_optimizer_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal optimizer_calls
        optimizer_calls += 1
        return original_optimizer_request(boundary, *args, **kwargs)

    monkeypatch.setattr(CognitiveLearningBoundary, "record", block_learning)
    monkeypatch.setattr(SQLiteReplayClaimStore, "renew", reject_renewal_after_takeover)
    monkeypatch.setattr(optimizer_boundary_type, "request", count_optimizer_request)

    failures: list[BaseException] = []

    def run_cycle() -> None:
        try:
            coordinator.run(result, optimize=True, recover=False)
        except BaseException as exc:
            failures.append(exc)

    worker = Thread(target=run_cycle, daemon=True)
    worker.start()
    takeover = None
    try:
        assert learning_entered.wait(timeout=3.0)
        original_claim = runtime.stores.replay_claim_store.get(cycle_id)
        assert original_claim is not None
        assert original_claim.lease_expires_at is not None

        takeover_enabled.set()
        assert heartbeat_rejected.wait(timeout=3.0)
        takeover_time = datetime.fromtimestamp(
            original_claim.lease_expires_at + 1.0,
            tz=UTC,
        )
        takeover = runtime.stores.replay_claim_store.claim(
            cycle_id,
            original_claim.fingerprint,
            lease_seconds=30.0,
            now=takeover_time,
        )
        assert takeover.status is ReplayClaimStatus.CLAIMED
        assert takeover.generation == original_claim.generation + 1
    finally:
        finish_learning.set()
        worker.join(timeout=5.0)

    assert not worker.is_alive()
    assert len(failures) == 1
    assert isinstance(failures[0], ReplayClaimOwnershipError)
    assert optimizer_calls == 0
    assert coordinator.get(cycle_id) is None
    current_claim = runtime.stores.replay_claim_store.get(cycle_id)
    assert current_claim is not None
    assert takeover is not None
    assert current_claim.generation == takeover.generation
    assert current_claim.owner_token == takeover.owner_token
    assert current_claim.status is ReplayClaimStatus.CLAIMED
