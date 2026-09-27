from __future__ import annotations

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.core import SH3Kernel


def _build_bus() -> tuple[EventBus, EventBusPublisher, list[Event]]:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []

    bus.subscribe(
        EventSubscription(
            subscriber_id="p1-3-audit",
            handler=events.append,
            priority=1000,
        ),
    )
    return bus, publisher, events


def _event_names(events: list[Event]) -> list[str]:
    return [event.name for event in events]


def _assert_propagation_chain(events: list[Event]) -> None:
    assert events
    correlation_ids = {event.metadata.correlation_id for event in events}
    trace_ids = {event.metadata.trace_id for event in events}
    assert len(correlation_ids) == 1
    assert len(trace_ids) == 1

    by_name = {event.name: event for event in events}
    event_ids = [event.metadata.event_id for event in events]
    assert len(event_ids) == len(set(event_ids))

    assert by_name["FailureDetected"].metadata.causation_id is None
    assert by_name["RecoveryPlanned"].metadata.causation_id == by_name["FailureDetected"].metadata.event_id
    assert by_name["RecoveryStarted"].metadata.causation_id == by_name["RecoveryPlanned"].metadata.event_id
    assert by_name["HealingFeedbackRecorded"].metadata.causation_id == by_name["RecoveryStarted"].metadata.event_id
    assert by_name["LearningRecordCreated"].metadata.causation_id == by_name["HealingFeedbackRecorded"].metadata.event_id
    assert by_name["LearningResultRecorded"].metadata.causation_id == by_name["LearningRecordCreated"].metadata.event_id
    assert by_name["RecoveryCompleted"].metadata.causation_id == by_name["HealingFeedbackRecorded"].metadata.event_id


def _find_event(events: list[Event], name: str) -> Event:
    for event in events:
        if event.name == name:
            return event
    raise AssertionError(f"event not found: {name}")


def test_p1_3_self_healing_event_bus_learning_e2e() -> None:
    bus, publisher, events = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    healing_events: list[Event] = []

    bus.subscribe(
        EventSubscription(
            subscriber_id="p1-3-healing-audit",
            handler=healing_events.append,
            event_name="HealingFeedbackRecorded",
            priority=-50,
        ),
    )

    context = EventPropagationContext.create(
        correlation_id="p1-3-correlation",
        trace_id="p1-3-trace",
        tenant_id="p1-3-tenant",
    )

    healer = kernel.meta_controller.healer
    healer.set_propagation_context(context)

    snapshot = healer.detect(
        RuntimeError("p1-3 failure"),
        {"component": "p1-3"},
    )
    plan = healer.plan_recovery(snapshot)

    result = healer.recover(snapshot, plan)

    assert result is not None

    names = _event_names(events)

    assert "FailureDetected" in names
    assert "RecoveryPlanned" in names
    assert "RecoveryStarted" in names
    assert "HealingFeedbackRecorded" in names
    assert "LearningRecordCreated" in names
    assert "LearningResultRecorded" in names
    assert "RecoveryCompleted" in names

    feedback_index = names.index("HealingFeedbackRecorded")
    learning_created_index = names.index("LearningRecordCreated")
    learning_result_index = names.index("LearningResultRecorded")
    completed_index = names.index("RecoveryCompleted")

    assert feedback_index < learning_created_index
    assert learning_created_index < learning_result_index
    assert learning_result_index < completed_index

    assert healing_events
    feedback = healing_events[-1]

    assert feedback.name == "HealingFeedbackRecorded"
    assert feedback.category is Category.LEARNING
    assert feedback.event_type is EventType.CREATED

    records = kernel.learning_loop.records()
    assert records

    recovery_records = tuple(
        record
        for record in records
        if record["domain"] == "self_healing.recovery"
    )
    assert recovery_records

    record = recovery_records[-1]
    assert record["success"] is True
    assert record["score"] == 1.0

    _assert_propagation_chain(events)

    assert feedback.metadata.correlation_id == context.correlation_id
    assert feedback.metadata.trace_id == context.trace_id
    assert feedback.metadata.tenant_id == context.tenant_id


def test_p1_3_event_causation_chain_is_contiguous() -> None:
    _, publisher, events = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="p1-3-chain",
        trace_id="p1-3-chain-trace",
    )

    healer = kernel.meta_controller.healer
    healer.set_propagation_context(context)

    snapshot = healer.detect(RuntimeError("chain failure"), {})
    plan = healer.plan_recovery(snapshot)
    healer.recover(snapshot, plan)

    relevant = [
        event
        for event in events
        if event.name
        in {
            "FailureDetected",
            "RecoveryPlanned",
            "RecoveryStarted",
            "HealingFeedbackRecorded",
            "LearningRecordCreated",
            "LearningResultRecorded",
            "RecoveryCompleted",
        }
    ]

    assert len(relevant) >= 7

    by_name = {event.name: event for event in relevant}
    assert by_name["RecoveryPlanned"].metadata.causation_id == by_name["FailureDetected"].metadata.event_id
    assert by_name["RecoveryStarted"].metadata.causation_id == by_name["RecoveryPlanned"].metadata.event_id
    assert by_name["HealingFeedbackRecorded"].metadata.causation_id == by_name["RecoveryStarted"].metadata.event_id
    assert by_name["LearningRecordCreated"].metadata.causation_id == by_name["HealingFeedbackRecorded"].metadata.event_id
    assert by_name["LearningResultRecorded"].metadata.causation_id == by_name["LearningRecordCreated"].metadata.event_id
    assert by_name["RecoveryCompleted"].metadata.causation_id == by_name["HealingFeedbackRecorded"].metadata.event_id


def test_p1_3_healing_feedback_reaches_learning_without_direct_reference() -> None:
    _, publisher, _ = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    healer = kernel.meta_controller.healer

    assert healer.learning is None

    context = EventPropagationContext.create(
        correlation_id="p1-3-no-direct-learning",
        trace_id="p1-3-no-direct-learning-trace",
    )
    healer.set_propagation_context(context)

    snapshot = healer.detect(RuntimeError("isolated failure"), {})
    plan = healer.plan_recovery(snapshot)
    healer.recover(snapshot, plan)

    records = kernel.learning_loop.records()

    assert any(
        record["domain"] == "self_healing.recovery"
        for record in records
    )


def test_p1_3_learning_subscription_is_registered() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    kernel = SH3Kernel(event_publisher=publisher)

    subscription = next(
        subscription
        for subscription in bus.router.subscribers()
        if subscription.subscriber_id == kernel.learning_loop.loop_id
    )

    assert subscription.event_name == "HealingFeedbackRecorded"
    assert subscription.enabled is True


def test_p1_3_publisher_replacement_rebinds_learning_subscription() -> None:
    first_bus = EventBus()
    first_publisher = EventBusPublisher(first_bus)
    second_bus = EventBus()
    second_publisher = EventBusPublisher(second_bus)

    kernel = SH3Kernel(event_publisher=first_publisher)
    loop_id = kernel.learning_loop.loop_id

    assert first_bus.router.contains(loop_id)

    kernel.set_event_publisher(second_publisher)

    assert not first_bus.router.contains(loop_id)
    assert second_bus.router.contains(loop_id)

    subscription = next(
        subscription
        for subscription in second_bus.router.subscribers()
        if subscription.subscriber_id == loop_id
    )

    assert subscription.event_name == "HealingFeedbackRecorded"


def test_p1_3_learning_failure_isolated_from_self_healing() -> None:
    bus, publisher, events = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    loop = kernel.learning_loop

    def failing_handler(event: Event) -> None:
        if event.name == "HealingFeedbackRecorded":
            raise RuntimeError("learning consumer failure")

    bus.subscribe(
        EventSubscription(
            subscriber_id="p1-3-failing-learning-consumer",
            handler=failing_handler,
            event_name="HealingFeedbackRecorded",
            priority=200,
        ),
    )

    context = EventPropagationContext.create(
        correlation_id="p1-3-failure-isolation",
        trace_id="p1-3-failure-isolation-trace",
    )

    kernel.meta_controller.healer.set_propagation_context(context)

    snapshot = kernel.meta_controller.healer.detect(
        RuntimeError("failure-isolation"),
        {},
    )
    plan = kernel.meta_controller.healer.plan_recovery(snapshot)

    result = kernel.meta_controller.healer.recover(snapshot, plan)

    assert result is not None
    assert any(event.name == "HealingFeedbackRecorded" for event in events)

    assert loop.records()
    assert any(
        record["domain"] == "self_healing.recovery"
        for record in loop.records()
    )
    assert bus.snapshot().failed >= 1


def test_p1_3_event_versions_are_canonical() -> None:
    _, publisher, events = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="p1-3-version",
        trace_id="p1-3-version-trace",
    )
    kernel.meta_controller.healer.set_propagation_context(context)

    snapshot = kernel.meta_controller.healer.detect(
        RuntimeError("version-check"),
        {},
    )
    plan = kernel.meta_controller.healer.plan_recovery(snapshot)
    kernel.meta_controller.healer.recover(snapshot, plan)

    relevant = [
        event
        for event in events
        if event.name
        in {
            "FailureDetected",
            "RecoveryPlanned",
            "RecoveryStarted",
            "HealingFeedbackRecorded",
            "LearningRecordCreated",
            "LearningResultRecorded",
            "RecoveryCompleted",
        }
    ]

    assert relevant

    for event in relevant:
        assert event.metadata.event_version == "1.0.0"


@pytest.mark.parametrize(
    ("event_name", "category", "event_type"),
    (
        ("FailureDetected", Category.ACTION, EventType.FAILURE),
        ("RecoveryPlanned", Category.ACTION, EventType.CREATED),
        ("RecoveryStarted", Category.ACTION, EventType.START),
        ("HealingFeedbackRecorded", Category.LEARNING, EventType.CREATED),
        ("LearningRecordCreated", Category.LEARNING, EventType.CREATED),
        ("LearningResultRecorded", Category.LEARNING, EventType.CREATED),
        ("RecoveryCompleted", Category.ACTION, EventType.COMPLETE),
    ),
)
def test_p1_3_event_contract(
    event_name: str,
    category: Category,
    event_type: EventType,
) -> None:
    _, publisher, events = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="p1-3-contract",
        trace_id="p1-3-contract-trace",
        tenant_id="p1-3-contract-tenant",
    )
    kernel.meta_controller.healer.set_propagation_context(context)

    snapshot = kernel.meta_controller.healer.detect(
        RuntimeError("contract"),
        {},
    )
    plan = kernel.meta_controller.healer.plan_recovery(snapshot)
    kernel.meta_controller.healer.recover(snapshot, plan)

    event = _find_event(events, event_name)

    assert event.category is category
    assert event.event_type is event_type
    assert event.metadata.correlation_id == context.correlation_id
    assert event.metadata.trace_id == context.trace_id
    assert event.metadata.tenant_id == context.tenant_id


def test_p1_3_learning_record_is_immutable_from_external_collection() -> None:
    _, publisher, _ = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="p1-3-record-copy",
        trace_id="p1-3-record-copy-trace",
    )
    kernel.meta_controller.healer.set_propagation_context(context)

    snapshot = kernel.meta_controller.healer.detect(
        RuntimeError("record-copy"),
        {},
    )
    plan = kernel.meta_controller.healer.plan_recovery(snapshot)
    kernel.meta_controller.healer.recover(snapshot, plan)

    records = kernel.learning_loop.records()
    assert records

    original = records[-1]
    details = original["details"]
    details["mutated"] = True

    fresh = kernel.learning_loop.records()[-1]
    assert "mutated" not in fresh["details"]


def test_p1_3_event_bus_snapshot_records_delivery() -> None:
    bus, publisher, _ = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="p1-3-metrics",
        trace_id="p1-3-metrics-trace",
    )
    kernel.meta_controller.healer.set_propagation_context(context)

    snapshot = kernel.meta_controller.healer.detect(
        RuntimeError("metrics"),
        {},
    )
    plan = kernel.meta_controller.healer.plan_recovery(snapshot)
    kernel.meta_controller.healer.recover(snapshot, plan)

    bus_snapshot = bus.snapshot()

    assert bus_snapshot.published >= 7
    assert bus_snapshot.accepted >= 7
    assert bus_snapshot.delivered >= 7
    assert bus_snapshot.failed == 0


def test_p1_3_full_required_event_order() -> None:
    _, publisher, events = _build_bus()
    kernel = SH3Kernel(event_publisher=publisher)

    context = EventPropagationContext.create(
        correlation_id="p1-3-order",
        trace_id="p1-3-order-trace",
    )
    kernel.meta_controller.healer.set_propagation_context(context)

    snapshot = kernel.meta_controller.healer.detect(
        RuntimeError("order"),
        {},
    )
    plan = kernel.meta_controller.healer.plan_recovery(snapshot)
    kernel.meta_controller.healer.recover(snapshot, plan)

    names = _event_names(events)

    required = [
        "FailureDetected",
        "RecoveryPlanned",
        "RecoveryStarted",
        "HealingFeedbackRecorded",
        "LearningRecordCreated",
        "LearningResultRecorded",
        "RecoveryCompleted",
    ]

    positions = [names.index(name) for name in required]

    assert positions == sorted(positions)
