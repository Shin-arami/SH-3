from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from foundation.utils.exceptions import SH3Exception
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from foundation.utils.time import iso

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
        "_failed",
        "_last_failure",
        "_last_plan",
        "_last_result",
        "_lock",
        "_recovered",
        "context_manager",
        "learning",
        "runtime",
    )

    _MIN_LEARNING_SAMPLES = 3

    def __init__(
        self,
        runtime: Any | None = None,
        context_manager: Any | None = None,
        learning: Any | None = None,
        *,
        learning_service: Any | None = None,
    ) -> None:
        self.runtime = runtime
        self.context_manager = context_manager
        self.learning = learning_service if learning_service is not None else learning
        self._lock = RLock()
        self._detected = 0
        self._recovered = 0
        self._failed = 0
        self._last_failure: FailureSnapshot | None = None
        self._last_plan: RecoveryPlan | None = None
        self._last_result: Any = None
        self._attempts: list[RecoveryAttempt] = []

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
        key = str(getattr(record, "key", ""))
        if key.startswith("self_healing:"):
            strategy = key.removeprefix("self_healing:")
        elif key == "self_healing.recovery":
            details = getattr(record, "details", None)
            if not isinstance(details, Mapping):
                return None
            strategy = str(details.get("strategy", ""))
        else:
            return None
        return strategy if strategy in cls._VALID_STRATEGIES else None

    def _learning_records(self) -> tuple[Any, ...]:
        learning = self.learning
        if learning is None:
            return ()
        records = getattr(learning, "records", None)
        if not callable(records):
            return ()
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
            successes += int(bool(getattr(record, "success", False)))
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

    def recover(self, snapshot: FailureSnapshot) -> Any:
        plan = self.plan_recovery(snapshot)
        try:
            result = self._execute_plan(snapshot, plan, 1)
        except SH3Exception:
            with self._lock:
                self._failed += 1
            raise
        except Exception as exc:
            with self._lock:
                self._failed += 1
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

            try:
                result = self._execute_plan(
                    snapshot,
                    plan,
                    attempt,
                )
            except Exception as exc:
                last_error = exc
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
        result: Any,
        recovery_error: Exception | None = None,
    ) -> None:
        learning = self.learning
        if learning is None:
            return
        record = getattr(learning, "record", None)
        if not callable(record):
            return

        details: dict[str, Any] = {
            "strategy": plan.strategy,
            "attempt": attempt,
            "trace_id": snapshot.trace_id,
            "plan_id": plan.trace_id,
            "error_type": type(snapshot.error).__name__,
            # "failure_context": dict(snapshot.context),
            "recovery_result": result,
            **dict(snapshot.context),
        }
        if recovery_error is not None:
            details["recovery_error"] = str(recovery_error)

        try:
            record(
                "self_healing.recovery",
                1.0 if success else 0.0,
                success=success,
                details=details,
            )
        except Exception as exc:
            error(
                "Learning record failed",
                {
                    "strategy": plan.strategy,
                    "trace_id": snapshot.trace_id,
                    "attempt": attempt,
                    "error": str(exc),
                },
            )

    @property
    def learned(self) -> bool:
        learning = self.learning
        if learning is None:
            return False
        return callable(getattr(learning, "record", None)) and callable(
            getattr(learning, "records", None)
        )

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
            if bool(getattr(record, "success", False)):
                entry["successes"] += 1
            else:
                entry["failures"] += 1

        for entry in strategies.values():
            count = entry["count"]
            entry["success_rate"] = entry["successes"] / count if count else 0.0

        total = len(records)
        successes = sum(bool(getattr(record, "success", False)) for record in records)

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
