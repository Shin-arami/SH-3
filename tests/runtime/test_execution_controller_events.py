from __future__ import annotations

from datetime import UTC, datetime, timedelta

from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event
from runtime.execution import ExecutionRequest, ExecutionSnapshot, ExecutionState
from runtime.execution_controller import RuntimeExecutionController
from runtime.state_machine import RuntimeExecutionStateMachine


def _build_bus() -> tuple[EventBus, EventBusPublisher, list[Event]]:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="runtime-controller-test",
            handler=events.append,
        )
    )
    return bus, publisher, events


def _snapshot(
    *,
    state: ExecutionState,
    timeout: float | None = None,
) -> ExecutionSnapshot:
    request = ExecutionRequest.create(
        execution_id="runtime-controller-event-test",
        operation="runtime.execute",
        priority=Priority.NORMAL,
        timeout=timeout,
        correlation_id="corr-controller",
        trace_id="trace-controller",
        tenant_id="tenant-controller",
    )
    now = datetime.now(UTC)
    snapshot = ExecutionSnapshot.create(request, now=now)
    machine = RuntimeExecutionStateMachine()
    machine.register(snapshot)
    if state is not ExecutionState.CREATED:
        machine.transition(request.execution_id, ExecutionState.QUEUED, now=now)
    if state is ExecutionState.RUNNING:
        machine.transition(request.execution_id, ExecutionState.RUNNING, now=now)
    return machine.get(request.execution_id)  # type: ignore[return-value]


def _controller(
    snapshot: ExecutionSnapshot,
    publisher: EventBusPublisher,
) -> RuntimeExecutionController:
    machine = RuntimeExecutionStateMachine()
    machine.register(snapshot)
    return RuntimeExecutionController(machine, event_publisher=publisher)


def test_cancel_publishes_cancel_event() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.QUEUED)
    controller = _controller(snapshot, publisher)

    result = controller.cancel(snapshot.execution_id)

    assert result.requested
    assert result.state is ExecutionState.CANCELLED
    assert [event.name for event in events] == ["RuntimeExecutionCancelled"]
    event = events[0]
    assert event.event_type is EventType.CANCEL
    assert event.metadata.correlation_id == "corr-controller"
    assert event.metadata.trace_id == "trace-controller"
    assert event.metadata.tenant_id == "tenant-controller"


def test_running_cancel_waits_for_completion_before_publishing() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.RUNNING)
    controller = _controller(snapshot, publisher)

    requested = controller.cancel(snapshot.execution_id)

    assert requested.requested
    assert requested.state is ExecutionState.CANCEL_REQUESTED
    assert events == []

    completed = controller.complete_cancellation(snapshot.execution_id)

    assert completed.state is ExecutionState.CANCELLED
    assert [event.name for event in events] == ["RuntimeExecutionCancelled"]
    assert events[0].event_type is EventType.CANCEL


def test_timeout_publishes_timeout_event() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.RUNNING, timeout=1.0)
    controller = _controller(snapshot, publisher)

    assert snapshot.started_at is not None
    now = snapshot.started_at + timedelta(seconds=1)

    result = controller.timeout(snapshot.execution_id, now=now)

    assert result.timed_out
    assert result.state is ExecutionState.TIMED_OUT
    assert [event.name for event in events] == ["RuntimeExecutionTimedOut"]
    assert events[0].event_type is EventType.TIMEOUT


def test_cancel_cleanup_failure_publishes_cleanup_failed() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.QUEUED)
    controller = _controller(snapshot, publisher)

    controller.register_cleanup(
        snapshot.execution_id,
        lambda: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
        name="resource",
    )

    result = controller.cancel(snapshot.execution_id)

    assert result.state is ExecutionState.CANCELLED
    assert result.cleanup is not None
    assert result.cleanup.failed
    assert [event.name for event in events] == [
        "RuntimeExecutionCancelled",
        "CleanupFailed",
    ]
    assert events[0].event_type is EventType.CANCEL
    assert events[1].event_type is EventType.FAILURE
    assert events[1].metadata.causation_id == events[0].id
    assert events[1].payload["execution_id"] == snapshot.execution_id
    assert events[1].payload["failures"][0]["name"] == "resource"


def test_timeout_cleanup_failure_publishes_cleanup_failed() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.RUNNING, timeout=1.0)
    controller = _controller(snapshot, publisher)

    controller.register_cleanup(
        snapshot.execution_id,
        lambda: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
        name="resource",
    )

    assert snapshot.started_at is not None
    now = snapshot.started_at + timedelta(seconds=1)
    result = controller.timeout(snapshot.execution_id, now=now)

    assert result.timed_out
    assert result.cleanup is not None
    assert result.cleanup.failed
    assert [event.name for event in events] == [
        "RuntimeExecutionTimedOut",
        "CleanupFailed",
    ]
    assert events[0].event_type is EventType.TIMEOUT
    assert events[1].event_type is EventType.FAILURE
    assert events[1].metadata.causation_id == events[0].id


def test_idempotent_cancel_does_not_republish_events() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.QUEUED)
    controller = _controller(snapshot, publisher)

    first = controller.cancel(snapshot.execution_id)
    second = controller.cancel(snapshot.execution_id)

    assert first.state is ExecutionState.CANCELLED
    assert second.state is ExecutionState.CANCELLED
    assert [event.name for event in events] == ["RuntimeExecutionCancelled"]


def test_idempotent_timeout_does_not_republish_events() -> None:
    _, publisher, events = _build_bus()
    snapshot = _snapshot(state=ExecutionState.RUNNING, timeout=1.0)
    controller = _controller(snapshot, publisher)

    assert snapshot.started_at is not None
    now = snapshot.started_at + timedelta(seconds=1)
    first = controller.timeout(snapshot.execution_id, now=now)
    second = controller.timeout(snapshot.execution_id, now=now)

    assert first.timed_out
    assert second.timed_out
    assert [event.name for event in events] == ["RuntimeExecutionTimedOut"]
