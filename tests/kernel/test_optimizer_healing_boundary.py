from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from typing import Any

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel
from kernel.learning_optimizer_boundary import LearningOptimizationResult
from kernel.optimizer_healing_boundary import (
    OptimizerHealingBoundary,
    OptimizerHealingRequest,
)
from self_healing.core import SelfHealingCore

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def test_self_healing_context_is_isolated_between_threads() -> None:
    healer = SelfHealingCore()
    barrier = Barrier(2)
    contexts = (
        EventPropagationContext.create(
            correlation_id="parallel-healing-a",
            trace_id="parallel-trace-a",
            tenant_id="parallel-tenant-a",
        ),
        EventPropagationContext.create(
            correlation_id="parallel-healing-b",
            trace_id="parallel-trace-b",
            tenant_id="parallel-tenant-b",
        ),
    )

    def observe(context: EventPropagationContext) -> EventPropagationContext | None:
        healer.set_propagation_context(context)
        barrier.wait(timeout=5)
        return healer.propagation_context

    with ThreadPoolExecutor(max_workers=2) as executor:
        observed = tuple(executor.map(observe, contexts))

    assert observed == contexts


def _optimization_result(
    *,
    success: bool = False,
    error: str | None = "optimization failure",
) -> LearningOptimizationResult:
    return LearningOptimizationResult(
        request_id="learning-optimization:1",
        learning_record_id="record:1",
        optimizer_id="optimizer:1",
        success=success,
        optimization={"execution": ()},
        created_at=NOW,
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        error=error,
    )


def test_request_is_deterministic_and_requires_optimizer_failure() -> None:
    context = EventPropagationContext.create(
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="trace-1",
    )
    first = OptimizerHealingRequest.from_result(
        _optimization_result(), context=context, created_at=NOW
    )
    second = OptimizerHealingRequest.from_result(
        _optimization_result(), context=context, created_at=NOW
    )
    assert first == second
    assert first.request_id == second.request_id
    assert first.optimizer_id == "optimizer:1"
    with pytest.raises(ValueError, match="must indicate failure"):
        OptimizerHealingRequest.from_result(
            _optimization_result(success=True, error=None),
            context=context,
            created_at=NOW,
        )


def test_boundary_executes_real_self_healing_api_without_event_bus() -> None:
    healer = SelfHealingCore()
    boundary = OptimizerHealingBoundary(healer)
    result = boundary.request(
        _optimization_result(),
        context=EventPropagationContext.create(correlation_id="corr-2"),
        created_at=NOW,
    )
    assert result.success is True
    assert result.failure_id
    assert result.healing["status"] == "context_rebuilt"
    assert healer.detected == 1
    assert healer.recovered == 1
    assert boundary.get(result.request_id) is result


def test_boundary_is_idempotent_for_duplicate_optimizer_result() -> None:
    healer = SelfHealingCore()
    boundary = OptimizerHealingBoundary(healer)
    context = EventPropagationContext.create(correlation_id="corr-3")
    first = boundary.request(_optimization_result(), context=context, created_at=NOW)
    second = boundary.request(_optimization_result(), context=context, created_at=NOW)
    assert first is second
    assert healer.detected == 1
    assert len(boundary.records()) == 1


def test_boundary_event_path_preserves_causation_and_reports_completion() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer = SelfHealingCore(event_publisher=publisher)
    boundary = OptimizerHealingBoundary(
        healer,
        publisher,
        subscriber_id="phase3-healing-boundary",
    )
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="phase3-healing-audit",
            handler=events.append,
            priority=-200,
        ),
        replace=True,
    )
    result = boundary.request(
        _optimization_result(),
        context=EventPropagationContext.create(
            correlation_id="corr-4",
            trace_id="trace-4",
            tenant_id="tenant-4",
            causation_id="optimizer-failed-event",
        ),
        created_at=NOW,
    )
    names = [event.name for event in events]
    assert result.success is True
    assert boundary.started is True
    assert "OptimizerHealingRequested" in names
    assert "FailureDetected" in names
    assert "RecoveryCompleted" in names
    assert "OptimizerHealingCompleted" in names
    requested = next(event for event in events if event.name == "OptimizerHealingRequested")
    failure = next(event for event in events if event.name == "FailureDetected")
    completed = next(event for event in events if event.name == "OptimizerHealingCompleted")
    assert requested.metadata.causation_id == "optimizer-failed-event"
    assert failure.metadata.causation_id == requested.metadata.event_id
    assert completed.metadata.causation_id == next(
        event.metadata.event_id for event in reversed(events) if event.name == "RecoveryCompleted"
    )
    assert result.correlation_id == "corr-4"
    assert result.trace_id == "trace-4"
    assert result.tenant_id == "tenant-4"
    assert result.propagation_context.causation_id == completed.metadata.event_id
    assert boundary.propagation_context is not None
    assert boundary.propagation_context.causation_id == completed.metadata.event_id


def test_boundary_event_handler_accepts_serialized_request() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    boundary = OptimizerHealingBoundary(
        SelfHealingCore(event_publisher=publisher),
        publisher,
        subscriber_id="phase3-serialized-boundary",
    )
    request = OptimizerHealingRequest.from_result(
        _optimization_result(),
        context=EventPropagationContext.create(correlation_id="corr-5"),
        created_at=NOW,
    )
    publisher.publish(
        Event.create(
            event_name="OptimizerHealingRequested",
            producer="test",
            payload={"request": request.to_dict()},
            category=Category.ACTION,
            event_type=EventType.START,
            correlation_id="corr-5",
        )
    )
    result = boundary.get(request.request_id)
    assert result is not None
    assert result.success is True


def test_boundary_returns_failure_when_self_healing_raises() -> None:
    class FailingHealer:
        def __init__(self) -> None:
            self.context: EventPropagationContext | None = None

        def set_propagation_context(self, context: EventPropagationContext | None) -> None:
            self.context = context

        @property
        def propagation_context(self) -> EventPropagationContext | None:
            return self.context

        def detect(self, exc: Exception, context: Mapping[str, Any] | None = None) -> Any:
            raise RuntimeError("healing detection failure")

        def recover_with_learning(self, snapshot: Any, max_attempts: int = 1) -> Any:
            raise AssertionError("must not execute after detect failure")

    boundary = OptimizerHealingBoundary(FailingHealer())
    result = boundary.request(
        _optimization_result(),
        context=EventPropagationContext.create(correlation_id="corr-6"),
        created_at=NOW,
    )
    assert result.success is False
    assert result.error == "healing detection failure"
    assert result.healing == {}


def test_closed_loop_uses_optimizer_healing_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="phase3-closed-loop-audit",
            handler=events.append,
            priority=-200,
        ),
        replace=True,
    )
    kernel = SH3Kernel(event_publisher=publisher)

    def fail_optimize(
        self: Any,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        raise RuntimeError("optimizer boundary failure")

    monkeypatch.setattr(kernel.system_optimizer.__class__, "optimize", fail_optimize)

    goal = "phase 11-3"
    from cognition.contracts import (
        CognitiveGoal,
        CognitiveLifecycleState,
        CognitiveResult,
        CognitiveResultStatus,
    )

    goal_contract = CognitiveGoal.create(goal, created_at=NOW, correlation_id="corr-7", trace_id="trace-7")
    result = CognitiveResult.create(
        goal_contract,
        status=CognitiveResultStatus.SUCCESS,
        lifecycle_state=CognitiveLifecycleState.COMPLETED,
        created_at=NOW,
        output={
            "goal": goal_contract.to_dict(),
            "plan": {"steps": [goal]},
            "decision": {"selected_option": goal},
        },
        result_id="result:phase11-3",
    )

    report = kernel.learning_feedback_loop.run(result, recover=True)
    assert report.status.value == "recovered"
    assert isinstance(report.healing_result, dict)
    assert report.healing_result["success"] is True
    assert any(event.name == "OptimizerHealingRequested" for event in events)
    assert any(event.name == "OptimizerHealingCompleted" for event in events)
    assert kernel.optimizer_healing_boundary.records()


def test_closed_loop_recovery_flag_is_preserved_for_optimizer_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = SH3Kernel()

    def fail_optimize(
        self: Any,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        raise RuntimeError("optimizer failure without recovery")

    monkeypatch.setattr(kernel.system_optimizer.__class__, "optimize", fail_optimize)

    from cognition.contracts import (
        CognitiveGoal,
        CognitiveLifecycleState,
        CognitiveResult,
        CognitiveResultStatus,
    )

    goal = CognitiveGoal.create("phase 11-3 no recovery", created_at=NOW, correlation_id="corr-8")
    result = CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        lifecycle_state=CognitiveLifecycleState.COMPLETED,
        created_at=NOW,
        output={"goal": goal.to_dict(), "plan": {"steps": ["phase 11-3"]}, "decision": {"selected_option": "phase 11-3"}},
        result_id="result:phase11-3-no-recovery",
    )

    report = kernel.learning_feedback_loop.run(result, recover=False)
    assert report.status.value == "failed"
    assert report.healing_result is None
    assert kernel.optimizer_healing_boundary.records() == ()
