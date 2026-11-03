from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cognition.feedback import CognitiveFeedbackKind
from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_store import ReplayClaimStatus
from kernel.cognitive_learning_boundary import CognitiveLearningBoundary
from kernel.learning_feedback_loop import ClosedLoopStatus
from kernel.persistent_factory import create_persistent_sh3_kernel
from tests.kernel.test_persistent_learning_closed_loop_restart import _result


def test_kernel_restart_replays_optimizer_healing_without_healing_again(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = tmp_path / "persistent-replay-optimizer-healing.sqlite3"
    first_runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"
    calls = {
        "learning": 0,
        "optimizer_request": 0,
        "optimizer_backend": 0,
        "optimizer_healing": 0,
        "recovery_strategy": 0,
        "recovery_execution": 0,
    }

    learning_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.learning_boundary
    )
    optimizer_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.optimizer_boundary
    )
    optimizer_backend_type = type(first_runtime.kernel.system_optimizer)
    healing_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.healing_boundary
    )
    strategy_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.recovery_strategy_boundary
    )
    execution_boundary_type = type(
        first_runtime.kernel.learning_feedback_loop.recovery_execution_boundary
    )

    original_learning_record = learning_boundary_type.record
    original_optimizer_request = optimizer_boundary_type.request
    original_healing_request = healing_boundary_type.request
    original_strategy_request = strategy_boundary_type.request
    original_execution_request = execution_boundary_type.request

    def count_learning_call(
        boundary: CognitiveLearningBoundary,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        calls["learning"] += 1
        return original_learning_record(boundary, *args, **kwargs)

    def fail_optimizer_backend(
        backend: Any,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        calls["optimizer_backend"] += 1
        _ = (backend, context, execute)
        raise RuntimeError("injected optimizer failure for persistent replay")

    def count_optimizer_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        calls["optimizer_request"] += 1
        return original_optimizer_request(boundary, *args, **kwargs)

    def count_healing_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        calls["optimizer_healing"] += 1
        return original_healing_request(boundary, *args, **kwargs)

    def count_strategy_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        calls["recovery_strategy"] += 1
        return original_strategy_request(boundary, *args, **kwargs)

    def count_execution_request(
        boundary: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        calls["recovery_execution"] += 1
        return original_execution_request(boundary, *args, **kwargs)

    monkeypatch.setattr(
        learning_boundary_type,
        "record",
        count_learning_call,
    )
    monkeypatch.setattr(
        optimizer_backend_type,
        "optimize",
        fail_optimizer_backend,
    )
    monkeypatch.setattr(
        optimizer_boundary_type,
        "request",
        count_optimizer_request,
    )
    monkeypatch.setattr(
        healing_boundary_type,
        "request",
        count_healing_request,
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
        optimize=True,
        recover=True,
    )

    assert calls == {
        "learning": 1,
        "optimizer_request": 1,
        "optimizer_backend": 1,
        "optimizer_healing": 1,
        "recovery_strategy": 1,
        "recovery_execution": 1,
    }
    assert first_report.status is ClosedLoopStatus.RECOVERED
    assert first_report.optimize is True
    assert first_report.recover is True
    assert first_report.optimization_result == {}
    assert isinstance(first_report.healing_result, dict)
    assert first_report.healing_result["success"] is True
    assert first_report.healing_result["status"] == "recovered"
    assert first_report.healing_result["result"]

    optimization_feedback = tuple(
        item
        for item in first_report.feedback
        if item.kind is CognitiveFeedbackKind.OPTIMIZATION
    )
    assert len(optimization_feedback) == 1
    assert optimization_feedback[0].success is False

    healing_feedback = tuple(
        item
        for item in first_report.feedback
        if item.kind is CognitiveFeedbackKind.SELF_HEALING
    )
    assert len(healing_feedback) == 1
    assert healing_feedback[0].success is True

    strategy_records = first_runtime.kernel.recovery_strategy_boundary.records()
    execution_records = first_runtime.kernel.recovery_execution_boundary.records()
    healing_records = first_runtime.kernel.optimizer_healing_boundary.records()
    assert len(strategy_records) == 1
    assert len(execution_records) == 1
    assert execution_records[0].success is True
    assert len(healing_records) == 1
    assert healing_records[0].success is True
    assert first_runtime.kernel.meta_controller.healer.detected == 1
    assert first_runtime.kernel.meta_controller.healer.recovered == 1

    first_claim = first_runtime.stores.replay_claim_store.get(cycle_id)
    assert first_claim is not None
    assert first_claim.status is ReplayClaimStatus.COMPLETED
    assert first_claim.evidence_id is not None
    evidence_count = first_runtime.stores.evidence_store.count()

    second_runtime = create_persistent_sh3_kernel(database)
    restored_report = second_runtime.kernel.learning_feedback_loop.run(
        result,
        optimize=True,
        recover=True,
    )

    assert calls == {
        "learning": 1,
        "optimizer_request": 1,
        "optimizer_backend": 1,
        "optimizer_healing": 1,
        "recovery_strategy": 1,
        "recovery_execution": 1,
    }
    assert restored_report == first_report
    assert second_runtime.kernel.learning_feedback_loop.get(cycle_id) == first_report
    assert second_runtime.stores.evidence_store.count() == evidence_count
    restored_claim = second_runtime.stores.replay_claim_store.get(cycle_id)
    assert restored_claim is not None
    assert restored_claim.status is ReplayClaimStatus.COMPLETED
    assert restored_claim.evidence_id == first_claim.evidence_id
    assert second_runtime.kernel.optimizer_healing_boundary.records() == ()
    assert second_runtime.kernel.recovery_strategy_boundary.records() == ()
    assert second_runtime.kernel.recovery_execution_boundary.records() == ()
    assert second_runtime.kernel.meta_controller.healer.detected == 0
    assert second_runtime.kernel.meta_controller.healer.recovered == 0
