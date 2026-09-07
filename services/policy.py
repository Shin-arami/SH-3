from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from foundation.enums import Severity
from foundation.utils.exceptions import SH3Exception

from .base import Service
from .health import HealthState, HealthStatus

__all__ = [
    "PolicyDecision",
    "PolicyException",
    "PolicyRule",
    "PolicyService",
]


class PolicyException(SH3Exception):
    """Policy evaluation or registry failure."""


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    policy: str = ""
    reason: str = ""
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "policy": self.policy,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class PolicyRule:
    name: str
    evaluator: Callable[[Mapping[str, Any]], bool]
    description: str = ""
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not callable(self.evaluator):
            raise TypeError("evaluator must be callable")

    def evaluate(self, context: Mapping[str, Any]) -> bool:
        try:
            return bool(self.evaluator(context))
        except Exception as exc:
            raise PolicyException(f"Policy evaluation failed: {self.name}") from exc


class PolicyService(Service):
    __slots__ = ("_default", "_rules", "_started")

    def __init__(
        self,
        name: str = "policy",
        *,
        default: bool = False,
    ) -> None:
        super().__init__(name)
        self._rules: dict[str, PolicyRule] = {}
        self._default = default
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
            self._rules.clear()

    def register(self, rule: PolicyRule) -> None:
        if not isinstance(rule, PolicyRule):
            raise TypeError("rule must be a PolicyRule")
        with self._lock:
            if rule.name in self._rules:
                raise PolicyException(f"Policy already registered: {rule.name}")
            self._rules[rule.name] = rule

    def unregister(self, name: str) -> PolicyRule | None:
        with self._lock:
            return self._rules.pop(name, None)

    def get(self, name: str) -> PolicyRule | None:
        with self._lock:
            return self._rules.get(name)

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._rules

    def list(self) -> tuple[PolicyRule, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._rules.values(),
                    key=lambda rule: (-rule.priority, rule.name),
                )
            )

    def count(self) -> int:
        with self._lock:
            return len(self._rules)

    def evaluate(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> PolicyDecision:
        values = MappingProxyType(dict(context or {}))
        with self._lock:
            rules = tuple(
                sorted(
                    self._rules.values(),
                    key=lambda rule: (-rule.priority, rule.name),
                )
            )
            default = self._default
        for rule in rules:
            if rule.evaluate(values):
                return PolicyDecision(
                    True,
                    rule.name,
                    rule.description or "Policy accepted",
                    {"priority": rule.priority},
                )
        return PolicyDecision(
            default,
            "",
            "Default policy decision",
            {"rules_evaluated": len(rules)},
        )

    def allow(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        return self.evaluate(context).allowed

    def deny(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        return not self.allow(context)

    def health(self) -> HealthStatus:
        with self._lock:
            count = len(self._rules)
            started = self._started
        if self.terminated:
            return HealthStatus.create(
                HealthState.UNHEALTHY,
                "Policy service is terminated",
                {"rules": count},
                self.name,
                Severity.HIGH,
            )
        if self.suspended:
            return HealthStatus.create(
                HealthState.DEGRADED,
                "Policy service is suspended",
                {"rules": count},
                self.name,
                Severity.MEDIUM,
            )
        if started:
            return HealthStatus.create(
                HealthState.HEALTHY,
                "Policy service is active",
                {"rules": count},
                self.name,
                Severity.INFO,
            )
        return HealthStatus.create(
            HealthState.UNKNOWN,
            "Policy service is not active",
            {"rules": count},
            self.name,
            Severity.LOW,
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rules = tuple(
                sorted(
                    self._rules.values(),
                    key=lambda rule: (-rule.priority, rule.name),
                )
            )
            return {
                "name": self.name,
                "state": self.state.value,
                "default": self._default,
                "started": self._started,
                "rules": [
                    {
                        "name": rule.name,
                        "description": rule.description,
                        "priority": rule.priority,
                    }
                    for rule in rules
                ],
                "rule_count": len(rules),
            }
