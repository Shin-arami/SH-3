from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from foundation.enums import Severity
from foundation.utils.exceptions import SH3Exception

from .base import Service
from .health import HealthState, HealthStatus

__all__ = [
    "HealingAction",
    "HealingException",
    "HealingResult",
    "HealingService",
]


class HealingException(SH3Exception):
    """Healing operation failure."""


@dataclass(frozen=True, slots=True)
class HealingAction:
    name: str
    handler: Callable[[Mapping[str, Any]], Any]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not callable(self.handler):
            raise TypeError("handler must be callable")

    def execute(self, context: Mapping[str, Any]) -> Any:
        return self.handler(context)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class HealingResult:
    failure: str
    action: str
    success: bool
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure": self.failure,
            "action": self.action,
            "success": self.success,
            "result": self.result,
            "error": self.error,
        }


class HealingService(Service):
    __slots__ = (
        "_actions",
        "_failures",
        "_history",
        "_last_result",
        "_started",
    )

    def __init__(self, name: str = "healing") -> None:
        super().__init__(name)
        self._actions: dict[str, HealingAction] = {}
        self._failures: dict[str, dict[str, Any]] = {}
        self._history: list[HealingResult] = []
        self._last_result: HealingResult | None = None
        self._started = False

    def _on_start(self) -> None:
        with self._lock:
            self._started = True

    def _on_suspend(self) -> None:
        with self._lock:
            self._started = False

    def _on_resume(self) -> None:
        with self._lock:
            self._started = True

    def _on_terminate(self) -> None:
        with self._lock:
            self._started = False
            self._last_result = None

    def register_action(
        self,
        action: HealingAction,
    ) -> None:
        if not isinstance(action, HealingAction):
            raise TypeError("action must be a HealingAction")
        with self._lock:
            self._actions[action.name] = action

    def unregister_action(self, name: str) -> HealingAction | None:
        with self._lock:
            return self._actions.pop(name, None)

    def get_action(self, name: str) -> HealingAction | None:
        with self._lock:
            return self._actions.get(name)

    def has_action(self, name: str) -> bool:
        with self._lock:
            return name in self._actions

    @property
    def actions(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._actions)

    def register_failure(
        self,
        failure: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if not failure or not failure.strip():
            raise ValueError("failure must not be empty")
        with self._lock:
            self._failures[failure] = dict(context or {})

    def clear_failure(self, failure: str) -> bool:
        with self._lock:
            return self._failures.pop(failure, None) is not None

    def has_failure(self, failure: str) -> bool:
        with self._lock:
            return failure in self._failures

    @property
    def failures(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._failures)

    def heal(
        self,
        failure: str,
        action: str,
        context: Mapping[str, Any] | None = None,
    ) -> HealingResult:
        if not failure or not failure.strip():
            raise ValueError("failure must not be empty")
        if not action or not action.strip():
            raise ValueError("action must not be empty")

        with self._lock:
            healing_action = self._actions.get(action)
            stored_context = dict(self._failures.get(failure, {}))

        if healing_action is None:
            raise HealingException(f"Unknown healing action: {action}")

        stored_context.update(context or {})

        try:
            value = healing_action.execute(stored_context)
            result = HealingResult(
                failure=failure,
                action=action,
                success=True,
                result=value,
            )
        except Exception as exc:
            result = HealingResult(
                failure=failure,
                action=action,
                success=False,
                error=str(exc),
            )

        with self._lock:
            self._history.append(result)
            self._last_result = result
            if result.success:
                self._failures.pop(failure, None)

        return result

    def execute(
        self,
        failure: str,
        action: str,
        context: Mapping[str, Any] | None = None,
    ) -> HealingResult:
        return self.heal(failure, action, context)

    @property
    def history(self) -> tuple[HealingResult, ...]:
        with self._lock:
            return tuple(self._history)

    @property
    def last_result(self) -> HealingResult | None:
        with self._lock:
            return self._last_result

    @property
    def successful_healings(self) -> int:
        with self._lock:
            return sum(result.success for result in self._history)

    @property
    def failed_healings(self) -> int:
        with self._lock:
            return sum(not result.success for result in self._history)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._history.clear()
            self._last_result = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "started": self._started,
                "actions": tuple(self._actions),
                "failures": tuple(self._failures),
                "history": [result.to_dict() for result in self._history],
                "last_result": (None if self._last_result is None else self._last_result.to_dict()),
            }

    def health(self) -> HealthStatus:
        with self._lock:
            started = self._started
            failures = len(self._failures)
            history = len(self._history)

        if self.terminated:
            return HealthStatus.create(
                HealthState.UNHEALTHY,
                "Healing service is terminated",
                {"failures": failures, "history": history},
                self.name,
                Severity.HIGH,
            )

        if self.suspended:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Healing service is suspended",
                {"failures": failures, "history": history},
                self.name,
                Severity.MEDIUM,
            )

        if started and failures == 0:
            return HealthStatus.create(
                HealthState.HEALTHY,
                "Healing service is active",
                {"failures": failures, "history": history},
                self.name,
                Severity.INFO,
            )

        if started:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Healing service has unresolved failures",
                {"failures": failures, "history": history},
                self.name,
                Severity.MEDIUM,
            )

        return HealthStatus.create(
            HealthState.UNKNOWN,
            "Healing service is not active",
            {"failures": failures, "history": history},
            self.name,
            Severity.LOW,
        )
