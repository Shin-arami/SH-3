from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary, RecoveryStrategyResult
from self_healing.core import FailureSnapshot, SelfHealingCore

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


def _snapshot() -> FailureSnapshot:
    return FailureSnapshot.create(ValueError("strategy boundary"), {"operation": "strategy"})


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="strategy-correlation",
        trace_id="strategy-trace",
        tenant_id="strategy-tenant",
    )


def test_boundary_evaluates_and_selects_deterministically() -> None:
    healer = SelfHealingCore()
    boundary = RecoveryStrategyBoundary(healer)
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    assert isinstance(result, RecoveryStrategyResult)
    assert result.selected_strategy == "rebuild_context"
    assert [item.strategy for item in result.evaluations] == [
        "rebuild_context",
        "retry_safe",
        "fallback_default",
    ]
    assert result.selected.strategy == result.selected_strategy
    assert result.learned is False
    assert result.confidence == 0.0


def test_recovery_strategy_identity_is_context_scoped() -> None:
    healer = SelfHealingCore()
    boundary = RecoveryStrategyBoundary(healer)
    snapshot = _snapshot()
    first_context = _context()
    second_context = EventPropagationContext.create(
        correlation_id="strategy-correlation-other",
        causation_id="strategy-cause-other",
        trace_id="strategy-trace-other",
        tenant_id="strategy-tenant-other",
    )

    first = boundary.request(snapshot, context=first_context, created_at=NOW)
    replay = boundary.request(snapshot, context=first_context, created_at=NOW)
    other_trace = boundary.request(snapshot, context=second_context, created_at=NOW)

    assert first.request_id == replay.request_id
    assert first.request_id != other_trace.request_id


def test_boundary_uses_existing_learned_selection() -> None:
    from services.learning import LearningService

    learning = LearningService()
    learning.start()
    for _ in range(3):
        learning.record("self_healing.recovery", 1.0, success=True, details={"strategy": "retry_safe"})
        learning.record("self_healing.recovery", 0.0, success=False, details={"strategy": "rebuild_context"})
    healer = SelfHealingCore(learning_service=learning)
    boundary = RecoveryStrategyBoundary(healer)
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    assert result.selected_strategy == "retry_safe"
    rates = {item.strategy: item.success_rate for item in result.evaluations}
    assert rates["retry_safe"] == 1.0
    assert rates["rebuild_context"] == 0.0


def test_event_path_preserves_causation_and_contract() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer = SelfHealingCore(event_publisher=publisher)
    boundary = RecoveryStrategyBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="strategy-audit", handler=events.append, priority=200))
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    names = [event.name for event in events]
    assert result.selected_strategy == "rebuild_context"
    assert names == ["RecoveryStrategyRequested", "RecoveryStrategyEvaluated", "RecoveryStrategySelected"]
    assert all(event.category is Category.STRATEGY for event in events)
    assert events[0].event_type is EventType.START
    assert events[1].event_type is EventType.UPDATED
    assert events[2].event_type is EventType.COMPLETE
    assert events[1].metadata.causation_id == events[0].metadata.event_id
    assert events[2].metadata.causation_id == events[1].metadata.event_id
    assert result.correlation_id == "strategy-correlation"
    assert result.trace_id == "strategy-trace"
    assert result.tenant_id == "strategy-tenant"


def test_boundary_is_idempotent_and_thread_safe() -> None:
    healer = SelfHealingCore()
    boundary = RecoveryStrategyBoundary(healer)
    snapshot = _snapshot()
    context = _context()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _: boundary.request(snapshot, context=context, created_at=NOW), range(32)))
    assert all(item is results[0] for item in results)
    assert len(boundary.records()) == 1


def test_publisher_replacement_rebinds_subscription() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    boundary = RecoveryStrategyBoundary(SelfHealingCore(), EventBusPublisher(first_bus))
    assert first_bus.router.contains("recovery.strategy-boundary")
    boundary.set_event_publisher(EventBusPublisher(second_bus))
    assert not first_bus.router.contains("recovery.strategy-boundary")
    assert second_bus.router.contains("recovery.strategy-boundary")


def test_kernel_ownership_and_optimizer_healing_use_strategy_boundary() -> None:
    kernel = SH3Kernel()
    assert kernel.recovery_strategy_boundary is kernel.learning_feedback_loop.recovery_strategy_boundary
    assert kernel.optimizer_healing_boundary.strategy_boundary is kernel.recovery_strategy_boundary


def test_serialized_result_is_immutable() -> None:
    boundary = RecoveryStrategyBoundary(SelfHealingCore())
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    data = result.to_dict()
    data["evaluations"][0]["strategy"] = "mutated"
    assert result.evaluations[0].strategy != "mutated"
