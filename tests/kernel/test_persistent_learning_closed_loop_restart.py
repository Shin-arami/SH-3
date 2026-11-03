from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from cognition.contracts import (
    CognitiveLifecycleState,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.feedback import CognitiveFeedbackKind
from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_store import ReplayClaimStatus
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
    evidence_count = first_runtime.stores.evidence_store.count()

    second_runtime = create_persistent_sh3_kernel(database)
    restored_report = second_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=False,
        recover=False,
    )

    assert learning_calls == 1
    assert restored_report == first_report
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
