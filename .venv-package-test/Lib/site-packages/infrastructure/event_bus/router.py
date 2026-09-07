"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

router.py

Deterministic event routing and subscription management.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Final

from foundation.Enums.event import EventType
from foundation.Enums.priority import Priority

from ..events.model import Event
from ..events.validator import EventValidator

__all__ = [
    "EventRouter",
    "EventSubscription",
    "RouteTarget",
]


EventHandler = Callable[[Event], None]


@dataclass(frozen=True, slots=True)
class EventSubscription:
    subscriber_id: str
    handler: EventHandler
    event_name: str | None = None
    event_type: EventType | None = None
    event_version: str | None = None
    min_priority: Priority | None = None
    producer: str | None = None
    tags: tuple[tuple[str, str], ...] = ()
    enabled: bool = True
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.subscriber_id:
            raise ValueError("subscriber_id must not be empty")
        if not callable(self.handler):
            raise TypeError("handler must be callable")
        if self.event_name is not None and not self.event_name:
            raise ValueError("event_name must not be empty")
        if self.event_version is not None and not self.event_version:
            raise ValueError("event_version must not be empty")
        if self.producer is not None and not self.producer:
            raise ValueError("producer must not be empty")
        if self.min_priority is not None and not isinstance(
            self.min_priority,
            Priority,
        ):
            raise TypeError("min_priority must be Priority")
        if not isinstance(self.priority, int):
            raise TypeError("priority must be int")
        for key, value in self.tags:
            if not isinstance(key, str) or not key:
                raise TypeError("tag keys must be non-empty strings")
            if not isinstance(value, str):
                raise TypeError("tag values must be strings")

    @property
    def tag_map(self) -> dict[str, str]:
        return dict(self.tags)

    def matches(self, event: Event) -> bool:
        if not self.enabled:
            return False
        if self.event_name is not None and event.name != self.event_name:
            return False
        if self.event_type is not None and event.event_type is not self.event_type:
            return False
        if self.event_version is not None and event.version != self.event_version:
            return False
        if self.min_priority is not None and event.priority < self.min_priority:
            return False
        if self.producer is not None and event.metadata.producer != self.producer:
            return False

        event_tags = event.metadata.tags
        return all(event_tags.get(key) == value for key, value in self.tags)


@dataclass(frozen=True, slots=True)
class RouteTarget:
    subscriber_id: str
    handler: EventHandler
    priority: int

    def __post_init__(self) -> None:
        if not self.subscriber_id:
            raise ValueError("subscriber_id must not be empty")
        if not callable(self.handler):
            raise TypeError("handler must be callable")


class EventRouter:
    """Thread-safe deterministic subscription router."""

    _DEFAULT_SUBSCRIPTION_PRIORITY: Final[int] = 0

    def __init__(self) -> None:
        self._subscriptions: dict[str, EventSubscription] = {}
        self._lock = RLock()

    def subscribe(
        self,
        subscription: EventSubscription,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(subscription, EventSubscription):
            raise TypeError("subscription must be EventSubscription")

        with self._lock:
            if subscription.subscriber_id in self._subscriptions and not replace:
                raise ValueError(f"subscriber already registered: {subscription.subscriber_id}")

            self._subscriptions[subscription.subscriber_id] = subscription

    def unsubscribe(
        self,
        subscriber_id: str,
    ) -> EventSubscription:
        if not subscriber_id:
            raise ValueError("subscriber_id must not be empty")

        with self._lock:
            try:
                return self._subscriptions.pop(subscriber_id)
            except KeyError as exc:
                raise KeyError(f"subscriber not registered: {subscriber_id}") from exc

    def enable(
        self,
        subscriber_id: str,
    ) -> None:
        self._set_enabled(subscriber_id, True)

    def disable(
        self,
        subscriber_id: str,
    ) -> None:
        self._set_enabled(subscriber_id, False)

    def route(
        self,
        event: Event,
    ) -> tuple[RouteTarget, ...]:
        EventValidator.validate(event)

        with self._lock:
            subscriptions = tuple(self._subscriptions.values())

        targets = [
            RouteTarget(
                subscriber_id=subscription.subscriber_id,
                handler=subscription.handler,
                priority=subscription.priority,
            )
            for subscription in subscriptions
            if subscription.matches(event)
        ]

        targets.sort(
            key=lambda target: (
                -target.priority,
                target.subscriber_id,
            )
        )

        return tuple(targets)

    def subscribers(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[EventSubscription, ...]:
        with self._lock:
            subscriptions = tuple(self._subscriptions.values())

        if enabled_only:
            subscriptions = tuple(
                subscription for subscription in subscriptions if subscription.enabled
            )

        return tuple(
            sorted(
                subscriptions,
                key=lambda subscription: subscription.subscriber_id,
            )
        )

    def contains(
        self,
        subscriber_id: str,
    ) -> bool:
        with self._lock:
            return subscriber_id in self._subscriptions

    def count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def clear(self) -> None:
        with self._lock:
            self._subscriptions.clear()

    def _set_enabled(
        self,
        subscriber_id: str,
        enabled: bool,
    ) -> None:
        with self._lock:
            subscription = self._subscriptions.get(subscriber_id)

            if subscription is None:
                raise KeyError(f"subscriber not registered: {subscriber_id}")

            self._subscriptions[subscriber_id] = EventSubscription(
                subscriber_id=subscription.subscriber_id,
                handler=subscription.handler,
                event_name=subscription.event_name,
                event_type=subscription.event_type,
                event_version=subscription.event_version,
                min_priority=subscription.min_priority,
                producer=subscription.producer,
                tags=subscription.tags,
                enabled=enabled,
                priority=subscription.priority,
            )
