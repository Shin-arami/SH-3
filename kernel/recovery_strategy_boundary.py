from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event as ThreadEvent
from threading import RLock
from types import MappingProxyType
from typing import Any, Protocol

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security.persistent_store import (
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteReplayStageStore,
)
from self_healing.core import FailureSnapshot

__all__ = [
    "RecoveryStrategyBoundary",
    "RecoveryStrategyEvaluation",
    "RecoveryStrategyResult",
]


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


class RecoveryStrategyBackend(Protocol):
    @property
    def learned(self) -> bool: ...

    def strategy_candidates(self, snapshot: FailureSnapshot) -> tuple[str, ...]: ...

    def evaluate_strategies(self, snapshot: FailureSnapshot) -> Mapping[str, tuple[int, int, float]]: ...

    def select_strategy(self, snapshot: FailureSnapshot) -> str: ...


@dataclass(frozen=True, slots=True)
class RecoveryStrategyEvaluation:
    strategy: str
    samples: int
    successes: int
    success_rate: float
    rank: int
    selected: bool = False

    def __post_init__(self) -> None:
        _text("strategy", self.strategy)
        if not isinstance(self.samples, int) or isinstance(self.samples, bool) or self.samples < 0:
            raise ValueError("samples must be a non-negative integer")
        if not isinstance(self.successes, int) or isinstance(self.successes, bool) or self.successes < 0:
            raise ValueError("successes must be a non-negative integer")
        if self.successes > self.samples:
            raise ValueError("successes must not exceed samples")
        if not isinstance(self.success_rate, (int, float)) or isinstance(self.success_rate, bool):
            raise TypeError("success_rate must be numeric")
        if not 0.0 <= float(self.success_rate) <= 1.0:
            raise ValueError("success_rate must be between 0 and 1")
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 0:
            raise ValueError("rank must be a non-negative integer")
        if not isinstance(self.selected, bool):
            raise TypeError("selected must be bool")
        object.__setattr__(self, "success_rate", float(self.success_rate))

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "samples": self.samples,
            "successes": self.successes,
            "success_rate": self.success_rate,
            "rank": self.rank,
            "selected": self.selected,
        }


@dataclass(frozen=True, slots=True)
class RecoveryStrategyResult:
    request_id: str
    failure_id: str
    selected_strategy: str
    evaluations: tuple[RecoveryStrategyEvaluation, ...]
    learned: bool
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("failure_id", self.failure_id),
            ("selected_strategy", self.selected_strategy),
            ("correlation_id", self.correlation_id),
        ):
            _text(name, value)
        if not self.evaluations:
            raise ValueError("evaluations must not be empty")
        if not any(item.strategy == self.selected_strategy and item.selected for item in self.evaluations):
            raise ValueError("selected_strategy must match a selected evaluation")
        if not isinstance(self.learned, bool):
            raise TypeError("learned must be bool")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        for field_name, field_value in (("causation_id", self.causation_id), ("trace_id", self.trace_id), ("tenant_id", self.tenant_id)):
            if field_value is not None:
                _text(field_name, field_value)
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @property
    def selected(self) -> RecoveryStrategyEvaluation:
        return next(item for item in self.evaluations if item.selected)

    @property
    def confidence(self) -> float:
        return self.selected.success_rate

    @property
    def propagation_context(self) -> EventPropagationContext:
        return EventPropagationContext.create(
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "failure_id": self.failure_id,
            "selected_strategy": self.selected_strategy,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "learned": self.learned,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


class RecoveryStrategyBoundary:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_inflight",
        "_last_context",
        "_lock",
        "_pending",
        "_replay_stage_store",
        "_results",
        "_subscriber_id",
        "backend",
    )

    def __init__(
        self,
        backend: RecoveryStrategyBackend,
        event_publisher: EventPublisher | None = None,
        *,
        subscriber_id: str = "recovery.strategy-boundary",
        replay_stage_store: SQLiteReplayStageStore | None = None,
    ) -> None:
        if backend is None:
            raise TypeError("backend must not be None")
        required = ("strategy_candidates", "evaluate_strategies", "select_strategy")
        if any(not callable(getattr(backend, name, None)) for name in required):
            raise TypeError("backend must provide strategy evaluation and selection APIs")
        if event_publisher is not None and not isinstance(event_publisher, EventPublisher):
            raise TypeError("event_publisher must be EventPublisher or None")
        if replay_stage_store is not None and not isinstance(
            replay_stage_store, SQLiteReplayStageStore
        ):
            raise TypeError(
                "replay_stage_store must be SQLiteReplayStageStore or None"
            )
        self.backend = backend
        self._replay_stage_store = replay_stage_store
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._lock = RLock()
        self._results: dict[str, RecoveryStrategyResult] = {}
        self._pending: dict[
            str,
            tuple[
                FailureSnapshot,
                EventPropagationContext,
                datetime,
                ReplayStageKey | None,
                str | None,
                int | None,
            ],
        ] = {}
        self._inflight: dict[str, ThreadEvent] = {}
        self._last_context: EventPropagationContext | None = None
        self._subscriber_id = _text("subscriber_id", subscriber_id)
        self._configure()

    @property
    def event_publisher(self) -> EventPublisher | None:
        with self._lock:
            return self._event_publisher

    @property
    def propagation_context(self) -> EventPropagationContext | None:
        with self._lock:
            return self._last_context

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must be EventPublisher or None")
        with self._lock:
            self._event_publisher = publisher
        self._configure()

    def records(self) -> tuple[RecoveryStrategyResult, ...]:
        with self._lock:
            return tuple(self._results[key] for key in sorted(self._results))

    def get(self, request_id: str) -> RecoveryStrategyResult | None:
        _text("request_id", request_id)
        with self._lock:
            return self._results.get(request_id)

    def request(
        self,
        snapshot: FailureSnapshot,
        *,
        context: EventPropagationContext,
        created_at: datetime | None = None,
        replay_cycle_id: str | None = None,
        replay_cycle_fingerprint: str | None = None,
        replay_claim_owner_token: str | None = None,
        replay_claim_generation: int | None = None,
        replay_stage_input: Mapping[str, Any] | None = None,
    ) -> RecoveryStrategyResult:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be FailureSnapshot")
        if not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext")

        claim_values = (
            replay_cycle_id,
            replay_cycle_fingerprint,
            replay_claim_owner_token,
            replay_claim_generation,
        )
        replay_enabled = any(value is not None for value in claim_values)
        if replay_enabled:
            if any(value is None for value in claim_values):
                raise ValueError("persistent recovery requires complete replay claim metadata")
            if self._replay_stage_store is None:
                raise ValueError(
                    "replay claim metadata requires a configured replay stage store"
                )
            if not isinstance(replay_stage_input, Mapping):
                raise TypeError("replay_stage_input must be a mapping for persistent recovery")
            assert replay_cycle_id is not None
            assert replay_cycle_fingerprint is not None
            assert replay_claim_owner_token is not None
            assert replay_claim_generation is not None
            stage_key = ReplayStageKey.create(
                replay_cycle_id,
                replay_cycle_fingerprint,
                "recovery_strategy.select.v1",
                {
                    "contract": "recovery-strategy-v1",
                    "recovery_input": dict(replay_stage_input),
                },
            )
            stage_owner_token: str | None = replay_claim_owner_token
            stage_generation: int | None = replay_claim_generation
        else:
            if replay_stage_input is not None:
                raise ValueError("replay_stage_input requires complete replay claim metadata")
            stage_key = None
            stage_owner_token = None
            stage_generation = None

        candidates = tuple(self.backend.strategy_candidates(snapshot))
        if not candidates:
            raise ValueError("strategy candidates must not be empty")
        request_id = short_id(
            {
                "failure_id": snapshot.trace_id,
                "candidates": candidates,
                "correlation_id": context.correlation_id,
                "causation_id": context.causation_id,
                "trace_id": context.trace_id,
                "tenant_id": context.tenant_id,
            },
            prefix="recovery-strategy:",
        )
        request_created_at = created_at or datetime.now(UTC)
        with self._lock:
            existing = self._results.get(request_id)
            if existing is not None:
                return existing
            waiter = self._inflight.get(request_id)
            if waiter is None:
                waiter = ThreadEvent()
                self._inflight[request_id] = waiter
                self._pending[request_id] = (
                    snapshot,
                    context,
                    request_created_at,
                    stage_key,
                    stage_owner_token,
                    stage_generation,
                )
                leader = True
            else:
                leader = False
        if not leader:
            waiter.wait()
            result = self.get(request_id)
            if result is None:
                raise RuntimeError(f"recovery strategy result not produced: {request_id}")
            return result

        try:
            stage_execution = None
            if stage_key is not None:
                assert self._replay_stage_store is not None
                assert stage_owner_token is not None
                assert stage_generation is not None
                stage_execution = self._replay_stage_store.begin(
                    stage_key,
                    stage_owner_token,
                    stage_generation,
                )

            replayed = (
                stage_execution is not None
                and stage_execution.status is ReplayStageStatus.COMPLETED
            )
            payload: dict[str, Any] = {
                "request_id": request_id,
                "failure_id": snapshot.trace_id,
                "candidates": candidates,
            }
            if stage_key is not None:
                payload["idempotency_key"] = stage_key.idempotency_key
                payload["replayed"] = replayed

            publisher = self.event_publisher
            event_bus = self._event_bus
            request_context = context
            if publisher is not None and event_bus is not None:
                request_context = self._publish(
                    "RecoveryStrategyRequested",
                    EventType.START,
                    payload,
                    context,
                )
                if replayed:
                    assert stage_execution is not None
                    if stage_execution.result is None:
                        raise RuntimeError(
                            "completed recovery strategy stage has no persisted result"
                        )
                    assert stage_key is not None
                    return self._restore_completed_stage(
                        request_id,
                        snapshot,
                        stage_execution.result,
                        context=request_context,
                        created_at=request_created_at,
                        idempotency_key=stage_key.idempotency_key,
                    )
                result = self.get(request_id)
                if result is None:
                    raise RuntimeError(f"recovery strategy result not produced: {request_id}")
                return result

            if replayed:
                assert stage_execution is not None
                if stage_execution.result is None:
                    raise RuntimeError(
                        "completed recovery strategy stage has no persisted result"
                    )
                assert stage_key is not None
                return self._restore_completed_stage(
                    request_id,
                    snapshot,
                    stage_execution.result,
                    context=request_context,
                    created_at=request_created_at,
                    idempotency_key=stage_key.idempotency_key,
                )

            return self._execute(
                request_id,
                snapshot,
                context=request_context,
                created_at=request_created_at,
                replay_stage_key=stage_key,
                replay_stage_owner_token=stage_owner_token,
                replay_stage_generation=stage_generation,
            )
        finally:
            with self._lock:
                waiter = self._inflight.pop(request_id, None)
                self._pending.pop(request_id, None)
                if waiter is not None:
                    waiter.set()

    def _configure(self) -> None:
        publisher = self.event_publisher
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
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id=self._subscriber_id,
                handler=self._handle_request,
                event_name="RecoveryStrategyRequested",
                priority=100,
            ),
            replace=True,
        )

    def _handle_request(self, event: Event) -> None:
        request_id = event.payload.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return
        if event.payload.get("replayed") is True:
            return
        with self._lock:
            pending = self._pending.get(request_id)
        if pending is None:
            return
        (
            snapshot,
            context,
            created_at,
            stage_key,
            stage_owner_token,
            stage_generation,
        ) = pending
        try:
            self._execute(
                request_id,
                snapshot,
                context=EventPropagationContext.from_event(event),
                created_at=created_at,
                replay_stage_key=stage_key,
                replay_stage_owner_token=stage_owner_token,
                replay_stage_generation=stage_generation,
            )
        except Exception as exc:
            context = EventPropagationContext.from_event(event)
            failure_payload: dict[str, Any] = {
                "request_id": request_id,
                "failure_id": snapshot.trace_id,
                "error": str(exc),
            }
            if stage_key is not None:
                failure_payload["idempotency_key"] = stage_key.idempotency_key
            self._publish(
                "RecoveryStrategySelectionFailed",
                EventType.FAILURE,
                failure_payload,
                context,
            )
            error("Recovery strategy boundary event handling failed", {"error": str(exc), "request_id": request_id})

    def _execute(
        self,
        request_id: str,
        snapshot: FailureSnapshot,
        *,
        context: EventPropagationContext,
        created_at: datetime,
        replay_stage_key: ReplayStageKey | None = None,
        replay_stage_owner_token: str | None = None,
        replay_stage_generation: int | None = None,
    ) -> RecoveryStrategyResult:
        with self._lock:
            existing = self._results.get(request_id)
        if existing is not None:
            return existing
        candidates = tuple(self.backend.strategy_candidates(snapshot))
        raw_scores = self.backend.evaluate_strategies(snapshot)
        selected_strategy = self.backend.select_strategy(snapshot)
        if selected_strategy not in candidates:
            raise ValueError(f"selected strategy is not a candidate: {selected_strategy}")
        evaluations_list: list[RecoveryStrategyEvaluation] = []
        for index, strategy in enumerate(candidates):
            samples, successes, success_rate = raw_scores.get(strategy, (0, 0, 0.0))
            evaluations_list.append(
                RecoveryStrategyEvaluation(
                    strategy=strategy,
                    samples=max(0, int(samples)),
                    successes=max(0, int(successes)),
                    success_rate=float(success_rate),
                    rank=index,
                    selected=strategy == selected_strategy,
                )
            )
        evaluations = tuple(evaluations_list)
        event_details: dict[str, Any] = {
            "request_id": request_id,
            "failure_id": snapshot.trace_id,
            "evaluations": [item.to_dict() for item in evaluations],
        }
        if replay_stage_key is not None:
            event_details["idempotency_key"] = replay_stage_key.idempotency_key
            event_details["replayed"] = False
        result_context = self._publish(
            "RecoveryStrategyEvaluated",
            EventType.UPDATED,
            event_details,
            context,
        )
        metadata: dict[str, Any] = {}
        if replay_stage_key is not None:
            metadata["idempotency_key"] = replay_stage_key.idempotency_key
        result = RecoveryStrategyResult(
            request_id=request_id,
            failure_id=snapshot.trace_id,
            selected_strategy=selected_strategy,
            evaluations=evaluations,
            learned=bool(getattr(self.backend, "learned", False)),
            created_at=created_at,
            correlation_id=result_context.correlation_id,
            causation_id=result_context.causation_id,
            trace_id=result_context.trace_id,
            tenant_id=result_context.tenant_id,
            metadata=metadata,
        )

        if replay_stage_key is not None:
            if self._replay_stage_store is None:
                raise RuntimeError("persistent recovery stage store is unavailable")
            if replay_stage_owner_token is None or replay_stage_generation is None:
                raise RuntimeError("persistent recovery stage has incomplete ownership metadata")
            self._replay_stage_store.complete(
                replay_stage_key,
                replay_stage_owner_token,
                replay_stage_generation,
                {
                    "contract": "recovery-strategy-v1",
                    "selected_strategy": selected_strategy,
                    "evaluations": [item.to_dict() for item in evaluations],
                    "learned": result.learned,
                },
            )

        with self._lock:
            self._results[request_id] = result
            self._last_context = result_context
        selected_payload: dict[str, Any] = {
            "request_id": request_id,
            "failure_id": snapshot.trace_id,
            "strategy": selected_strategy,
            "confidence": result.confidence,
            "evaluations": [item.to_dict() for item in evaluations],
        }
        if replay_stage_key is not None:
            selected_payload["idempotency_key"] = replay_stage_key.idempotency_key
            selected_payload["replayed"] = False
        final_context = self._publish(
            "RecoveryStrategySelected",
            EventType.COMPLETE,
            selected_payload,
            result_context,
        )
        with self._lock:
            self._last_context = final_context
            self._results[request_id] = RecoveryStrategyResult(
                request_id=result.request_id,
                failure_id=result.failure_id,
                selected_strategy=result.selected_strategy,
                evaluations=result.evaluations,
                learned=result.learned,
                created_at=result.created_at,
                correlation_id=result_context.correlation_id,
                causation_id=final_context.causation_id,
                trace_id=final_context.trace_id,
                tenant_id=final_context.tenant_id,
                metadata=result.metadata,
            )
            return self._results[request_id]

    def _restore_completed_stage(
        self,
        request_id: str,
        snapshot: FailureSnapshot,
        stored_result: Mapping[str, Any],
        *,
        context: EventPropagationContext,
        created_at: datetime,
        idempotency_key: str,
    ) -> RecoveryStrategyResult:
        if stored_result.get("contract") != "recovery-strategy-v1":
            raise ValueError("persisted recovery strategy stage contract is invalid")
        selected_strategy = stored_result.get("selected_strategy")
        if not isinstance(selected_strategy, str) or not selected_strategy.strip():
            raise ValueError("persisted recovery strategy selection is invalid")
        learned = stored_result.get("learned")
        if not isinstance(learned, bool):
            raise ValueError("persisted recovery strategy learned flag is invalid")
        raw_evaluations = stored_result.get("evaluations")
        if not isinstance(raw_evaluations, (list, tuple)) or not raw_evaluations:
            raise ValueError("persisted recovery strategy evaluations are invalid")

        evaluations: list[RecoveryStrategyEvaluation] = []
        for item in raw_evaluations:
            if not isinstance(item, Mapping):
                raise ValueError("persisted recovery strategy evaluation is invalid")

            strategy = item.get("strategy")
            samples = item.get("samples")
            successes = item.get("successes")
            success_rate = item.get("success_rate")
            rank = item.get("rank")
            selected = item.get("selected", False)

            if not isinstance(strategy, str) or not strategy.strip():
                raise ValueError("persisted recovery strategy name is invalid")
            if (
                not isinstance(samples, int)
                or isinstance(samples, bool)
                or samples < 0
            ):
                raise ValueError("persisted recovery strategy samples are invalid")
            if (
                not isinstance(successes, int)
                or isinstance(successes, bool)
                or successes < 0
            ):
                raise ValueError("persisted recovery strategy successes are invalid")
            if (
                not isinstance(success_rate, (int, float))
                or isinstance(success_rate, bool)
            ):
                raise ValueError("persisted recovery strategy success rate is invalid")
            if (
                not isinstance(rank, int)
                or isinstance(rank, bool)
                or rank < 0
            ):
                raise ValueError("persisted recovery strategy rank is invalid")
            if not isinstance(selected, bool):
                raise ValueError("persisted recovery strategy selected flag is invalid")

            evaluations.append(
                RecoveryStrategyEvaluation(
                    strategy=strategy,
                    samples=samples,
                    successes=successes,
                    success_rate=float(success_rate),
                    rank=rank,
                    selected=selected,
                )
            )
        evaluation_values = tuple(evaluations)
        event_details: dict[str, Any] = {
            "request_id": request_id,
            "failure_id": snapshot.trace_id,
            "evaluations": [item.to_dict() for item in evaluation_values],
            "idempotency_key": idempotency_key,
            "replayed": True,
        }
        result_context = self._publish(
            "RecoveryStrategyEvaluated",
            EventType.UPDATED,
            event_details,
            context,
        )
        result = RecoveryStrategyResult(
            request_id=request_id,
            failure_id=snapshot.trace_id,
            selected_strategy=selected_strategy,
            evaluations=evaluation_values,
            learned=learned,
            created_at=created_at,
            correlation_id=result_context.correlation_id,
            causation_id=result_context.causation_id,
            trace_id=result_context.trace_id,
            tenant_id=result_context.tenant_id,
            metadata={"idempotency_key": idempotency_key, "replayed": True},
        )
        with self._lock:
            self._results[request_id] = result
            self._last_context = result_context
        selected_payload: dict[str, Any] = {
            "request_id": request_id,
            "failure_id": snapshot.trace_id,
            "strategy": selected_strategy,
            "confidence": result.confidence,
            "evaluations": [item.to_dict() for item in evaluation_values],
            "idempotency_key": idempotency_key,
            "replayed": True,
        }
        final_context = self._publish(
            "RecoveryStrategySelected",
            EventType.COMPLETE,
            selected_payload,
            result_context,
        )
        with self._lock:
            self._last_context = final_context
            self._results[request_id] = RecoveryStrategyResult(
                request_id=result.request_id,
                failure_id=result.failure_id,
                selected_strategy=result.selected_strategy,
                evaluations=result.evaluations,
                learned=result.learned,
                created_at=result.created_at,
                correlation_id=result_context.correlation_id,
                causation_id=final_context.causation_id,
                trace_id=final_context.trace_id,
                tenant_id=final_context.tenant_id,
                metadata=result.metadata,
            )
            return self._results[request_id]

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: Mapping[str, Any],
        context: EventPropagationContext,
    ) -> EventPropagationContext:
        publisher = self.event_publisher
        if publisher is None:
            return context
        try:
            event = Event.create(
                event_name=event_name,
                producer="healing.strategy",
                payload=payload,
                category=Category.STRATEGY,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            return context.next(event.metadata.event_id)
        except Exception as exc:
            error("Recovery strategy event publication failed", {"event_name": event_name, "error": str(exc)})
            return context
