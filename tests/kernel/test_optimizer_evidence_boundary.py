from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from cognition.policy import PolicyRule
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel import SH3Kernel
from kernel.optimizer_evidence_boundary import OptimizationEvidenceBoundary
from kernel.optimizer_update_boundary import OptimizationUpdateKind

NOW = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="evidence-correlation",
        causation_id="evidence-cause",
        trace_id="evidence-trace",
        tenant_id="evidence-tenant",
    )


def _runtime_optimization(kernel: SH3Kernel) -> dict[str, object]:
    for index in range(7):
        kernel.context_manager.push(f"ctx-{index}")
    return kernel.system_optimizer.optimize(context=_context(), execute=False)


def test_kernel_owns_optimizer_evidence_boundary() -> None:
    kernel = SH3Kernel()
    assert isinstance(kernel.optimizer_evidence_boundary, OptimizationEvidenceBoundary)
    assert kernel.optimizer_evidence_boundary.evidence_store.records() == ()
    assert kernel.optimizer_update_boundary.evidence_boundary is kernel.optimizer_evidence_boundary


def test_material_runtime_update_is_recorded_as_integrity_protected_evidence() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="optimizer-evidence-canonical", handler=events.append, priority=-100))
    kernel = SH3Kernel(event_publisher=publisher)
    optimization = _runtime_optimization(kernel)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    outcome = kernel.optimizer_evidence_boundary.get(update.request_id)
    assert outcome is not None
    assert outcome.recorded is True
    assert outcome.evidence is not None
    evidence = outcome.evidence
    assert evidence.kind == "optimization"
    assert evidence.source == "optimizer"
    assert evidence.subject_id == update.request_id
    assert evidence.trace_id == update.trace_id
    assert evidence.verify()
    assert kernel.optimizer_evidence_boundary.evidence_store.verify(evidence.evidence_id)
    assert evidence.payload["material_changes"] == 1
    assert evidence.payload["updates"][0]["target"] == OptimizationUpdateKind.RUNTIME.value


def test_material_policy_update_is_recorded() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel(event_publisher=publisher)
    for index in range(10):
        kernel.policy.add_rule(PolicyRule(f"rule-{index}"))
    optimization = kernel.system_optimizer.optimize(context=_context(), execute=False)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    outcome = kernel.optimizer_evidence_boundary.get(update.request_id)
    assert outcome is not None and outcome.recorded and outcome.evidence is not None
    assert outcome.evidence.payload["updates"][0]["target"] == OptimizationUpdateKind.POLICY.value


def test_non_material_update_does_not_create_evidence() -> None:
    kernel = SH3Kernel()
    optimization = kernel.system_optimizer.optimize(context=_context(), execute=False)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    outcome = kernel.optimizer_evidence_boundary.record(update, context=_context(), created_at=NOW)
    assert outcome is not None
    assert outcome.recorded is False
    assert outcome.evidence is None
    assert outcome.metadata["material_changes"] == 0
    assert kernel.optimizer_evidence_boundary.evidence_store.records() == ()


def test_evidence_record_event_preserves_trace_and_causation_chain() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="optimizer-evidence-test", handler=events.append, priority=-100))
    kernel = SH3Kernel(event_publisher=publisher)
    optimization = _runtime_optimization(kernel)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    recorded = next(event for event in events if event.name == "OptimizationEvidenceRecorded")
    completion = next(event for event in events if event.name == "OptimizationUpdateCompleted")
    assert recorded.category is Category.ACTION
    assert recorded.event_type is EventType.CREATED
    assert recorded.metadata.correlation_id == completion.metadata.correlation_id
    assert recorded.metadata.trace_id == completion.metadata.trace_id
    assert recorded.metadata.tenant_id == completion.metadata.tenant_id
    assert recorded.causation_id == completion.id
    assert recorded.payload["request_id"] == update.request_id


def test_evidence_is_idempotent_for_duplicate_result() -> None:
    kernel = SH3Kernel()
    optimization = _runtime_optimization(kernel)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)

    first = kernel.optimizer_evidence_boundary.record(update, context=_context(), created_at=NOW)
    second = kernel.optimizer_evidence_boundary.record(update, context=_context(), created_at=NOW)

    assert first is second
    assert len(kernel.optimizer_evidence_boundary.records()) == 1
    assert len(kernel.optimizer_evidence_boundary.evidence_store.records()) == 1


def test_concurrent_evidence_recording_is_idempotent() -> None:
    kernel = SH3Kernel()
    optimization = _runtime_optimization(kernel)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)
    boundary = kernel.optimizer_evidence_boundary

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(
            executor.map(
                lambda _: boundary.record(update, context=_context(), created_at=NOW),
                range(8),
            )
        )

    assert len({item.request_id for item in results}) == 1
    assert len(boundary.evidence_store.records()) == 1


def test_publisher_replacement_rebinds_evidence_subscription() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    first_publisher = EventBusPublisher(first_bus)
    second_publisher = EventBusPublisher(second_bus)
    boundary = OptimizationEvidenceBoundary(event_publisher=first_publisher)

    assert first_bus.router.contains("optimizer.evidence-boundary")
    boundary.set_event_publisher(second_publisher)
    assert not first_bus.router.contains("optimizer.evidence-boundary")
    assert second_bus.router.contains("optimizer.evidence-boundary")


def test_evidence_version_and_payload_are_canonical() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="optimizer-evidence-canonical",
            handler=events.append,
            priority=-100,
        ),
    )
    kernel = SH3Kernel(event_publisher=publisher)
    optimization = _runtime_optimization(kernel)
    update = kernel.optimizer_update_boundary.request(optimization, context=_context(), created_at=NOW)
    outcome = kernel.optimizer_evidence_boundary.get(update.request_id)

    assert outcome is not None and outcome.evidence is not None
    evidence = outcome.evidence
    completion = next(event for event in events if event.name == "OptimizationUpdateCompleted")
    assert evidence.version == "1.0.0"
    assert evidence.payload["correlation_id"] == completion.correlation_id
    assert evidence.payload["causation_id"] == completion.id
    assert evidence.payload["trace_id"] == completion.trace_id
    assert evidence.payload["tenant_id"] == completion.metadata.tenant_id


def test_direct_record_rejects_wrong_result_type() -> None:
    kernel = SH3Kernel()
    try:
        kernel.optimizer_evidence_boundary.record(object())  # type: ignore[arg-type]
    except TypeError as exc:
        assert str(exc) == "result must be OptimizationUpdateResult"
    else:
        raise AssertionError("expected TypeError")
