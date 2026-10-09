from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import cast

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel
from kernel.recovery_execution_boundary import (
    RecoveryExecutionBoundary,
    RecoveryExecutionResult,
)
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary, RecoveryStrategyResult
from self_healing.core import FailureSnapshot, SelfHealingCore

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


def _snapshot(message: str = "execution boundary") -> FailureSnapshot:
    return FailureSnapshot.create(ValueError(message), {"operation": "execution"})


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="execution-correlation",
        trace_id="execution-trace",
        tenant_id="execution-tenant",
    )


def _strategy_result(
    healer: SelfHealingCore | None = None,
) -> tuple[SelfHealingCore, RecoveryStrategyBoundary, RecoveryStrategyResult, FailureSnapshot]:
    current = healer or SelfHealingCore()
    strategy = RecoveryStrategyBoundary(current)
    snapshot = _snapshot()
    result = strategy.request(snapshot, context=_context(), created_at=NOW)
    return current, strategy, result, snapshot


def test_boundary_executes_selected_strategy_directly() -> None:
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer)
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    assert isinstance(result, RecoveryExecutionResult)
    assert result.success is True
    assert result.strategy == "rebuild_context"
    assert result.error is None
    assert result.result is not None


def test_event_path_preserves_causation_and_contract() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="execution-audit", handler=events.append, priority=200))
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    relevant = [event for event in events if event.name.startswith("RecoveryExecution")]
    assert [event.name for event in relevant] == ["RecoveryExecutionRequested", "RecoveryExecutionCompleted"]
    assert relevant[0].category is Category.ACTION
    assert relevant[0].event_type is EventType.START
    assert relevant[1].event_type is EventType.COMPLETE
    assert relevant[1].metadata.causation_id == relevant[0].metadata.event_id
    assert result.correlation_id == "execution-correlation"
    assert result.trace_id == "execution-trace"
    assert result.tenant_id == "execution-tenant"


def test_event_versions_are_canonical() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="execution-version", handler=events.append, priority=-100))
    boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    relevant = [event for event in events if event.name.startswith("RecoveryExecution")]
    assert relevant
    assert all(event.metadata.event_version == "1.0.0" for event in relevant)


def test_boundary_is_idempotent_and_thread_safe() -> None:
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer)
    context = _context()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(
            executor.map(
                lambda _: boundary.request(strategy_result, snapshot, context=context, created_at=NOW),
                range(32),
            )
        )
    assert all(item is results[0] for item in results)
    assert len(boundary.records()) == 1


def test_publisher_replacement_rebinds_subscription() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    boundary = RecoveryExecutionBoundary(SelfHealingCore(), EventBusPublisher(first_bus))
    assert first_bus.router.contains("recovery.execution-boundary")
    boundary.set_event_publisher(EventBusPublisher(second_bus))
    assert not first_bus.router.contains("recovery.execution-boundary")
    assert second_bus.router.contains("recovery.execution-boundary")


def test_failure_is_captured_as_typed_result() -> None:
    class FailingHealer(SelfHealingCore):
        def recover_with_strategy(self, snapshot: FailureSnapshot, strategy: str) -> object:
            raise RuntimeError("execution failure")

    failing = FailingHealer()
    snapshot = _snapshot()
    strategy_result = RecoveryStrategyBoundary(failing).request(
        snapshot,
        context=_context(),
        created_at=NOW,
    )
    boundary = RecoveryExecutionBoundary(failing)
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    assert result.success is False
    assert result.error == "execution failure"
    assert result.result is None


def test_failure_event_is_published() -> None:
    class FailingHealer(SelfHealingCore):
        def recover_with_strategy(self, snapshot: FailureSnapshot, strategy: str) -> object:
            raise RuntimeError("execution failure")

    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer = FailingHealer()
    snapshot = _snapshot()
    strategy_result = RecoveryStrategyBoundary(healer).request(snapshot, context=_context(), created_at=NOW)
    boundary = RecoveryExecutionBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="execution-failure-audit", handler=events.append, priority=200))
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    relevant = [event for event in events if event.name.startswith("RecoveryExecution")]
    assert result.success is False
    assert [event.name for event in relevant] == ["RecoveryExecutionRequested", "RecoveryExecutionFailed"]
    assert relevant[-1].event_type is EventType.FAILURE
    assert relevant[-1].causation_id == relevant[0].id
    assert relevant[-1].payload["error"] == "execution failure"


def test_kernel_owns_shared_execution_boundary() -> None:
    kernel = SH3Kernel()
    assert kernel.recovery_execution_boundary is kernel.learning_feedback_loop.recovery_execution_boundary
    assert kernel.optimizer_healing_boundary.execution_boundary is kernel.recovery_execution_boundary


def test_kernel_recover_uses_execution_boundary() -> None:
    kernel = SH3Kernel()
    result = kernel.recover(RuntimeError("kernel recovery"), {"operation": "kernel"})
    assert result is not None
    assert kernel.recovery_execution_boundary.records()


def test_request_rejects_mismatched_failure() -> None:
    healer, _, strategy_result, _ = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer)
    other = _snapshot("other")
    with pytest.raises(ValueError, match="failure_id"):
        boundary.request(strategy_result, other, context=_context(), created_at=NOW)


def test_request_requires_strategy_result_type() -> None:
    boundary = RecoveryExecutionBoundary(SelfHealingCore())
    with pytest.raises(TypeError, match="RecoveryStrategyResult"):
        boundary.request(cast(RecoveryStrategyResult, object()), _snapshot(), context=_context(), created_at=NOW)
