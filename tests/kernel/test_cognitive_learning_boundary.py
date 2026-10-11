from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from cognition.contracts import CognitiveGoal, CognitiveResult, CognitiveResultStatus
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.cognitive_learning_boundary import CognitiveLearningBoundary
from kernel.core import SH3Kernel

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


class RecordingLearning:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self._lock = Lock()

    def run(self, execution_result: dict[str, Any], *, context: EventPropagationContext | None = None) -> dict[str, Any]:
        with self._lock:
            self.calls += 1
        if self.fail:
            raise RuntimeError("learning failure")
        return {"loop_id": "learning:11-5", "score": 0.8, "memory_key": "memory:11-5", "input": execution_result}


def _result() -> CognitiveResult:
    goal = CognitiveGoal.create(
        "prepare release",
        owner="test",
        created_at=NOW,
        correlation_id="corr:11-5",
        trace_id="trace:11-5",
        tenant_id="tenant:11-5",
    )
    return CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        created_at=NOW,
        result_id="result:11-5",
        output={
            "goal": goal.to_dict(),
            "plan": {"steps": ["prepare release"]},
            "decision": {"selected_option": "prepare release"},
        },
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
    )


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="corr:11-5",
        causation_id="result:11-5",
        trace_id="trace:11-5",
        tenant_id="tenant:11-5",
    )


def test_request_is_deterministic_and_extracts_cognitive_result() -> None:
    learning = RecordingLearning()
    boundary = CognitiveLearningBoundary(learning)
    result = _result()
    first = boundary.record(result, context=_context(), created_at=NOW)
    second = boundary.record(result, context=_context(), created_at=NOW)
    assert first.request_id == second.request_id
    assert first.learning["memory_key"] == "memory:11-5"
    assert learning.calls == 1


def test_direct_execution_uses_learning_backend_without_event_bus() -> None:
    learning = RecordingLearning()
    boundary = CognitiveLearningBoundary(learning)
    result = boundary.record(_result(), context=_context(), created_at=NOW)
    assert result.success is True
    assert result.loop_id == "learning:11-5"
    assert boundary.get(result.request_id) is result


def test_event_bus_order_and_trace_are_preserved() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="11-5-audit", handler=events.append, priority=-100), replace=True)
    boundary = CognitiveLearningBoundary(RecordingLearning(), publisher)
    result = boundary.record(_result(), context=_context(), created_at=NOW)
    assert result.success is True
    assert [event.name for event in events] == ["CognitiveLearningRequested", "CognitiveLearningCompleted"]
    requested, completed = events
    assert completed.metadata.causation_id == requested.metadata.event_id
    assert completed.metadata.correlation_id == requested.metadata.correlation_id
    assert completed.metadata.trace_id == requested.metadata.trace_id
    assert completed.metadata.tenant_id == requested.metadata.tenant_id
    assert result.propagation_context.causation_id == completed.metadata.event_id


def test_event_bus_subscription_is_rebound_when_publisher_changes() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    first = EventBusPublisher(first_bus)
    second = EventBusPublisher(second_bus)
    boundary = CognitiveLearningBoundary(RecordingLearning(), first)
    assert first_bus.router.contains("cognition.learning-boundary")
    boundary.set_event_publisher(second)
    assert not first_bus.router.contains("cognition.learning-boundary")
    assert second_bus.router.contains("cognition.learning-boundary")


def test_failure_is_returned_and_failure_event_is_emitted() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="11-5-audit", handler=events.append, priority=-100), replace=True)
    boundary = CognitiveLearningBoundary(RecordingLearning(fail=True), publisher)
    result = boundary.record(_result(), context=_context(), created_at=NOW)
    assert result.success is False
    assert "learning failure" in (result.error or "")
    assert [event.name for event in events] == ["CognitiveLearningRequested", "CognitiveLearningFailed"]


def test_concurrent_duplicate_requests_execute_learning_once() -> None:
    learning = RecordingLearning()
    boundary = CognitiveLearningBoundary(learning)
    result = _result()
    context = _context()
    with ThreadPoolExecutor(max_workers=8) as executor:
        values = tuple(
            executor.map(
                lambda _: boundary.record(result, context=context, created_at=NOW),
                range(8),
            )
        )
    assert len({value.request_id for value in values}) == 1
    assert len({id(value) for value in values}) == 1
    assert learning.calls == 1


def test_kernel_owns_and_injects_cognitive_learning_boundary() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel(event_publisher=publisher)
    assert kernel.cognitive_learning_boundary.learning is kernel.learning_loop
    assert kernel.learning_feedback_loop.learning_boundary is kernel.cognitive_learning_boundary


def test_cognitive_learning_boundary_has_typed_immutable_results() -> None:
    boundary = CognitiveLearningBoundary(RecordingLearning())
    result = boundary.record(_result(), context=_context(), created_at=NOW)
    assert result.to_dict()["success"] is True
    assert result.learning["loop_id"] == "learning:11-5"
