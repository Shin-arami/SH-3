from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from types import MappingProxyType
from typing import Any

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.exceptions import SH3Exception
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from foundation.utils.time import iso
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security import EvidenceRecord, EvidenceStore

__all__ = [
    "FailureSnapshot",
    "RecoveryAttempt",
    "RecoveryPlan",
    "SelfHealingCore",
    "SelfHealingException",
]


class SelfHealingException(SH3Exception):
    """Self-healing operation failure."""


@dataclass(frozen=True, slots=True)
class FailureSnapshot:
    error: Exception
    context: Mapping[str, Any]
    timestamp: str
    trace_id: str

    @classmethod
    def create(
        cls,
        error: Exception,
        context: Mapping[str, Any],
    ) -> FailureSnapshot:
        timestamp = iso(datetime.now(UTC))
        trace_id = short_id(f"{type(error).__name__}:{error}:{timestamp}")
        return cls(
            error=error,
            context=dict(context),
            timestamp=timestamp,
            trace_id=trace_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": str(self.error),
            "type": type(self.error).__name__,
            "context": dict(self.context),
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    strategy: str
    action: Callable[[FailureSnapshot], Any]
    trace_id: str

    @classmethod
    def create(
        cls,
        strategy: str,
        action: Callable[[FailureSnapshot], Any],
    ) -> RecoveryPlan:
        return cls(
            strategy=strategy,
            action=action,
            trace_id=short_id(f"recovery:{strategy}"),
        )

    def execute(self, snapshot: FailureSnapshot) -> Any:
        return self.action(snapshot)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class RecoveryAttempt:
    attempt: int
    strategy: str
    success: bool
    timestamp: str
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "strategy": self.strategy,
            "success": self.success,
            "timestamp": self.timestamp,
            "result": self.result,
            "error": self.error,
        }


class SelfHealingCore:
    __slots__ = (
        "_attempts",
        "_detected",
        "_event_bus",
        "_event_publisher",
        "_evidence_store",
        "_failed",
        "_last_event_id",
        "_last_failure",
        "_last_plan",
        "_last_result",
        "_learned_records",
        "_lock",
        "_propagation_context",
        "_recovered",
        "context_manager",
        "learning",
        "runtime",
    )

    _MIN_LEARNING_SAMPLES = 3

    def __init__(
        self,
        runtime: Any = None,
        context_manager: Any = None,
        learning: Any = None,
        *,
        learning_service: Any = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.runtime = runtime
        self.context_manager = context_manager
        self.learning = (
            learning_service if learning_service is not None else learning
        )
        self._lock = RLock()
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._evidence_store = EvidenceStore()
        self._last_event_id: str | None = None
        self._attempts: list[RecoveryAttempt] = []
        self._detected = 0
        self._recovered = 0
        self._failed = 0
        self._last_failure: FailureSnapshot | None = None
        self._last_plan: RecoveryPlan | None = None
        self._last_result: Any = None
        self._propagation_context: EventPropagationContext | None = None
        self._learned_records: list[dict[str, Any]] = []
        self._configure_learning_subscription()


    @property
    def evidence_store(self) -> EvidenceStore:
        return self._evidence_store

    def recovery_evidence(self) -> EvidenceRecord | None:
        with self._lock:
            failure = self._last_failure
            plan = self._last_plan
            attempts = tuple(self._attempts)
            result = self._last_result
        if failure is None or plan is None:
            return None
        record = EvidenceRecord.create(
            evidence_id=f"recovery:{failure.trace_id}",
            kind="recovery",
            source="self-healing",
            subject_id=plan.trace_id,
            version="1.0.0",
            trace_id=failure.trace_id,
            payload={
                "failure": failure.to_dict(),
                "plan": plan.to_dict(),
                "attempts": [attempt.to_dict() for attempt in attempts],
                "result": result,
                "recovered": self.recovered,
                "failed": self.failed,
            },
        )
        return self._evidence_store.register(record)

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must implement EventPublisher")
        self._event_publisher = publisher
        self._configure_learning_subscription()

    def _configure_learning_subscription(self) -> None:
        publisher = self._event_publisher
        event_bus = (
            getattr(publisher, "event_bus", None) if publisher is not None else None
        )
        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None
        if self._event_bus is event_bus:
            return
        if self._event_bus is not None:
            with suppress(KeyError):
                self._event_bus.unsubscribe("self-healing-learning")
        self._event_bus = event_bus
        if event_bus is None:
            return
        event_bus.subscribe(
            EventSubscription(
                subscriber_id="self-healing-learning",
                handler=self._handle_learning_event,
                event_name="LearningResultRecorded",
                priority=100,
            ),
            replace=True,
        )

    def _handle_learning_event(self, event: Event) -> None:
        if event.name != "LearningResultRecorded":
            return
        record = event.payload
        if not isinstance(record, Mapping):
            return
        domain = str(record.get("domain", ""))
        details = record.get("details", {})
        success = record.get("success")
        score = record.get("score")
        if domain != "self_healing.recovery" or not isinstance(details, Mapping):
            return
        if (
            not isinstance(success, bool)
            or not isinstance(score, (int, float))
            or isinstance(score, bool)
        ):
            return
        if float(score) != (1.0 if success else 0.0):
            return
        normalized = {
            "domain": domain,
            "score": float(score),
            "success": success,
            "details": dict(details),
            "record_id": record.get("record_id"),
        }
        with self._lock:
            self._learned_records.append(normalized)

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: dict[str, Any],
        snapshot: FailureSnapshot | None = None,
        context: EventPropagationContext | None = None,
    ) -> EventPropagationContext | None:
        publisher = self._event_publisher
        propagation = context or self._propagation_context

        if publisher is None:
            return propagation

        try:
            if propagation is None:
                trace_id = snapshot.trace_id if snapshot is not None else None
                propagation = EventPropagationContext.create(
                    correlation_id=trace_id or "healing",
                    trace_id=trace_id,
                )

            event = Event.create(
                event_name=event_name,
                producer="healing",
                payload=payload,
                category=(
                    Category.LEARNING
                    if event_name == "HealingFeedbackRecorded"
                    else Category.ACTION
                ),
                event_type=event_type,
                correlation_id=propagation.correlation_id,
                causation_id=propagation.causation_id,
                trace_id=propagation.trace_id,
                tenant_id=propagation.tenant_id,
            )
            publisher.publish(event)

            next_context = propagation.next(event.metadata.event_id)
            self._last_event_id = event.metadata.event_id
            self._propagation_context = next_context
            return next_context

        except Exception as exc:
            info(
                "Self-healing event publication failed",
                {"event": event_name, "error": str(exc)},
            )
            return propagation

    def detect(
        self,
        exc: Exception,
        context: Mapping[str, Any] | None = None,
    ) -> FailureSnapshot:
        if not isinstance(exc, Exception):
            raise TypeError("exc must be an Exception")
        snapshot = FailureSnapshot.create(exc, context or {})
        with self._lock:
            self._detected += 1
            self._last_failure = snapshot
            self._attempts.clear()
        error("Failure detected", snapshot.to_dict())
        self._publish(
            "FailureDetected",
            EventType.FAILURE,
            {
                "failure_id": snapshot.trace_id,
                "component": "self-healing",
                "error": str(snapshot.error),
                "details": dict(snapshot.context),
            },
            snapshot,
        )
        return snapshot

    def _strategy_candidates(
        self,
        snapshot: FailureSnapshot,
    ) -> tuple[str, ...]:
        exc = snapshot.error
        if isinstance(exc, SH3Exception):
            return (
                "retry_safe",
                "rebuild_context",
                "fallback_default",
            )
        if isinstance(exc, KeyError):
            return (
                "fallback_default",
                "retry_safe",
                "rebuild_context",
            )
        if isinstance(exc, (ValueError, TypeError)):
            return (
                "rebuild_context",
                "retry_safe",
                "fallback_default",
            )
        return (
            "rebuild_context",
            "retry_safe",
            "fallback_default",
        )

    def _strategy_action(
        self,
        strategy: str,
    ) -> Callable[[FailureSnapshot], Any]:
        actions: dict[str, Callable[[FailureSnapshot], Any]] = {
            "retry_safe": self._retry,
            "fallback_default": self._fallback,
            "rebuild_context": self._rebuild,
        }
        action = actions.get(strategy)
        if action is None:
            raise SelfHealingException(f"Unknown recovery strategy: {strategy}")
        return action

    _VALID_STRATEGIES = frozenset(
        {
            "retry_safe",
            "rebuild_context",
            "fallback_default",
        }
    )

    @classmethod
    def _record_strategy(cls, record: Any) -> str | None:
        if isinstance(record, Mapping):
            key = str(record.get("key", record.get("domain", "")))
            details = record.get("details", {})
        else:
            key = str(getattr(record, "key", ""))
            details = getattr(record, "details", None)
        if key.startswith("self_healing:"):
            strategy = key.removeprefix("self_healing:")
        elif key == "self_healing.recovery":
            if not isinstance(details, Mapping):
                return None
            strategy = str(details.get("strategy", ""))
        else:
            return None
        return strategy if strategy in cls._VALID_STRATEGIES else None

    @staticmethod
    def _record_success(record: Any) -> bool:
        if isinstance(record, Mapping):
            return bool(record.get("success", False))
        return bool(getattr(record, "success", False))

    def _learning_records(self) -> tuple[Any, ...]:
        learning = self.learning
        if learning is None:
            with self._lock:
                values = tuple(self._learned_records)
            return tuple(record for record in values if self._record_strategy(record) is not None)
        records = getattr(learning, "records", None)
        if not callable(records):
            with self._lock:
                values = tuple(self._learned_records)
            return tuple(record for record in values if self._record_strategy(record) is not None)
        try:
            values = records()
        except Exception as exc:
            error(
                "Learning records read failed",
                {"error": str(exc)},
            )
            return ()
        return tuple(record for record in values if self._record_strategy(record) is not None)

    def _learned_strategy_scores(
        self,
    ) -> dict[str, tuple[int, int, float]]:
        scores: dict[str, tuple[int, int, float]] = {}
        for record in self._learning_records():
            strategy = self._record_strategy(record)
            if strategy is None:
                continue
            count, successes, _ = scores.get(
                strategy,
                (0, 0, 0.0),
            )
            count += 1
            successes += int(self._record_success(record))
            scores[strategy] = (
                count,
                successes,
                successes / count if count else 0.0,
            )
        return scores

    def _ordered_strategies(
        self,
        snapshot: FailureSnapshot,
        excluded: set[str] | None = None,
    ) -> tuple[str, ...]:
        candidates = self._strategy_candidates(snapshot)
        excluded_values = excluded or set()
        scores = self._learned_strategy_scores()
        indexed = tuple(
            (strategy, index)
            for index, strategy in enumerate(candidates)
            if strategy not in excluded_values
        )
        if not self.learned:
            return tuple(strategy for strategy, _ in indexed)

        eligible: list[tuple[str, float, int, int]] = []
        neutral: list[tuple[str, int]] = []
        failed: list[tuple[str, float, int, int]] = []

        for strategy, index in indexed:
            score = scores.get(strategy)
            if score is None or score[0] < self._MIN_LEARNING_SAMPLES:
                neutral.append((strategy, index))
                continue
            success_rate = score[2]
            item = (strategy, success_rate, score[0], index)
            if success_rate <= 0.0:
                failed.append(item)
            else:
                eligible.append(item)

        eligible.sort(
            key=lambda item: (
                -item[1],
                -item[2],
                item[3],
            )
        )
        failed.sort(
            key=lambda item: (
                item[1],
                -item[2],
                item[3],
            )
        )
        return tuple(
            [item[0] for item in eligible]
            + [item[0] for item in neutral]
            + [item[0] for item in failed]
        )

    def strategy_candidates(
        self,
        snapshot: FailureSnapshot,
    ) -> tuple[str, ...]:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        return self._strategy_candidates(snapshot)

    def evaluate_strategies(
        self,
        snapshot: FailureSnapshot,
    ) -> Mapping[str, tuple[int, int, float]]:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        scores = self._learned_strategy_scores()
        return MappingProxyType({
            strategy: scores.get(strategy, (0, 0, 0.0))
            for strategy in self._strategy_candidates(snapshot)
        })

    def _select_strategy(
        self,
        snapshot: FailureSnapshot,
    ) -> str:
        strategies = self._ordered_strategies(snapshot)
        if not strategies:
            raise SelfHealingException("No recovery strategy available")
        strategy = strategies[0]
        default_strategy = self._strategy_candidates(snapshot)[0]
        if strategy != default_strategy:
            scores = self._learned_strategy_scores()
            score = scores.get(strategy)
            info(
                "Learning strategy selected",
                {
                    "strategy": strategy,
                    "default_strategy": default_strategy,
                    "success_rate": (score[2] if score is not None else 0.0),
                    "samples": score[0] if score is not None else 0,
                },
            )
        return strategy

    def select_strategy(
        self,
        snapshot: FailureSnapshot,
    ) -> str:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        return self._select_strategy(snapshot)

    def recover_with_strategy(
        self,
        snapshot: FailureSnapshot,
        strategy: str,
    ) -> Any:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        if not isinstance(strategy, str) or not strategy.strip():
            raise ValueError("strategy must not be empty")
        if strategy not in self._strategy_candidates(snapshot):
            raise SelfHealingException(f"Unknown recovery strategy: {strategy}")
        plan = RecoveryPlan.create(strategy, self._strategy_action(strategy))
        return self.recover(snapshot, plan)

    def plan_recovery(
        self,
        snapshot: FailureSnapshot,
    ) -> RecoveryPlan:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        strategy = self._select_strategy(snapshot)
        action = self._strategy_action(strategy)
        plan = RecoveryPlan.create(strategy, action)
        with self._lock:
            self._last_plan = plan
        info(
            "Recovery plan created",
            {
                "strategy": plan.strategy,
                "trace_id": snapshot.trace_id,
                "plan_id": plan.trace_id,
            },
        )
        self._publish(
            "RecoveryPlanned",
            EventType.CREATED,
            {
                "recovery_id": plan.trace_id,
                "failure_id": snapshot.trace_id,
                "strategy": plan.strategy,
            },
            snapshot,
        )
        return plan

    def _record_attempt(
        self,
        attempt: int,
        strategy: str,
        success: bool,
        result: Any = None,
        recovery_error: Exception | None = None,
    ) -> RecoveryAttempt:
        record = RecoveryAttempt(
            attempt=attempt,
            strategy=strategy,
            success=success,
            timestamp=iso(datetime.now(UTC)),
            result=result,
            error=(None if recovery_error is None else str(recovery_error)),
        )
        with self._lock:
            self._attempts.append(record)
        return record

    def _execute_plan(
        self,
        snapshot: FailureSnapshot,
        plan: RecoveryPlan,
        attempt: int,
    ) -> Any:
        try:
            result = plan.execute(snapshot)
        except Exception as exc:
            self._record_attempt(
                attempt,
                plan.strategy,
                False,
                recovery_error=exc,
            )
            self._learn(
                snapshot,
                plan,
                attempt=attempt,
                success=False,
                result=None,
                recovery_error=exc,
            )
            raise

        self._record_attempt(
            attempt,
            plan.strategy,
            True,
            result=result,
        )
        self._learn(
            snapshot,
            plan,
            attempt=attempt,
            success=True,
            result=result,
        )
        return result

    def recover(
        self,
        snapshot: FailureSnapshot,
        plan: RecoveryPlan | None = None,
    ) -> Any:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        if plan is None:
            plan = self.plan_recovery(snapshot)
        elif not isinstance(plan, RecoveryPlan):
            raise TypeError("plan must be a RecoveryPlan or None")
        self._publish(
            "RecoveryStarted",
            EventType.START,
            {
                "recovery_id": plan.trace_id,
                "failure_id": snapshot.trace_id,
                "strategy": plan.strategy,
            },
            snapshot,
        )
        try:
            result = self._execute_plan(snapshot, plan, 1)
        except SH3Exception as exc:
            with self._lock:
                self._failed += 1
            self._publish(
                "RecoveryFailed",
                EventType.FAILURE,
                {
                    "recovery_id": plan.trace_id,
                    "failure_id": snapshot.trace_id,
                    "strategy": plan.strategy,
                    "error": str(exc),
                    "details": {
                        "error_type": type(exc).__name__,
                    },
                    "success": False,
                },
                context=self._propagation_context,
            )
            raise
        except Exception as exc:
            with self._lock:
                self._failed += 1
            self._publish(
                "RecoveryFailed",
                EventType.FAILURE,
                {
                    "recovery_id": plan.trace_id,
                    "failure_id": snapshot.trace_id,
                    "strategy": plan.strategy,
                    "error": str(exc),
                    "details": {
                        "error_type": type(exc).__name__,
                    },
                },
                context=self._propagation_context,
            )
            wrapped = SelfHealingException(f"Recovery failed: {plan.strategy}")
            error(
                "Recovery failed",
                {
                    "strategy": plan.strategy,
                    "trace_id": snapshot.trace_id,
                    "error": str(exc),
                },
            )
            raise wrapped from exc

        with self._lock:
            self._recovered += 1
            self._last_result = result

        self._publish(
            "RecoveryCompleted",
            EventType.COMPLETE,
            {
                "recovery_id": plan.trace_id,
                "failure_id": snapshot.trace_id,
                "strategy": plan.strategy,
                "success": True,
                "details": result,
            },
            context=self._propagation_context,
        )
        info(
            "Recovery successful",
            {
                "strategy": plan.strategy,
                "trace_id": snapshot.trace_id,
            },
        )
        return result

    def recover_with_learning(
        self,
        snapshot: FailureSnapshot,
        max_attempts: int = 1,
    ) -> Any:
        if not isinstance(snapshot, FailureSnapshot):
            raise TypeError("snapshot must be a FailureSnapshot")
        if not isinstance(max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        with self._lock:
            self._attempts.clear()

        strategies = self._ordered_strategies(snapshot)
        if not strategies:
            raise SelfHealingException("No recovery strategy available")

        last_error: Exception | None = None

        for attempt, strategy in enumerate(
            strategies[:max_attempts],
            start=1,
        ):
            plan = RecoveryPlan.create(
                strategy,
                self._strategy_action(strategy),
            )
            with self._lock:
                self._last_plan = plan

            self._publish(
                "RecoveryPlanned",
                EventType.CREATED,
                {
                    "recovery_id": plan.trace_id,
                    "failure_id": snapshot.trace_id,
                    "strategy": strategy,
                },
                snapshot,
            )
            self._publish(
                "RecoveryStarted",
                EventType.START,
                {
                    "recovery_id": plan.trace_id,
                    "failure_id": snapshot.trace_id,
                    "strategy": strategy,
                },
                snapshot,
            )

            try:
                result = self._execute_plan(
                    snapshot,
                    plan,
                    attempt,
                )
            except Exception as exc:
                last_error = exc
                self._publish(
                    "RecoveryFailed",
                    EventType.FAILURE,
                    {
                        "recovery_id": plan.trace_id,
                        "failure_id": snapshot.trace_id,
                        "strategy": plan.strategy,
                        "error": str(exc),
                        "details": {
                            "error_type": type(exc).__name__,
                        },
                    },
                    snapshot,
                )
                error(
                    "Recovery attempt failed",
                    {
                        "attempt": attempt,
                        "strategy": strategy,
                        "trace_id": snapshot.trace_id,
                        "error": str(exc),
                    },
                )
                continue

            with self._lock:
                self._recovered += 1
                self._last_result = result

            self._publish(
                "RecoveryCompleted",
                EventType.COMPLETE,
                {
                    "recovery_id": plan.trace_id,
                    "failure_id": snapshot.trace_id,
                    "strategy": strategy,
                    "success": True,
                    "details": result,
                },
                snapshot,
            )

            info(
                "Learning recovery successful",
                {
                    "attempt": attempt,
                    "strategy": strategy,
                    "trace_id": snapshot.trace_id,
                },
            )
            return result

        with self._lock:
            self._failed += 1

        if last_error is None:
            raise SelfHealingException("Recovery failed without an available attempt")

        if isinstance(last_error, SH3Exception):
            raise last_error

        raise SelfHealingException(
            f"All recovery attempts failed: {snapshot.trace_id}"
        ) from last_error

    def _learn(
        self,
        snapshot: FailureSnapshot,
        plan: RecoveryPlan,
        *,
        attempt: int,
        success: bool,
        result: Any = None,
        recovery_error: Exception | None = None,
    ) -> None:
        score = 1.0 if success else 0.0
        details = {
            **dict(snapshot.context),
            "trace_id": snapshot.trace_id,
            "strategy": plan.strategy,
            "attempt": attempt,
            "snapshot_trace_id": snapshot.trace_id,
            "plan_id": plan.trace_id,
            "error_type": type(snapshot.error).__name__,
            "recovery_result": result,
            "snapshot_context": dict(snapshot.context),
            "recovery_error": str(recovery_error) if recovery_error is not None else None,
        }

        publisher = self._event_publisher
        if publisher is None:
            learning = self.learning
            record = getattr(learning, "record", None) if learning is not None else None
            if callable(record):
                try:
                    record(
                        "self_healing.recovery",
                        score,
                        success=success,
                        details=details,
                    )
                except Exception as exc:
                    info(
                        "Self-healing learning record failed",
                        {
                            "strategy": plan.strategy,
                            "trace_id": snapshot.trace_id,
                            "error": str(exc),
                        },
                    )
            return

        self._publish(
            "HealingFeedbackRecorded",
            EventType.CREATED,
            {
                "recovery_id": plan.trace_id,
                "success": success,
                "strategy": plan.strategy,
                "feedback": {
                    "attempt": attempt,
                    "score": score,
                    "error_type": type(snapshot.error).__name__,
                    "recovery_error": str(recovery_error) if recovery_error is not None else None,
                    "details": details,
                },
            },
            snapshot,
        )


    @property
    def learned(self) -> bool:
        learning = self.learning
        if learning is not None:
            return callable(getattr(learning, "record", None)) and callable(
                getattr(learning, "records", None)
            )
        with self._lock:
            return bool(self._learned_records)

    def learning_records(self) -> tuple[Any, ...]:
        return self._learning_records()

    def learning_summary(self) -> dict[str, Any]:
        records = self._learning_records()
        strategies: dict[str, dict[str, Any]] = {}

        for record in records:
            strategy = self._record_strategy(record)
            if strategy is None:
                continue
            entry = strategies.setdefault(
                strategy,
                {
                    "count": 0,
                    "successes": 0,
                    "failures": 0,
                    "success_rate": 0.0,
                },
            )
            entry["count"] += 1
            if self._record_success(record):
                entry["successes"] += 1
            else:
                entry["failures"] += 1

        for entry in strategies.values():
            count = entry["count"]
            entry["success_rate"] = entry["successes"] / count if count else 0.0

        total = len(records)
        successes = sum(self._record_success(record) for record in records)

        return {
            "enabled": self.learned,
            "record_count": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total else 0.0,
            "strategies": strategies,
        }

    @property
    def attempts(self) -> tuple[RecoveryAttempt, ...]:
        with self._lock:
            return tuple(self._attempts)

    @property
    def attempt_count(self) -> int:
        with self._lock:
            return len(self._attempts)

    def _retry(self, snapshot: FailureSnapshot) -> dict[str, Any]:
        info("Retry strategy executed", {"trace_id": snapshot.trace_id})
        return {
            "status": "retried",
            "strategy": "retry_safe",
            "trace_id": snapshot.trace_id,
        }

    def _fallback(self, snapshot: FailureSnapshot) -> dict[str, Any]:
        info("Fallback strategy executed", {"trace_id": snapshot.trace_id})
        return {
            "status": "fallback_used",
            "strategy": "fallback_default",
            "trace_id": snapshot.trace_id,
        }

    def _rebuild(self, snapshot: FailureSnapshot) -> dict[str, Any]:
        rebuilt = False
        manager = self.context_manager
        if manager is not None:
            clear = getattr(manager, "clear", None)
            if callable(clear):
                clear()
                rebuilt = True

        info(
            "Rebuild strategy executed",
            {
                "trace_id": snapshot.trace_id,
                "context_rebuilt": rebuilt,
            },
        )
        return {
            "status": "context_rebuilt",
            "strategy": "rebuild_context",
            "trace_id": snapshot.trace_id,
            "context_rebuilt": rebuilt,
        }

    def execute_safe(
        self,
        fn: Callable[..., Any],
        *args: Any,
        context: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if not callable(fn):
            raise TypeError("fn must be callable")
        ctx = dict(context or {})
        try:
            return fn(*args, **kwargs)
        except SH3Exception as exc:
            snapshot = self.detect(exc, ctx)
            return self.recover(snapshot)
        except Exception as exc:
            snapshot = self.detect(exc, ctx)
            return self.recover(snapshot)

    @property
    def detected(self) -> int:
        with self._lock:
            return self._detected

    @property
    def recovered(self) -> int:
        with self._lock:
            return self._recovered

    @property
    def failed(self) -> int:
        with self._lock:
            return self._failed

    @property
    def last_failure(self) -> FailureSnapshot | None:
        with self._lock:
            return self._last_failure

    @property
    def last_plan(self) -> RecoveryPlan | None:
        with self._lock:
            return self._last_plan

    @property
    def last_result(self) -> Any:
        with self._lock:
            return self._last_result

    def reset(self) -> None:
        with self._lock:
            self._detected = 0
            self._recovered = 0
            self._failed = 0
            self._last_failure = None
            self._last_plan = None
            self._last_result = None
            self._attempts.clear()
            self._last_event_id = None
        info("Self-healing state reset")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            failure = self._last_failure
            plan = self._last_plan
            result = {
                "detected": self._detected,
                "recovered": self._recovered,
                "failed": self._failed,
                "last_failure": (None if failure is None else failure.to_dict()),
                "last_plan": (None if plan is None else plan.to_dict()),
                "last_result": self._last_result,
                "attempt_count": len(self._attempts),
                "attempts": [attempt.to_dict() for attempt in self._attempts],
            }

        result["learning"] = self.learning_summary()
        return result


    @property
    def propagation_context(self) -> EventPropagationContext | None:
        return self._propagation_context

    def set_propagation_context(
        self,
        context: EventPropagationContext | None,
    ) -> None:
        if context is not None and not isinstance(context, EventPropagationContext):
            raise TypeError("context must be EventPropagationContext or None")
        self._propagation_context = context
