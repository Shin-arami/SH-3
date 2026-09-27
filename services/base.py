from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock
from typing import Any

from foundation.enums import LifecycleState, Severity
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.exceptions import SH3Exception
from foundation.utils.logging import error, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events import Event, EventPropagationContext

from .health import HealthState, HealthStatus

__all__ = ["Service", "ServiceException"]


class ServiceException(SH3Exception):
    """Service lifecycle or execution failure."""


class Service(ABC):
    __slots__ = ("_event_publisher", "_lock", "_propagation_context", "_state", "name")

    def __init__(
        self,
        name: str,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must implement EventPublisher")
        self.name = name
        self._state = LifecycleState.CREATED
        self._lock = RLock()
        self._event_publisher = event_publisher
        self._propagation_context: EventPropagationContext | None = None

    @property
    def state(self) -> LifecycleState:
        with self._lock:
            return self._state

    @property
    def active(self) -> bool:
        return self.state == LifecycleState.ACTIVE

    @property
    def suspended(self) -> bool:
        return self.state == LifecycleState.SUSPENDED

    @property
    def terminated(self) -> bool:
        return self.state == LifecycleState.TERMINATED

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        with self._lock:
            return self._propagation_context

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must implement EventPublisher")
        with self._lock:
            self._event_publisher = publisher

    def set_propagation_context(self, context: EventPropagationContext | None) -> None:
        if context is not None and not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext or None")
        with self._lock:
            self._propagation_context = context

    def start(self, *, context: EventPropagationContext | None = None) -> None:
        with self._lock:
            if self._state != LifecycleState.CREATED:
                raise ServiceException(
                    f"Cannot start service '{self.name}' from state {self._state.value}"
                )
            self._set_propagation_context(context)
            try:
                self._on_start()
                self._state = LifecycleState.ACTIVE
                self._publish_lifecycle(
                    "ServiceStarted",
                    EventType.START,
                    context=self._propagation_context,
                )
                info(
                    "Service started",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                self._publish_failure("start", exc, context=self._propagation_context)
                error(
                    "Service start failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service start failed: {self.name}") from exc

    def suspend(self, *, context: EventPropagationContext | None = None) -> None:
        with self._lock:
            if self._state != LifecycleState.ACTIVE:
                raise ServiceException(
                    f"Cannot suspend service '{self.name}' from state {self._state.value}"
                )
            self._set_propagation_context(context)
            try:
                self._on_suspend()
                self._state = LifecycleState.SUSPENDED
                self._publish_lifecycle(
                    "ServiceSuspended",
                    EventType.PAUSE,
                    context=self._propagation_context,
                )
                info(
                    "Service suspended",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                self._publish_failure("suspend", exc, context=self._propagation_context)
                error(
                    "Service suspend failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service suspend failed: {self.name}") from exc

    def resume(self, *, context: EventPropagationContext | None = None) -> None:
        with self._lock:
            if self._state != LifecycleState.SUSPENDED:
                raise ServiceException(
                    f"Cannot resume service '{self.name}' from state {self._state.value}"
                )
            self._set_propagation_context(context)
            try:
                self._on_resume()
                self._state = LifecycleState.ACTIVE
                self._publish_lifecycle(
                    "ServiceResumed",
                    EventType.RESUME,
                    context=self._propagation_context,
                )
                info(
                    "Service resumed",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                self._publish_failure("resume", exc, context=self._propagation_context)
                error(
                    "Service resume failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(f"Service resume failed: {self.name}") from exc

    def terminate(self, *, context: EventPropagationContext | None = None) -> None:
        with self._lock:
            if self._state == LifecycleState.TERMINATED:
                return
            if self._state not in {
                LifecycleState.CREATED,
                LifecycleState.ACTIVE,
                LifecycleState.SUSPENDED,
            }:
                raise ServiceException(
                    f"Cannot terminate service '{self.name}' from state {self._state.value}"
                )
            self._set_propagation_context(context)
            try:
                self._on_terminate()
                self._state = LifecycleState.TERMINATED
                self._publish_lifecycle(
                    "ServiceStopped",
                    EventType.STOP,
                    context=self._propagation_context,
                )
                info(
                    "Service terminated",
                    {"service": self.name, "state": self._state.value},
                )
            except SH3Exception:
                raise
            except Exception as exc:
                self._publish_failure(
                    "terminate",
                    exc,
                    context=self._propagation_context,
                )
                error(
                    "Service termination failed",
                    {"service": self.name, "error": str(exc)},
                )
                raise ServiceException(
                    f"Service termination failed: {self.name}"
                ) from exc

    def health(self) -> HealthStatus:
        with self._lock:
            state = self._state
        if state == LifecycleState.ACTIVE:
            return HealthStatus.create(
                HealthState.HEALTHY,
                "Service is active",
                {"state": state.value},
                self.name,
                Severity.INFO,
            )
        if state == LifecycleState.SUSPENDED:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Service is suspended",
                {"state": state.value},
                self.name,
                Severity.MEDIUM,
            )
        if state == LifecycleState.TERMINATED:
            return HealthStatus.create(
                HealthState.UNHEALTHY,
                "Service is terminated",
                {"state": state.value},
                self.name,
                Severity.HIGH,
            )
        return HealthStatus.create(
            HealthState.UNKNOWN,
            "Service is not active",
            {"state": state.value},
            self.name,
            Severity.LOW,
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "active": self._state == LifecycleState.ACTIVE,
                "suspended": self._state == LifecycleState.SUSPENDED,
                "terminated": self._state == LifecycleState.TERMINATED,
            }

    def _set_propagation_context(
        self,
        context: EventPropagationContext | None,
    ) -> None:
        if context is not None:
            if not isinstance(context, EventPropagationContext):
                raise TypeError("context must be EventPropagationContext or None")
            self._propagation_context = context

    def _publish_lifecycle(
        self,
        event_name: str,
        event_type: EventType,
        *,
        context: EventPropagationContext | None,
    ) -> None:
        self._publish(
            event_name,
            {"service": self.name, "state": self._state.value},
            event_type,
            context=context,
        )

    def _publish_failure(
        self,
        operation: str,
        exc: Exception,
        *,
        context: EventPropagationContext | None,
    ) -> None:
        self._publish(
            "ServiceFailed",
            {
                "service": self.name,
                "operation": operation,
                "state": self._state.value,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            EventType.FAILURE,
            context=context,
        )

    def _publish(
        self,
        event_name: str,
        payload: dict[str, Any],
        event_type: EventType,
        *,
        context: EventPropagationContext | None,
    ) -> None:
        publisher = self._event_publisher
        if publisher is None:
            return
        try:
            propagation = context if context is not None else self._propagation_context
            if propagation is None:
                correlation_id = f"service:{self.name}"
                causation_id = None
                trace_id = None
                tenant_id = None
            else:
                correlation_id = propagation.correlation_id
                causation_id = propagation.causation_id
                trace_id = propagation.trace_id
                tenant_id = propagation.tenant_id

            event = Event.create(
                event_name=event_name,
                producer=self.name,
                payload=payload,
                category=Category.COMPONENT,
                event_type=event_type,
                correlation_id=correlation_id,
                causation_id=causation_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
            )
            publisher.publish(event)
            if propagation is not None:
                self._propagation_context = propagation.next(event.metadata.event_id)
        except Exception as exc:
            error(
                "Service event publication failed",
                {
                    "service": self.name,
                    "event_name": event_name,
                    "error": str(exc),
                },
            )

    @abstractmethod
    def _on_start(self) -> None:
        return None

    def _on_suspend(self) -> None:
        return None

    def _on_resume(self) -> None:
        return None

    def _on_terminate(self) -> None:
        return None
