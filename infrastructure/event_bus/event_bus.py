"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

event_bus.py

Deterministic event bus orchestration.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from threading import RLock
from typing import Final

from ..events.model import Event
from .dead_letter import DeadLetterEntry, DeadLetterQueue, DeadLetterReason
from .delivery import DeliveryReport, EventDelivery
from .queue import EventQueue, QueueItem
from .retry import RetryDecision, RetryManager, RetryPolicy
from .router import EventRouter, EventSubscription

__all__ = [
    "EventBus",
    "EventBusSnapshot",
    "PublishResult",
]


@dataclass(frozen=True, slots=True)
class PublishResult:
    event_id: str
    accepted: bool
    queued: bool
    delivered: bool
    delivery: DeliveryReport | None = None
    retry: RetryDecision | None = None
    dead_lettered: bool = False
    error: str | None = None
    published_at: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be str or None")


@dataclass(frozen=True, slots=True)
class EventBusSnapshot:
    published: int
    accepted: int
    rejected: int
    delivered: int
    failed: int
    retried: int
    dead_lettered: int
    subscriptions: int
    queue_size: int
    dead_letter_size: int
    closed: bool


class EventBus:
    """Thread-safe deterministic event transport coordinator."""

    _UTC: Final[timezone] = UTC

    def __init__(
        self,
        *,
        router: EventRouter | None = None,
        queue: EventQueue | None = None,
        dead_letter: DeadLetterQueue | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._router = router if router is not None else EventRouter()
        self._queue = queue if queue is not None else EventQueue("event_bus")
        self._dead_letter = dead_letter if dead_letter is not None else DeadLetterQueue()
        self._delivery = EventDelivery(self._router)
        self._retry = RetryManager(retry_policy)
        self._lock = RLock()
        self._closed = False
        self._published = 0
        self._accepted = 0
        self._rejected = 0
        self._delivered = 0
        self._failed = 0
        self._retried = 0
        self._dead_lettered = 0

    @property
    def router(self) -> EventRouter:
        return self._router

    @property
    def queue(self) -> EventQueue:
        return self._queue

    @property
    def dead_letter(self) -> DeadLetterQueue:
        return self._dead_letter

    @property
    def delivery(self) -> EventDelivery:
        return self._delivery

    @property
    def retry(self) -> RetryManager:
        return self._retry

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def subscribe(
        self,
        subscription: EventSubscription,
        *,
        replace: bool = False,
    ) -> None:
        self._ensure_open()
        self._router.subscribe(subscription, replace=replace)

    def unsubscribe(
        self,
        subscriber_id: str,
    ) -> EventSubscription:
        self._ensure_open()
        return self._router.unsubscribe(subscriber_id)

    def publish(
        self,
        event: Event,
    ) -> PublishResult:
        self._ensure_open()

        if not isinstance(event, Event):
            raise TypeError("event must be Event")

        event_id = event.id
        published_at = self._timestamp()

        with self._lock:
            self._published += 1

        try:
            self._queue.put(event)
        except Exception as exc:
            with self._lock:
                self._rejected += 1

            dead_lettered = self._store_dead_letter(
                event,
                reason=DeadLetterReason.QUEUE_REJECTED,
                error=f"{type(exc).__name__}: {exc}",
            )

            return PublishResult(
                event_id=event_id,
                accepted=False,
                queued=False,
                delivered=False,
                dead_lettered=dead_lettered,
                error=f"{type(exc).__name__}: {exc}",
                published_at=published_at,
            )

        with self._lock:
            self._accepted += 1

        try:
            item = self._queue.get()
        except IndexError:
            with self._lock:
                self._failed += 1

            return PublishResult(
                event_id=event_id,
                accepted=True,
                queued=False,
                delivered=False,
                error="queued event could not be consumed",
                published_at=published_at,
            )

        report = self._process_item(item)

        if report.failed:
            return self._handle_delivery_failure(
                event,
                report,
                published_at,
            )

        return PublishResult(
            event_id=event_id,
            accepted=True,
            queued=True,
            delivered=report.succeeded,
            delivery=report,
            published_at=published_at,
        )

    def publish_many(
        self,
        events: tuple[Event, ...],
    ) -> tuple[PublishResult, ...]:
        if not isinstance(events, tuple):
            raise TypeError("events must be tuple")

        return tuple(self.publish(event) for event in events)

    def process(
        self,
        *,
        limit: int | None = None,
    ) -> tuple[DeliveryReport, ...]:
        self._ensure_open()

        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")

        reports: list[DeliveryReport] = []
        count = 0

        while limit is None or count < limit:
            try:
                item = self._queue.get()
            except IndexError:
                break

            report = self._process_item(item)
            reports.append(report)

            if report.failed:
                self._handle_delivery_failure(
                    item.event,
                    report,
                    self._timestamp(),
                )

            count += 1

        return tuple(reports)

    def process_one(self) -> DeliveryReport | None:
        self._ensure_open()

        try:
            item = self._queue.get()
        except IndexError:
            return None

        report = self._process_item(item)

        if report.failed:
            self._handle_delivery_failure(
                item.event,
                report,
                self._timestamp(),
            )

        return report

    def retry_event(
        self,
        event: Event,
        *,
        key: Hashable | None = None,
    ) -> PublishResult:
        self._ensure_open()

        if not isinstance(event, Event):
            raise TypeError("event must be Event")

        retry_key = event.id if key is None else key
        state = self._retry.state(retry_key)

        if state.attempts == 0 or not self._retry.should_retry(retry_key):
            return PublishResult(
                event_id=event.id,
                accepted=False,
                queued=False,
                delivered=False,
                error="retry not available",
                published_at=self._timestamp(),
            )

        return self.publish(event)

    def record_failure(
        self,
        key: Hashable,
        error: BaseException,
    ) -> RetryDecision:
        decision = self._retry.record_failure(key, error)

        with self._lock:
            if decision.retry:
                self._retried += 1

        return decision

    def record_success(
        self,
        key: Hashable,
    ) -> None:
        self._retry.record_success(key)

    def dead_letters(self) -> tuple[DeadLetterEntry, ...]:
        return self._dead_letter.entries()

    def release_dead_letter(self) -> DeadLetterEntry:
        return self._dead_letter.get()

    def snapshot(self) -> EventBusSnapshot:
        queue_snapshot = self._queue.snapshot()
        dead_letter_snapshot = self._dead_letter.snapshot()

        with self._lock:
            return EventBusSnapshot(
                published=self._published,
                accepted=self._accepted,
                rejected=self._rejected,
                delivered=self._delivered,
                failed=self._failed,
                retried=self._retried,
                dead_lettered=self._dead_lettered,
                subscriptions=self._router.count(),
                queue_size=queue_snapshot.size,
                dead_letter_size=dead_letter_snapshot.size,
                closed=self._closed,
            )

    def size(self) -> int:
        return self._queue.size()

    def empty(self) -> bool:
        return self._queue.empty()

    def dead_letter_size(self) -> int:
        return self._dead_letter.size()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True

        self._queue.close()

    def clear(self) -> None:
        self._queue.clear()

    def clear_dead_letters(self) -> tuple[DeadLetterEntry, ...]:
        return self._dead_letter.clear()

    def reset_metrics(self) -> None:
        self._queue.clear()
        self._retry.clear()

        with self._lock:
            self._published = 0
            self._accepted = 0
            self._rejected = 0
            self._delivered = 0
            self._failed = 0
            self._retried = 0
            self._dead_lettered = 0

    def _process_item(
        self,
        item: QueueItem,
    ) -> DeliveryReport:
        report = self._delivery.deliver(item.event)

        with self._lock:
            self._delivered += report.successful
            self._failed += report.failed

        return report

    def _handle_delivery_failure(
        self,
        event: Event,
        report: DeliveryReport,
        published_at: str,
    ) -> PublishResult:
        failed_result = next(
            (result for result in report.results if result.failed),
            None,
        )

        if failed_result is None:
            return PublishResult(
                event_id=event.id,
                accepted=True,
                queued=True,
                delivered=False,
                delivery=report,
                published_at=published_at,
            )

        error = failed_result.error or "delivery failed"

        decision = self.record_failure(
            self._retry_key(
                event,
                failed_result.subscriber_id,
            ),
            RuntimeError(error),
        )

        if decision.retry:
            return PublishResult(
                event_id=event.id,
                accepted=True,
                queued=True,
                delivered=False,
                delivery=report,
                retry=decision,
                published_at=published_at,
            )

        dead_lettered = self._store_dead_letter(
            event,
            reason=DeadLetterReason.RETRY_EXHAUSTED,
            error=error,
            subscriber_id=failed_result.subscriber_id,
        )

        return PublishResult(
            event_id=event.id,
            accepted=True,
            queued=True,
            delivered=False,
            delivery=report,
            retry=decision,
            dead_lettered=dead_lettered,
            error=error,
            published_at=published_at,
        )

    def _store_dead_letter(
        self,
        event: Event,
        *,
        reason: str,
        error: str | None = None,
        subscriber_id: str | None = None,
    ) -> bool:
        try:
            self._dead_letter.put(
                event,
                reason=reason,
                error=error,
                subscriber_id=subscriber_id,
            )
        except Exception:
            return False

        with self._lock:
            self._dead_lettered += 1

        return True

    @staticmethod
    def _retry_key(
        event: Event,
        subscriber_id: str,
    ) -> tuple[str, str]:
        return event.id, subscriber_id

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("event bus is closed")

    @classmethod
    def _timestamp(cls) -> str:
        return datetime.now(cls._UTC).isoformat()
