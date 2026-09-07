from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType
from typing import Any

from foundation.utils.exceptions import SH3Exception

from .base import Service

__all__ = ["Plan", "PlanStep", "PlannerException", "PlannerService"]


class PlannerException(SH3Exception):
    """Planner service failure."""


@dataclass(frozen=True, slots=True)
class PlanStep:
    name: str
    action: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.action or not self.action.strip():
            raise ValueError("action must not be empty")
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType(dict(self.parameters)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "action": self.action,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True, slots=True)
class Plan:
    name: str
    goal: str
    steps: tuple[PlanStep, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.goal or not self.goal.strip():
            raise ValueError("goal must not be empty")
        object.__setattr__(
            self,
            "steps",
            tuple(self.steps),
        )
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": dict(self.metadata),
        }


class PlannerService(Service):
    __slots__ = ("_planner_lock", "_plans")

    def __init__(self, name: str = "planner") -> None:
        super().__init__(name)
        self._plans: dict[str, Plan] = {}
        self._planner_lock = RLock()

    def _on_start(self) -> None:
        return None

    def _on_suspend(self) -> None:
        return None

    def _on_resume(self) -> None:
        return None

    def _on_terminate(self) -> None:
        with self._planner_lock:
            self._plans.clear()

    def create_plan(
        self,
        name: str,
        goal: str,
        steps: tuple[PlanStep, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> Plan:
        if not self.active:
            raise PlannerException(f"Planner service '{self.name}' is not active")
        plan = Plan(
            name=name,
            goal=goal,
            steps=steps,
            metadata=metadata or {},
        )
        with self._planner_lock:
            if plan.name in self._plans:
                raise PlannerException(f"Plan already exists: {plan.name}")
            self._plans[plan.name] = plan
        return plan

    def get_plan(self, name: str) -> Plan | None:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        with self._planner_lock:
            return self._plans.get(name)

    def remove_plan(self, name: str) -> Plan | None:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        with self._planner_lock:
            return self._plans.pop(name, None)

    def clear(self) -> None:
        with self._planner_lock:
            self._plans.clear()

    def plans(self) -> tuple[Plan, ...]:
        with self._planner_lock:
            return tuple(self._plans.values())

    def plan_count(self) -> int:
        with self._planner_lock:
            return len(self._plans)

    def snapshot(self) -> dict[str, Any]:
        with self._planner_lock:
            plans = tuple(self._plans.values())
        snapshot = super().snapshot()
        snapshot.update(
            {
                "plan_count": len(plans),
                "plans": [plan.to_dict() for plan in plans],
            }
        )
        return snapshot
