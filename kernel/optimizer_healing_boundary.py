from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol, cast

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.learning_optimizer_boundary import LearningOptimizationResult
from kernel.recovery_execution_boundary import RecoveryExecutionBoundary
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary
from kernel.replay_execution_context import DurableOperationPersistenceError

__all__ = [
    "OptimizerHealingBoundary",
    "OptimizerHealingRequest",
    "OptimizerHealingResult",
]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


def _bool(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool")
    return value


class SelfHealingBackend(Protocol):
    def detect(
        self,
        exc: Exception,
        context: Mapping[str, Any] | None = None,
    ) -> Any: ...

    def recover_with_learning(
        self,
        snapshot: Any,
        max_attempts: int = 1,
    ) -> Any: ...

    def set_propagation_context(
        self,
        context: EventPropagationContext | None,
    ) -> None: ...

    @property
    def propagation_context(self) -> EventPropagationContext | None: ...


class StrategyRecoveryBackend(Protocol):
    def recover_with_strategy(self, snapshot: Any, strategy: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class OptimizerHealingRequest:
    request_id: str
    optimizer_id: str
    learning_record_id: str
    error: str
    optimization: Mapping[str, Any]
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    # P2-3: optimizer-healing replay metadata survives event serialization.
    replay_cycle_id: str | None = None
    replay_cycle_fingerprint: str | None = None
    replay_claim_owner_token: str | None = None
    replay_claim_generation: int | None = None
    replay_stage_input: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("optimizer_id", self.optimizer_id),
            ("learning_record_id", self.learning_record_id),
            ("error", self.error),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.causation_id is not None:
            _text("causation_id", self.causation_id)
        if self.trace_id is not None:
            _text("trace_id", self.trace_id)
        if self.tenant_id is not None:
            _text("tenant_id", self.tenant_id)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "optimization", _mapping(self.optimization))
        object.__setattr__(self, "metadata", _mapping(self.metadata))
        replay_values = (
            self.replay_cycle_id,
            self.replay_cycle_fingerprint,
            self.replay_claim_owner_token,
        )
        if self.replay_stage_input is not None and not isinstance(
            self.replay_stage_input, Mapping
        ):
            raise TypeError("replay_stage_input must be a mapping or None")
        replay_enabled = any(value is not None for value in replay_values) or (
            self.replay_claim_generation is not None
        ) or self.replay_stage_input is not None
        if replay_enabled:
            if any(value is None for value in replay_values) or (
                self.replay_claim_generation is None
            ) or self.replay_stage_input is None:
                raise ValueError(
                    "persistent optimizer healing requires complete replay metadata"
                )
            _text("replay_cycle_id", self.replay_cycle_id)
            _text("replay_cycle_fingerprint", self.replay_cycle_fingerprint)
            _text("replay_claim_owner_token", self.replay_claim_owner_token)
            if (
                isinstance(self.replay_claim_generation, bool)
                or not isinstance(self.replay_claim_generation, int)
                or self.replay_claim_generation < 1
            ):
                raise ValueError("replay_claim_generation must be a positive integer")
            object.__setattr__(
                self, "replay_stage_input", _mapping(self.replay_stage_input)
            )

    @classmethod
    def from_result(
        cls,
        result: LearningOptimizationResult,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
        replay_cycle_id: str | None = None,
        replay_cycle_fingerprint: str | None = None,
        replay_claim_owner_token: str | None = None,
        replay_claim_generation: int | None = None,
        replay_stage_input: Mapping[str, Any] | None = None,
    ) -> OptimizerHealingRequest:
        if not isinstance(result, LearningOptimizationResult):
            raise TypeError("result must be LearningOptimizationResult")
        if result.success:
            raise ValueError("optimizer result must indicate failure")
        message = result.error or f"optimizer cycle failure for {result.learning_record_id}"
        request_id = short_id(
            {
                "learning_optimization_request_id": result.request_id,
                "optimizer_id": result.optimizer_id,
                "learning_record_id": result.learning_record_id,
                "correlation_id": context.correlation_id,
                "causation_id": context.causation_id,
                "trace_id": context.trace_id,
                "tenant_id": context.tenant_id,
            },
            prefix="optimizer-healing:",
        )
        return cls(
            request_id=request_id,
            optimizer_id=result.optimizer_id,
            learning_record_id=result.learning_record_id,
            error=message,
            optimization=result.optimization,
            created_at=created_at or result.created_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            metadata={"optimization_request_id": result.request_id},
            replay_cycle_id=replay_cycle_id,
            replay_cycle_fingerprint=replay_cycle_fingerprint,
            replay_claim_owner_token=replay_claim_owner_token,
            replay_claim_generation=replay_claim_generation,
            replay_stage_input=replay_stage_input,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OptimizerHealingRequest:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = (
            created_at
            if isinstance(created_at, datetime)
            else datetime.fromisoformat(str(created_at))
        )
        optimization = data.get("optimization")
        metadata = data.get("metadata")
        replay_stage_input = data.get("replay_stage_input")
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            optimizer_id=_text("optimizer_id", data.get("optimizer_id")),
            learning_record_id=_text(
                "learning_record_id", data.get("learning_record_id")
            ),
            error=_text("error", data.get("error")),
            optimization=optimization if isinstance(optimization, Mapping) else {},
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            metadata=metadata if isinstance(metadata, Mapping) else {},
            replay_cycle_id=data.get("replay_cycle_id"),
            replay_cycle_fingerprint=data.get("replay_cycle_fingerprint"),
            replay_claim_owner_token=data.get("replay_claim_owner_token"),
            replay_claim_generation=data.get("replay_claim_generation"),
            replay_stage_input=(
                replay_stage_input if isinstance(replay_stage_input, Mapping) else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "optimizer_id": self.optimizer_id,
            "learning_record_id": self.learning_record_id,
            "error": self.error,
            "optimization": dict(self.optimization),
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
            "replay_cycle_id": self.replay_cycle_id,
            "replay_cycle_fingerprint": self.replay_cycle_fingerprint,
            "replay_claim_owner_token": self.replay_claim_owner_token,
            "replay_claim_generation": self.replay_claim_generation,
            "replay_stage_input": (
                dict(self.replay_stage_input)
                if self.replay_stage_input is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class OptimizerHealingResult:
    request_id: str
    optimizer_id: str
    learning_record_id: str
    success: bool
    healing: Mapping[str, Any]
    failure_id: str | None
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    error: str | None = None
    _next_context: EventPropagationContext | None = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        if self._next_context is not None and not isinstance(
            self._next_context, EventPropagationContext
        ):
            raise TypeError("_next_context must be EventPropagationContext or None")
        for name, value in (
            ("request_id", self.request_id),
            ("optimizer_id", self.optimizer_id),
            ("learning_record_id", self.learning_record_id),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.failure_id is not None:
            _text("failure_id", self.failure_id)
        if self.causation_id is not None:
            _text("causation_id", self.causation_id)
        if self.trace_id is not None:
            _text("trace_id", self.trace_id)
        if self.tenant_id is not None:
            _text("tenant_id", self.tenant_id)
        if self.error is not None:
            _text("error", self.error)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "healing", _mapping(self.healing))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OptimizerHealingResult:
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        created_at = data.get("created_at")
        timestamp = (
            created_at
            if isinstance(created_at, datetime)
            else datetime.fromisoformat(str(created_at))
        )
        healing = data.get("healing")
        return cls(
            request_id=_text("request_id", data.get("request_id")),
            optimizer_id=_text("optimizer_id", data.get("optimizer_id")),
            learning_record_id=_text(
                "learning_record_id", data.get("learning_record_id")
            ),
            success=_bool("success", data.get("success")),
            healing=healing if isinstance(healing, Mapping) else {},
            failure_id=data.get("failure_id"),
            created_at=timestamp,
            correlation_id=_text("correlation_id", data.get("correlation_id")),
            causation_id=data.get("causation_id"),
            trace_id=data.get("trace_id"),
            tenant_id=data.get("tenant_id"),
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "optimizer_id": self.optimizer_id,
            "learning_record_id": self.learning_record_id,
            "success": self.success,
            "healing": dict(self.healing),
            "failure_id": self.failure_id,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "error": self.error,
        }

    @property
    def propagation_context(self) -> EventPropagationContext:
        if self._next_context is not None:
            return self._next_context
        return EventPropagationContext.create(
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
        )


class OptimizerHealingBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_execution_boundary",
        "_last_context",
        "_lock",
        "_results",
        "_started",
        "_strategy_boundary",
        "_subscriber_id",
        "healer",
    )

    def __init__(
        self,
        healer: SelfHealingBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "optimizer.self-healing-boundary",
        strategy_boundary: RecoveryStrategyBoundary | None = None,
        execution_boundary: RecoveryExecutionBoundary | None = None,
    ) -> None:
        if healer is None:
            raise TypeError("healer must not be None")
        required = ("detect", "recover_with_learning", "set_propagation_context")
        if any(not callable(getattr(healer, name, None)) for name in required):
            raise TypeError("healer must provide self-healing operations")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        self.healer = healer
        if strategy_boundary is not None and not isinstance(strategy_boundary, RecoveryStrategyBoundary):
            raise TypeError("strategy_boundary must be RecoveryStrategyBoundary or None")
        if execution_boundary is not None and not isinstance(execution_boundary, RecoveryExecutionBoundary):
            raise TypeError("execution_boundary must be RecoveryExecutionBoundary or None")
        self._strategy_boundary = strategy_boundary
        self._execution_boundary = execution_boundary
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._lock = RLock()
        self._results: dict[str, OptimizerHealingResult] = {}
        self._last_context: EventPropagationContext | None = None
        self._started = False
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def strategy_boundary(self) -> RecoveryStrategyBoundary | None:
        return self._strategy_boundary

    @property
    def execution_boundary(self) -> RecoveryExecutionBoundary | None:
        return self._execution_boundary

    @property
    def replay_operation_store(self) -> Any:
        boundary = self._execution_boundary
        return None if boundary is None else boundary.replay_operation_store

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        with self._lock:
            return self._last_context

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = publisher
        self._configure()

    def records(self) -> tuple[OptimizerHealingResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def get(self, request_id: str) -> OptimizerHealingResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def request(
        self,
        optimization_result: LearningOptimizationResult,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
        replay_cycle_id: str | None = None,
        replay_cycle_fingerprint: str | None = None,
        replay_claim_owner_token: str | None = None,
        replay_claim_generation: int | None = None,
        replay_stage_input: Mapping[str, Any] | None = None,
    ) -> OptimizerHealingResult:
        request = OptimizerHealingRequest.from_result(
            optimization_result,
            context=context,
            created_at=created_at,
            replay_cycle_id=replay_cycle_id,
            replay_cycle_fingerprint=replay_cycle_fingerprint,
            replay_claim_owner_token=replay_claim_owner_token,
            replay_claim_generation=replay_claim_generation,
            replay_stage_input=replay_stage_input,
        )
        return self._start(request, context)

    def _start(
        self,
        request: OptimizerHealingRequest,
        context: EventPropagationContext,
    ) -> OptimizerHealingResult:
        with self._lock:
            existing = self._results.get(request.request_id)
            publisher = self._event_publisher
            event_bus = self._event_bus
        if existing is not None:
            return existing
        # Persistent Recovery owner/generation state is private process context.
        # Dispatch it synchronously so durable persistence failures cannot be
        # swallowed by EventBus delivery and converted into a missing-result error.
        if (
            request.replay_cycle_id is not None
            and self.replay_operation_store is not None
        ):
            return self._execute(request, context)
        if publisher is None or event_bus is None:
            return self._execute(request, context)
        self._publish(
            "OptimizerHealingRequested",
            EventType.START,
            {"request": request.to_dict()},
            context,
        )
        result = self.get(request.request_id)
        if result is None:
            raise RuntimeError(f"healing result not produced: {request.request_id}")
        return result

    def _configure(self) -> None:
        publisher = self._event_publisher
        event_bus = getattr(publisher, "event_bus", None) if publisher is not None else None
        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None
        if self._event_bus is event_bus:
            return
        if self._event_bus is not None:
            with suppress(KeyError):
                self._event_bus.unsubscribe(self._subscriber_id)
        self._event_bus = event_bus
        if event_bus is None:
            with self._lock:
                self._started = False
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id=self._subscriber_id,
                handler=self._handle_request,
                event_name="OptimizerHealingRequested",
                priority=100,
            ),
            replace=True,
        )
        with self._lock:
            self._started = True

    def _handle_request(self, event: Event) -> None:
        payload = event.payload.get("request")
        if not isinstance(payload, Mapping):
            return
        try:
            request = OptimizerHealingRequest.from_dict(payload)
            self._execute(request, EventPropagationContext.from_event(event))
        except DurableOperationPersistenceError:
            raise
        except Exception as exc:
            error(
                "Optimizer healing boundary event handling failed",
                {"error": str(exc)},
            )

    def _execute(
        self,
        request: OptimizerHealingRequest,
        context: EventPropagationContext,
    ) -> OptimizerHealingResult:
        with self._lock:
            existing = self._results.get(request.request_id)
            if existing is not None:
                return existing
            failure_id: str | None = None
            healing: Mapping[str, Any] = {}
            success = False
            error_message: str | None = None
            result_context = context
            try:
                self.healer.set_propagation_context(context)
                snapshot = self.healer.detect(
                    RuntimeError(request.error),
                    {
                        "source": "optimizer",
                        "optimizer_id": request.optimizer_id,
                        "learning_record_id": request.learning_record_id,
                        "request_id": request.request_id,
                        "optimization": dict(request.optimization),
                        **dict(request.metadata),
                    },
                )
                failure_id = getattr(snapshot, "trace_id", None)
                replay_arguments: dict[str, Any] = {}
                if request.replay_cycle_id is not None:
                    replay_arguments = {
                        "replay_cycle_id": request.replay_cycle_id,
                        "replay_cycle_fingerprint": request.replay_cycle_fingerprint,
                        "replay_claim_owner_token": request.replay_claim_owner_token,
                        "replay_claim_generation": request.replay_claim_generation,
                        "replay_stage_input": request.replay_stage_input,
                    }
                    if self._strategy_boundary is None or self._execution_boundary is None:
                        raise RuntimeError(
                            "persistent optimizer healing requires recovery strategy and execution boundaries"
                        )
                if self._strategy_boundary is None:
                    value = self.healer.recover_with_learning(snapshot, max_attempts=1)
                else:
                    strategy = self._strategy_boundary.request(
                        snapshot,
                        context=self.healer.propagation_context or context,
                        created_at=request.created_at,
                        **replay_arguments,
                    )
                    self.healer.set_propagation_context(strategy.propagation_context)
                    if self._execution_boundary is None:
                        strategy_recovery = cast(StrategyRecoveryBackend, self.healer)
                        value = strategy_recovery.recover_with_strategy(snapshot, strategy.selected_strategy)
                    else:
                        execution = self._execution_boundary.request(
                            strategy,
                            snapshot,
                            context=strategy.propagation_context,
                            created_at=request.created_at,
                            **replay_arguments,
                        )
                        if not execution.success:
                            raise RuntimeError(execution.error or "recovery execution failed")
                        value = execution.result
                    if isinstance(value, Mapping):
                        value = {**dict(value), "strategy": strategy.selected_strategy}
                healing = value if isinstance(value, Mapping) else {"result": value}
                result_context = self.healer.propagation_context or context
                success = True
            except DurableOperationPersistenceError:
                raise
            except Exception as exc:
                error_message = str(exc)
                result_context = self.healer.propagation_context or context

            result = OptimizerHealingResult(
                request_id=request.request_id,
                optimizer_id=request.optimizer_id,
                learning_record_id=request.learning_record_id,
                success=success,
                healing=healing,
                failure_id=failure_id,
                created_at=request.created_at,
                correlation_id=result_context.correlation_id,
                causation_id=result_context.causation_id,
                trace_id=result_context.trace_id,
                tenant_id=result_context.tenant_id,
                error=error_message,
            )
            self._results[request.request_id] = result
        event_name = "OptimizerHealingCompleted" if success else "OptimizerHealingFailed"
        event_type = EventType.COMPLETE if success else EventType.FAILURE
        final_context = self._publish(
            event_name,
            event_type,
            {"request": request.to_dict(), "result": result.to_dict()},
            result_context,
        )
        result = replace(result, _next_context=final_context)

        with self._lock:
            self._last_context = final_context
            self._results[request.request_id] = result

        return result

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: Mapping[str, Any],
        context: EventPropagationContext,
    ) -> EventPropagationContext:
        publisher = self._event_publisher
        if publisher is None:
            return context
        try:
            event = Event.create(
                event_name=event_name,
                producer=self._subscriber_id,
                payload=payload,
                category=Category.ACTION,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            return context.next(event.metadata.event_id)
        except Exception as exc:
            error(
                "Optimizer healing boundary event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )
            return context
