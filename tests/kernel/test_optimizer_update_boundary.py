from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import pytest

from cognition.policy import PolicyRule
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel
from kernel.optimizer_update_boundary import OptimizationUpdateKind, OptimizationUpdateResult

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="update-correlation",
        causation_id="update-cause",
        trace_id="update-trace",
        tenant_id="update-tenant",
    )


def _runtime_optimization(kernel: SH3Kernel) -> dict[str, Any]:
    for index in range(7):
        kernel.context_manager.push(f"ctx-{index}")
    return kernel.system_optimizer.optimize(context=_context(), execute=False)


def _policy_optimization(kernel: SH3Kernel) -> dict[str, Any]:
    for index in range(10):
        kernel.policy.add_rule(PolicyRule(f"rule-{index}"))
    return kernel.system_optimizer.optimize(context=_context(), execute=False)


def test_kernel_owns_optimizer_update_boundary() -> None:
    kernel = SH3Kernel()
    assert kernel.optimizer_update_boundary is kernel.learning_optimizer_boundary.update_boundary


def test_update_boundary_applies_runtime_update_with_typed_result() -> None:
    kernel = SH3Kernel()
    optimization = _runtime_optimization(kernel)
    result = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    assert isinstance(result, OptimizationUpdateResult)
    assert result.success is True
    assert result.changed is True
    assert result.updates[0].target is OptimizationUpdateKind.RUNTIME
    assert kernel.context_manager.snapshot()["depth"] == 6


def test_update_boundary_applies_policy_update() -> None:
    kernel = SH3Kernel()
    optimization = _policy_optimization(kernel)
    before = len(kernel.policy.rules)
    result = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    assert result.success is True
    assert result.updates[0].target is OptimizationUpdateKind.POLICY
    assert result.updates[0].changed is True
    assert len(kernel.policy.rules) == before - 1


def test_update_boundary_emits_context_update_and_completion() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="optimizer-update-test", handler=events.append, priority=-100))
    kernel = SH3Kernel(event_publisher=publisher)
    optimization = _runtime_optimization(kernel)
    result = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    names = [event.name for event in events]
    assert "OptimizationUpdateRequested" in names
    assert "ContextUpdated" in names
    assert "OptimizationUpdateCompleted" in names
    context_event = next(event for event in events if event.name == "ContextUpdated")
    assert context_event.category is Category.RUNTIME
    assert context_event.event_type is EventType.UPDATED
    assert context_event.metadata.correlation_id == result.correlation_id
    assert context_event.metadata.trace_id == result.trace_id
    assert context_event.metadata.tenant_id == result.tenant_id


def test_update_boundary_emits_policy_update() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="optimizer-policy-update-test", handler=events.append, priority=-100))
    kernel = SH3Kernel(event_publisher=publisher)
    optimization = _policy_optimization(kernel)
    result = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    policy_event = next(event for event in events if event.name == "PolicyUpdated")
    assert policy_event.category is Category.ACTION
    assert policy_event.event_type is EventType.UPDATED
    assert policy_event.payload["request_id"] == result.request_id


def test_learning_optimizer_boundary_uses_update_boundary_once() -> None:
    kernel = SH3Kernel()
    kernel.context_manager.push("one")
    kernel.context_manager.push("two")
    learning_result = {
        "loop_id": "loop:test",
        "memory_key": "memory:test",
        "domain": "cognition.result",
        "score": 1.0,
        "success": True,
    }
    result = kernel.learning_optimizer_boundary.request(learning_result, context=_context(), created_at=NOW)

    assert result.success is True
    assert "update" in result.optimization
    assert kernel.optimizer_update_boundary.records()


def test_update_boundary_is_idempotent_for_duplicate_request() -> None:
    kernel = SH3Kernel()
    optimization = _runtime_optimization(kernel)
    boundary = kernel.optimizer_update_boundary
    first = boundary.request(optimization, context=_context(), created_at=NOW)
    second = boundary.request(optimization, context=_context(), created_at=NOW)

    assert first is second
    assert len(boundary.records()) == 1
    assert kernel.context_manager.snapshot()["depth"] == 6


def test_update_boundary_rejects_unsupported_action() -> None:
    kernel = SH3Kernel()
    optimization = {
        "optimizer_id": kernel.system_optimizer.optimizer_id,
        "rebalance": {"actions": ["unsupported"]},
    }
    with pytest.raises(ValueError, match="unsupported optimization update action"):
        kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)


def test_update_boundary_rejects_invalid_optimizer_payload() -> None:
    with pytest.raises(TypeError, match=r"optimization\.rebalance"):
        SH3Kernel().optimizer_update_boundary.request({"optimizer_id": "optimizer"}, context=_context(), created_at=NOW)


def test_update_boundary_supports_concurrent_duplicate_requests() -> None:
    kernel = SH3Kernel()
    optimization = _runtime_optimization(kernel)
    boundary = kernel.optimizer_update_boundary
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _: boundary.request(optimization, context=_context(), created_at=NOW), range(8)))

    assert len({item.request_id for item in results}) == 1
    assert len(boundary.records()) == 1
    assert kernel.context_manager.snapshot()["depth"] == 6
