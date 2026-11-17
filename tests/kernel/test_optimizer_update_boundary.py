from __future__ import annotations

from collections.abc import Mapping
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
from kernel.optimizer_update_boundary import (
    OptimizationUpdateBoundary,
    OptimizationUpdateKind,
    OptimizationUpdateResult,
)
from kernel.system_optimizer import OptimizationActionResult

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
    result = kernel.optimizer_update_boundary.request(
        optimization,
        context=_context(),
        created_at=NOW,
        idempotency_key="optimizer-update-parent:event-contract",
    )

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
    assert context_event.payload["parent_idempotency_key"] == "optimizer-update-parent:event-contract"
    assert context_event.payload["idempotency_key"].startswith("optimizer-action:")


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


def test_update_request_event_replay_does_not_repeat_side_effects() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="update-replay-audit",
            handler=events.append,
            priority=-100,
        )
    )
    kernel = SH3Kernel(event_publisher=publisher)
    optimization = _runtime_optimization(kernel)
    result = kernel.optimizer_update_boundary.request(
        optimization, context=_context(), created_at=NOW
    )
    requested = next(
        event for event in events if event.name == "OptimizationUpdateRequested"
    )
    completed_count = len(
        [event for event in events if event.name == "OptimizationUpdateCompleted"]
    )
    updated_count = len(
        [event for event in events if event.name in {"ContextUpdated", "PolicyUpdated", "MemoryUpdated"}]
    )
    context_after_first_run = kernel.context_manager.snapshot()

    publisher.publish(requested)

    assert kernel.optimizer_update_boundary.get(result.request_id) is result
    assert kernel.context_manager.snapshot() == context_after_first_run
    assert len(kernel.optimizer_update_boundary.records()) == 1
    assert len(
        [event for event in events if event.name == "OptimizationUpdateCompleted"]
    ) == completed_count == 1
    assert len(
        [event for event in events if event.name in {"ContextUpdated", "PolicyUpdated", "MemoryUpdated"}]
    ) == updated_count


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

def test_update_boundary_does_not_share_results_across_trace_contexts() -> None:
    kernel = SH3Kernel()
    optimization = {
        "optimizer_id": kernel.system_optimizer.optimizer_id,
        "rebalance": {"actions": []},
    }
    first_context = EventPropagationContext.create(
        correlation_id="update-isolation-a",
        causation_id="update-cause-a",
        trace_id="update-trace-a",
        tenant_id="update-tenant-a",
    )
    second_context = EventPropagationContext.create(
        correlation_id="update-isolation-b",
        causation_id="update-cause-b",
        trace_id="update-trace-b",
        tenant_id="update-tenant-b",
    )

    first = kernel.optimizer_update_boundary.request(
        optimization, context=first_context, created_at=NOW
    )
    second = kernel.optimizer_update_boundary.request(
        optimization, context=second_context, created_at=NOW
    )

    assert first.request_id != second.request_id
    assert first.propagation_context.correlation_id == first_context.correlation_id
    assert first.propagation_context.trace_id == first_context.trace_id
    assert first.propagation_context.tenant_id == first_context.tenant_id
    assert second.propagation_context.correlation_id == second_context.correlation_id
    assert second.propagation_context.trace_id == second_context.trace_id
    assert second.propagation_context.tenant_id == second_context.tenant_id


def test_update_boundary_preserves_action_and_parent_idempotency_keys() -> None:
    kernel = SH3Kernel()
    optimization = _runtime_optimization(kernel)
    parent_key = "optimizer-update-parent:contract"

    result = kernel.optimizer_update_boundary.request(
        optimization,
        context=_context(),
        created_at=NOW,
        idempotency_key=parent_key,
    )

    update = result.updates[0]
    assert update.parent_idempotency_key == parent_key
    assert update.idempotency_key is not None
    assert update.idempotency_key.startswith("optimizer-action:")
    assert update.to_dict()["idempotency_key"] == update.idempotency_key
    assert update.to_dict()["parent_idempotency_key"] == parent_key



def test_update_boundary_rejects_reused_parent_key_with_conflicting_actions() -> None:
    kernel = SH3Kernel()
    boundary = kernel.optimizer_update_boundary
    optimization = {
        "optimizer_id": kernel.system_optimizer.optimizer_id,
        "rebalance": {"actions": []},
    }
    boundary.request(
        optimization,
        context=_context(),
        created_at=NOW,
        idempotency_key="optimizer-parent:collision",
    )

    conflicting = {
        "optimizer_id": kernel.system_optimizer.optimizer_id,
        "rebalance": {"actions": ["reduce_context_depth"]},
    }
    with pytest.raises(ValueError, match="conflicting optimization input"):
        boundary.request(
            conflicting,
            context=_context(),
            created_at=NOW,
            idempotency_key="optimizer-parent:collision",
        )


def test_update_boundary_scopes_parent_keys_by_tenant() -> None:
    kernel = SH3Kernel()
    boundary = kernel.optimizer_update_boundary
    optimization = {
        "optimizer_id": kernel.system_optimizer.optimizer_id,
        "rebalance": {"actions": []},
    }
    tenant_a = EventPropagationContext.create(
        correlation_id="collision-tenant-a",
        trace_id="collision-trace-a",
        tenant_id="tenant-a",
    )
    tenant_b = EventPropagationContext.create(
        correlation_id="collision-tenant-b",
        trace_id="collision-trace-b",
        tenant_id="tenant-b",
    )

    first = boundary.request(
        optimization,
        context=tenant_a,
        created_at=NOW,
        idempotency_key="optimizer-parent:tenant-scope",
    )
    second = boundary.request(
        optimization,
        context=tenant_b,
        created_at=NOW,
        idempotency_key="optimizer-parent:tenant-scope",
    )

    assert first.request_id != second.request_id
    assert first.tenant_id == "tenant-a"
    assert second.tenant_id == "tenant-b"
    assert len(boundary.records()) == 2


def test_update_boundary_reports_uncertain_state_after_rollback_failure() -> None:
    class UncertainOptimizer:
        optimizer_id = "optimizer-state-uncertain"

        def execute_actions(
            self,
            actions: list[str] | tuple[str, ...],
            context: Mapping[str, Any] | None = None,
            *,
            rollback_on_failure: bool = True,
        ) -> tuple[OptimizationActionResult, ...]:
            return (
                OptimizationActionResult(
                    action="reduce_context_depth",
                    success=False,
                    result={"changed": True},
                    error="rollback callback failed",
                    state_uncertain=True,
                ),
            )

    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="optimizer-state-uncertain-audit",
            handler=events.append,
            priority=-100,
        )
    )
    optimizer = UncertainOptimizer()
    boundary = OptimizationUpdateBoundary(optimizer, publisher)
    result = boundary.request(
        {
            "optimizer_id": optimizer.optimizer_id,
            "rebalance": {"actions": ["reduce_context_depth"]},
        },
        context=_context(),
        created_at=NOW,
        idempotency_key="optimizer-parent:uncertain",
    )

    failed_event = next(
        event for event in events if event.name == "OptimizationUpdateFailed"
    )
    assert result.success is False
    assert result.changed is True
    assert result.state_uncertain is True
    assert result.to_dict()["state_uncertain"] is True
    assert failed_event.payload["state_uncertain"] is True
    assert not any(event.name == "ContextUpdated" for event in events)
