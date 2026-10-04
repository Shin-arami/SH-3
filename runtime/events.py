from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from foundation.Enums import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus.publisher import EventPublisher
from infrastructure.events import Event, EventPropagationContext

__all__ = ["publish_runtime_event"]


def publish_runtime_event(
    publisher: EventPublisher | None,
    *,
    event_name: str,
    producer: str,
    payload: Mapping[str, Any],
    event_type: EventType,
    context: EventPropagationContext,
) -> str | None:
    if publisher is None:
        return None

    event = Event.create(
        event_name=event_name,
        producer=producer,
        payload=dict(payload),
        category=Category.RUNTIME,
        event_type=event_type,
        correlation_id=context.correlation_id,
        causation_id=context.causation_id,
        trace_id=context.trace_id,
        tenant_id=context.tenant_id,
    )
    publisher.publish(event)
    return event.metadata.event_id
