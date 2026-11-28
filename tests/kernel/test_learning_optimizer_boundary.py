from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.learning_optimizer_boundary import (
    LearningOptimizationRequest,
    LearningOptimizerBoundary,
)

NOW = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)


def _learning_result(record_id: str = "record:1") -> dict[str, Any]:
    return {
        "record_id": record_id,
        "domain": "self_healing.recovery",
        "success": True,
        "score": 0.65,
        "details": {"strategy": "retry_safe", "source": "phase3"},
    }


class RecordingOptimizer:
    def __init__(self) -> None:
        self.calls = 0
        self.optimizer_id = "optimizer:test"

    def optimize(
        self,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        self.calls += 1
        return {
            "optimizer_id": self.optimizer_id,
            "execution": (),
            "execute": execute,
            "context": context,
        }


def test_learning_result_is_converted_to_deterministic_request() -> None:
    context = EventPropagationContext.create(
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
    )
    first = LearningOptimizationRequest.from_learning_result(
        _learning_result(), context=context, created_at=NOW
    )
    second = LearningOptimizationRequest.from_learning_result(
        _learning_result(), context=context, created_at=NOW
    )
    assert first == second
    assert first.request_id == second.request_id
    assert first.learning_record_id == "record:1"
    assert first.strategy == "retry_safe"




def test_learning_optimization_request_identity_is_context_scoped() -> None:
    learning_result = _learning_result("record:context-scope")
    first_context = EventPropagationContext.create(
        correlation_id="corr:scope-a",
        causation_id="cause:scope-a",
        trace_id="trace:scope-a",
        tenant_id="tenant:scope-a",
    )
    second_context = EventPropagationContext.create(
        correlation_id="corr:scope-b",
        causation_id="cause:scope-b",
        trace_id="trace:scope-b",
        tenant_id="tenant:scope-b",
    )

    first = LearningOptimizationRequest.from_learning_result(
        learning_result, context=first_context, created_at=NOW
    )
    replay = LearningOptimizationRequest.from_learning_result(
        learning_result, context=first_context, created_at=NOW
    )
    other_trace = LearningOptimizationRequest.from_learning_result(
        learning_result, context=second_context, created_at=NOW
    )

    assert first.request_id == replay.request_id
    assert first.request_id != other_trace.request_id


def test_learning_result_uses_legacy_memory_key_as_record_id() -> None:
    context = EventPropagationContext.create(correlation_id="corr-legacy")
    learning_result = _learning_result("record:legacy")
    learning_result.pop("record_id")
    learning_result["memory_key"] = "memory:legacy"
    request = LearningOptimizationRequest.from_learning_result(
        learning_result, context=context, created_at=NOW
    )
    assert request.learning_record_id == "memory:legacy"
    assert request.request_id == LearningOptimizationRequest.from_learning_result(
        learning_result, context=context, created_at=NOW
    ).request_id

def test_learning_result_without_domain_uses_compatibility_domain() -> None:
    optimizer = RecordingOptimizer()
    boundary = LearningOptimizerBoundary(optimizer)
    context = EventPropagationContext.create(correlation_id="corr-domain")
    learning_result = {"loop_id": "loop-domain", "memory_key": "memory-domain", "score": 0.65, "success": True}
    result = boundary.request(learning_result, context=context, created_at=NOW)
    request = LearningOptimizationRequest.from_learning_result(
        learning_result, context=context, created_at=NOW
    )
    assert request.domain == "cognition.result"
    assert request.success is True
    assert result.learning_record_id == "memory-domain"
    assert result.success is True



def test_boundary_executes_existing_optimizer_api_without_event_bus() -> None:
    optimizer = RecordingOptimizer()
    boundary = LearningOptimizerBoundary(optimizer)
    context = EventPropagationContext.create(
        correlation_id="corr-2", trace_id="trace-2"
    )
    result = boundary.request(_learning_result(), context=context, created_at=NOW)
    assert result.success is True
    assert result.optimization["optimizer_id"] == "optimizer:test"
    assert result.optimization["execute"] is True
    assert optimizer.calls == 1


def test_boundary_uses_event_bus_and_preserves_causation() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    optimizer = RecordingOptimizer()
    boundary = LearningOptimizerBoundary(
        optimizer,
        publisher,
        subscriber_id="phase3-optimizer-boundary",
    )
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="phase3-audit",
            handler=events.append,
            priority=-200,
        ),
        replace=True,
    )
    context = EventPropagationContext.create(
        correlation_id="corr-3",
        trace_id="trace-3",
        tenant_id="tenant-3",
        causation_id="learning-event",
    )
    result = boundary.request(
        _learning_result("record:3"), context=context, created_at=NOW
    )
    names = [event.name for event in events]
    requested = next(
        event for event in events if event.name == "LearningOptimizationRequested"
    )
    completed = next(
        event for event in events if event.name == "LearningOptimizationCompleted"
    )
    assert result.success is True
    assert optimizer.calls == 1
    assert "LearningOptimizationRequested" in names
    assert "LearningOptimizationCompleted" in names
    assert requested.metadata.causation_id == "learning-event"
    assert completed.metadata.causation_id == requested.metadata.event_id
    assert result.causation_id == requested.metadata.event_id
    assert result.propagation_context.causation_id == completed.metadata.event_id
    assert boundary.propagation_context is not None
    assert boundary.propagation_context.causation_id == completed.metadata.event_id

    publisher.publish(requested)
    assert optimizer.calls == 1
    assert len(
        [event for event in events if event.name == "LearningOptimizationCompleted"]
    ) == 1


def test_boundary_is_idempotent_for_duplicate_learning_result() -> None:
    optimizer = RecordingOptimizer()
    boundary = LearningOptimizerBoundary(optimizer)
    context = EventPropagationContext.create(correlation_id="corr-4")
    first = boundary.request(
        _learning_result("record:4"), context=context, created_at=NOW
    )
    second = boundary.request(
        _learning_result("record:4"), context=context, created_at=NOW
    )
    assert first is second
    assert optimizer.calls == 1
    assert len(boundary.records()) == 1


def test_boundary_returns_failure_when_optimizer_raises() -> None:
    class FailingOptimizer(RecordingOptimizer):
        def optimize(
            self,
            *,
            context: EventPropagationContext | None = None,
            execute: bool = False,
        ) -> dict[str, Any]:
            self.calls += 1
            raise RuntimeError("optimization failure")

    optimizer = FailingOptimizer()
    boundary = LearningOptimizerBoundary(optimizer)
    result = boundary.request(
        _learning_result("record:5"),
        context=EventPropagationContext.create(correlation_id="corr-5"),
        created_at=NOW,
    )
    assert result.success is False
    assert result.error == "optimization failure"
    assert result.optimization == {}
