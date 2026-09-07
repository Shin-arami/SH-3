"""
SH-3 Complete Edition v2.0
Infrastructure Layer
Events Subsystem

delivery.py

Deterministic event delivery execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from threading import RLock
from typing import Final

from ..events.model import Event
from .router import EventRouter, RouteTarget

__all__ = [
    "DeliveryReport",
    "DeliveryResult",
    "DeliveryStatus",
    "EventDelivery",
]


class DeliveryStatus:
    PENDING: Final[str] = "pending"
    SUCCESS: Final[str] = "success"
    FAILED: Final[str] = "failed"
    SKIPPED: Final[str] = "skipped"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    event_id: str
    subscriber_id: str
    status: str
    started_at: str
    completed_at: str
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if not self.subscriber_id:
            raise ValueError("subscriber_id must not be empty")
        if self.status not in {
            DeliveryStatus.PENDING,
            DeliveryStatus.SUCCESS,
            DeliveryStatus.FAILED,
            DeliveryStatus.SKIPPED,
        }:
            raise ValueError(f"invalid delivery status: {self.status}")

        if self.status == DeliveryStatus.FAILED and not self.error:
            raise ValueError("failed delivery must contain error")

        if self.status != DeliveryStatus.FAILED and self.error is not None:
            raise ValueError("non-failed delivery must not contain error")

    @property
    def successful(self) -> bool:
        return self.status == DeliveryStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status == DeliveryStatus.FAILED

    @property
    def skipped(self) -> bool:
        return self.status == DeliveryStatus.SKIPPED


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    event_id: str
    results: tuple[DeliveryResult, ...]

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must not be empty")

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def successful(self) -> int:
        return sum(result.successful for result in self.results)

    @property
    def failed(self) -> int:
        return sum(result.failed for result in self.results)

    @property
    def skipped(self) -> int:
        return sum(result.skipped for result in self.results)

    @property
    def completed(self) -> bool:
        return all(
            result.status
            in {
                DeliveryStatus.SUCCESS,
                DeliveryStatus.FAILED,
                DeliveryStatus.SKIPPED,
            }
            for result in self.results
        )

    @property
    def succeeded(self) -> bool:
        return self.total > 0 and self.failed == 0

    @property
    def empty(self) -> bool:
        return self.total == 0


class EventDelivery:
    """Thread-safe execution layer for routed event targets."""

    _UTC: Final[timezone] = UTC

    def __init__(
        self,
        router: EventRouter,
    ) -> None:
        if not isinstance(router, EventRouter):
            raise TypeError("router must be EventRouter")

        self._router = router
        self._lock = RLock()

    def deliver(
        self,
        event: Event,
    ) -> DeliveryReport:
        targets = self._router.route(event)
        return self.deliver_targets(event, targets)

    def deliver_targets(
        self,
        event: Event,
        targets: tuple[RouteTarget, ...],
    ) -> DeliveryReport:
        if not targets:
            return DeliveryReport(
                event_id=event.id,
                results=(),
            )

        results: list[DeliveryResult] = []

        for target in targets:
            results.append(
                self._deliver_target(
                    event,
                    target,
                )
            )

        return DeliveryReport(
            event_id=event.id,
            results=tuple(results),
        )

    def deliver_target(
        self,
        event: Event,
        target: RouteTarget,
    ) -> DeliveryResult:
        return self._deliver_target(
            event,
            target,
        )

    def _deliver_target(
        self,
        event: Event,
        target: RouteTarget,
    ) -> DeliveryResult:
        started_at = self._timestamp()

        try:
            target.handler(event)
        except Exception as exc:
            completed_at = self._timestamp()

            return DeliveryResult(
                event_id=event.id,
                subscriber_id=target.subscriber_id,
                status=DeliveryStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                error=f"{type(exc).__name__}: {exc}",
            )

        completed_at = self._timestamp()

        return DeliveryResult(
            event_id=event.id,
            subscriber_id=target.subscriber_id,
            status=DeliveryStatus.SUCCESS,
            started_at=started_at,
            completed_at=completed_at,
        )

    def route_and_deliver(
        self,
        event: Event,
    ) -> DeliveryReport:
        return self.deliver(event)

    @classmethod
    def _timestamp(cls) -> str:
        return datetime.now(cls._UTC).isoformat()
