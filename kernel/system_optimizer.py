from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import RLock, local
from typing import Any

from cognition.memory import MemoryCore
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events import EventPropagationContext
from infrastructure.events.model import Event
from kernel.core import SH3Kernel

__all__ = ["OptimizationAction", "OptimizationActionResult", "SystemOptimizer"]


@dataclass(frozen=True, slots=True)
class OptimizationAction:
    name: str
    apply: Callable[[Mapping[str, Any]], Any]
    rollback: Callable[[Any], Any]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not callable(self.apply):
            raise TypeError("apply must be callable")
        if not callable(self.rollback):
            raise TypeError("rollback must be callable")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description}


@dataclass(frozen=True, slots=True)
class OptimizationActionResult:
    action: str
    success: bool
    result: Any = None
    rolled_back: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "success": self.success,
            "result": self.result,
            "rolled_back": self.rolled_back,
            "error": self.error,
        }


class SystemOptimizer:
    __slots__ = (
        "_actions",
        "_event_publisher",
        "_history",
        "_last_event_id",
        "_last_propagation_context",
        "_lock",
        "_propagation_context_local",
        "kernel",
        "memory",
        "optimizer_id",
    )

    def __init__(
        self,
        kernel: SH3Kernel,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.kernel = kernel
        self.memory: MemoryCore = kernel.memory
        self.optimizer_id = short_id("system-optimizer")
        self._event_publisher = event_publisher
        self._last_event_id: str | None = None
        self._propagation_context_local = local()
        self._last_propagation_context: EventPropagationContext | None = None
        self._actions: dict[str, OptimizationAction] = {}
        self._history: list[OptimizationActionResult] = []
        self._lock = RLock()
        self._register_default_actions()

    @property
    def _propagation_context(self) -> EventPropagationContext | None:
        if hasattr(self._propagation_context_local, "value"):
            value = self._propagation_context_local.value
            return value if isinstance(value, EventPropagationContext) else None
        with self._lock:
            return self._last_propagation_context

    @_propagation_context.setter
    def _propagation_context(
        self,
        context: EventPropagationContext | None,
    ) -> None:
        self._propagation_context_local.value = context
        with self._lock:
            self._last_propagation_context = context

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

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        self._event_publisher = publisher

    def register_action(self, action: OptimizationAction, *, replace: bool = False) -> None:
        if not isinstance(action, OptimizationAction):
            raise TypeError("action must be OptimizationAction")
        with self._lock:
            if action.name in self._actions and not replace:
                raise KeyError(f"optimization action already registered: {action.name}")
            self._actions[action.name] = action

    def unregister_action(self, name: str) -> OptimizationAction | None:
        with self._lock:
            return self._actions.pop(name, None)

    def get_action(self, name: str) -> OptimizationAction | None:
        with self._lock:
            return self._actions.get(name)

    @property
    def actions(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._actions))

    @property
    def history(self) -> tuple[OptimizationActionResult, ...]:
        with self._lock:
            return tuple(self._history)

    def _register_default_actions(self) -> None:
        self.register_action(
            OptimizationAction(
                "reduce_context_depth",
                self._apply_reduce_context_depth,
                self._rollback_context,
                "Reduce one runtime context level.",
            )
        )
        self.register_action(
            OptimizationAction(
                "compress_memory",
                self._apply_compress_memory,
                self._rollback_noop,
                "Create a deterministic compressed memory view.",
            )
        )
        self.register_action(
            OptimizationAction(
                "simplify_policy",
                self._apply_simplify_policy,
                self._rollback_policy,
                "Remove the lowest-weight policy rule.",
            )
        )

    def _apply_reduce_context_depth(self, _: Mapping[str, Any]) -> dict[str, Any]:
        context = self.kernel.context_manager.pop()
        if context is None:
            return {"changed": False, "depth": 0, "context": None}
        return {"changed": True, "depth": len(self.kernel.context_manager), "context": context.to_dict()}

    def _rollback_context(self, result: Any) -> None:
        if not isinstance(result, Mapping) or not result.get("changed"):
            return
        data = result.get("context")
        if not isinstance(data, Mapping):
            return
        context = self.kernel.context_manager.push(str(data.get("name", "restored")))
        state = data.get("state", {})
        if isinstance(state, Mapping):
            context.update(state)

    def _apply_compress_memory(self, context: Mapping[str, Any]) -> dict[str, Any]:
        group_size = context.get("group_size", 5)
        groups = self.memory.compress(group_size)
        return {"changed": False, "groups": groups, "group_size": group_size}

    @staticmethod
    def _rollback_noop(_: Any) -> None:
        return None

    def _apply_simplify_policy(self, _: Mapping[str, Any]) -> dict[str, Any]:
        rules = self.kernel.policy.rules
        if not rules:
            return {"changed": False, "rule": None}
        index, rule = min(enumerate(rules), key=lambda item: (item[1].weight, item[0]))
        rules.pop(index)
        return {"changed": True, "index": index, "rule": rule}

    def _rollback_policy(self, result: Any) -> None:
        if not isinstance(result, Mapping) or not result.get("changed"):
            return
        rule = result.get("rule")
        index = result.get("index")
        if rule is None or not isinstance(index, int):
            return
        rules = self.kernel.policy.rules
        rules.insert(min(index, len(rules)), rule)

    def execute_action(self, name: str, context: Mapping[str, Any] | None = None) -> OptimizationActionResult:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        action = self.get_action(name)
        if action is None:
            raise KeyError(f"unknown optimization action: {name}")
        stored_context = dict(context or {})
        try:
            value = action.apply(stored_context)
            result = OptimizationActionResult(name, True, value)
        except Exception as exc:
            result = OptimizationActionResult(name, False, error=str(exc))
            with self._lock:
                self._history.append(result)
            self._publish("OptimizationFailed", EventType.FAILURE, {"optimization_id": self.optimizer_id, "action": name, "error": str(exc)})
            return result
        with self._lock:
            self._history.append(result)
        return result

    def rollback_action(self, result: OptimizationActionResult) -> OptimizationActionResult:
        if not isinstance(result, OptimizationActionResult):
            raise TypeError("result must be OptimizationActionResult")
        if not result.success or result.rolled_back:
            return result
        action = self.get_action(result.action)
        if action is None:
            raise KeyError(f"unknown optimization action: {result.action}")
        try:
            action.rollback(result.result)
        except Exception as exc:
            failure = OptimizationActionResult(result.action, False, result.result, False, str(exc))
            self._publish("OptimizationFailed", EventType.FAILURE, {"optimization_id": self.optimizer_id, "action": result.action, "error": str(exc), "rollback": True})
            with self._lock:
                self._history.append(failure)
            return failure
        rolled_back = OptimizationActionResult(result.action, True, result.result, True)
        with self._lock:
            self._history.append(rolled_back)
        return rolled_back

    def execute_actions(self, actions: list[str] | tuple[str, ...], context: Mapping[str, Any] | None = None, *, rollback_on_failure: bool = True) -> tuple[OptimizationActionResult, ...]:
        results: list[OptimizationActionResult] = []
        for name in actions:
            result = self.execute_action(name, context)
            results.append(result)
            if not result.success:
                if rollback_on_failure:
                    for previous in reversed(results[:-1]):
                        if previous.success and not previous.rolled_back:
                            self.rollback_action(previous)
                break
        return tuple(results)

    def _publish(
        self,
        event_name: str,
        event_type: EventType,
        payload: dict[str, Any],
    ) -> None:
        publisher = self._event_publisher
        if publisher is None:
            return
        try:
            correlation_id = self._propagation_context.correlation_id if self._propagation_context is not None else self.optimizer_id
            causation_id = self._propagation_context.causation_id if self._propagation_context is not None else self._last_event_id
            trace_id = self._propagation_context.trace_id if self._propagation_context is not None else None
            tenant_id = self._propagation_context.tenant_id if self._propagation_context is not None else None
            event = Event.create(
                event_name=event_name,
                producer="optimizer",
                payload=payload,
                category=Category.ACTION,
                event_type=event_type,
                correlation_id=correlation_id,
                causation_id=causation_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
            )
            publisher.publish(event)
            self._last_event_id = event.metadata.event_id
            self._propagation_context = EventPropagationContext(
                correlation_id=correlation_id,
                causation_id=event.metadata.event_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
            )
        except Exception as exc:
            error(
                "SystemOptimizer event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )

    def snapshot(self) -> dict[str, Any]:
        snap = {
            "context_depth": self.kernel.context_manager.snapshot()["depth"],
            "memory_size": len(self.kernel.history(limit=100)),
            "policy_count": len(self.kernel.policy.rules),
        }

        info("System snapshot created", snap)
        return snap

    def detect_bottlenecks(
        self,
        snapshot: dict[str, Any],
    ) -> dict[str, float]:
        bottlenecks = {
            "context_pressure": snapshot["context_depth"] * 0.15,
            "memory_pressure": snapshot["memory_size"] / 100,
            "policy_complexity": snapshot["policy_count"] / 10,
        }

        info("Bottlenecks detected", bottlenecks)
        return bottlenecks

    def score_modules(self) -> dict[str, float]:
        scores = {
            "runtime": 0.8,
            "cognition": 0.9,
            "policy": 0.7,
            "memory": 0.85,
            "kernel": 0.95,
        }

        info("Module scores computed", scores)
        return scores

    def rebalance(
        self,
        bottlenecks: dict[str, float],
    ) -> dict[str, Any]:
        actions: list[str] = []

        if bottlenecks["context_pressure"] > 1.0:
            actions.append("reduce_context_depth")

        if bottlenecks["memory_pressure"] > 0.8:
            actions.append("compress_memory")

        if bottlenecks["policy_complexity"] > 0.9:
            actions.append("simplify_policy")

        info("Rebalance actions determined", {"actions": actions})

        return {
            "actions": actions,
            "optimizer_id": self.optimizer_id,
        }

    def prune(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        pruned: list[str] = []

        if snapshot["memory_size"] > 80:
            pruned.append("memory:old_experiences")

        if snapshot["policy_count"] > 8:
            pruned.append("policy:weak_rules")

        info("Pruning completed", {"pruned": pruned})

        return {
            "pruned": pruned,
            "optimizer_id": self.optimizer_id,
        }

    def optimize(
        self,
        *,
        context: EventPropagationContext | None = None,
        execute: bool = False,
    ) -> dict[str, Any]:
        if context is not None:
            self.set_propagation_context(context)

        self._publish(
            "OptimizationStarted",
            EventType.START,
            {"optimizer_id": self.optimizer_id},
        )

        snapshot = self.snapshot()
        bottlenecks = self.detect_bottlenecks(snapshot)
        modules = self.score_modules()
        rebalance_actions = self.rebalance(bottlenecks)
        prune_actions = self.prune(snapshot)

        proposed_actions = tuple(rebalance_actions["actions"])
        execution: tuple[OptimizationActionResult, ...] = ()
        if execute:
            execution = self.execute_actions(proposed_actions)
        result = {
            "optimizer_id": self.optimizer_id,
            "snapshot": snapshot,
            "bottlenecks": bottlenecks,
            "module_scores": modules,
            "rebalance": rebalance_actions,
            "prune": prune_actions,
            "execution": tuple(item.to_dict() for item in execution),
        }

        success = all(item.success for item in execution) if execution else True
        if execute:
            self._publish(
                "OptimizationEvaluated",
                EventType.COMPLETE,
                {
                    "optimization_id": self.optimizer_id,
                    "success": success,
                    "actions": len(execution),
                },
            )
        self._publish(
            "OptimizationCompleted" if success else "OptimizationFailed",
            EventType.COMPLETE if success else EventType.FAILURE,
            {
                "optimizer_id": self.optimizer_id,
                "success": success,
                "changes": tuple(item.to_dict() for item in execution),
            },
        )

        info("System optimization completed", result)
        return result
