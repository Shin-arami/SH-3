"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Event Bus Subsystem

publisher.py

Typed event publication boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from ..events.model import Event
from .event_bus import EventBus, PublishResult

__all__ = [
    "EventBusPublisher",
    "EventPublisher",
    "EventSink",
]


@runtime_checkable
class EventPublisher(Protocol):
    """Typed boundary for publishing immutable SH-3 events."""

    def publish(self, event: Event) -> PublishResult:
        """Publish an event and return its transport result."""
        ...


EventSink = Callable[[Event], PublishResult]


class EventBusPublisher:
    """EventPublisher adapter backed by an EventBus instance."""

    __slots__ = ("_event_bus",)

    def __init__(self, event_bus: EventBus) -> None:
        if not isinstance(event_bus, EventBus):
            raise TypeError("event_bus must be EventBus")
        self._event_bus = event_bus

    @property
    def event_bus(self) -> EventBus:
        """Return the wrapped EventBus."""
        return self._event_bus

    def publish(self, event: Event) -> PublishResult:
        """Publish an event through the wrapped EventBus."""
        return self._event_bus.publish(event)

    def as_sink(self) -> EventSink:
        """Return the publisher as a callable event sink."""
        return self.publish
