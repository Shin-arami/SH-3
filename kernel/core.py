from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cognition.core import CognitionCore
from cognition.memory import MemoryCore
from cognition.planner import Planner
from cognition.policy import PolicyEngine
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.types.identifiers import IdentifierGenerator
from foundation.utils.exceptions import KernelException, SH3Exception
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events import Event, EventPropagationContext
from runtime.context_manager import ContextManager
from runtime.core import RuntimeCore

__all__ = ["SH3Kernel"]


class SH3Kernel:
    __slots__ = (
        "_event_publisher",
        "_last_event_id",
        "_propagation_context",
        "cognition",
        "context_manager",
        "kernel_id",
        "learning_loop",
        "memory",
        "meta_controller",
        "planner",
        "policy",
        "runtime",
        "system_optimizer",
    )

    def __init__(
        self,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._event_publisher = event_publisher
        self._last_event_id: str | None = None
        self._propagation_context: EventPropagationContext | None = None

        self.runtime = RuntimeCore(event_publisher=event_publisher)
        self.context_manager = ContextManager()
        self.cognition = CognitionCore(self.context_manager)
        self.planner = Planner()
        self.policy = PolicyEngine()
        self.memory = MemoryCore()

        from kernel.learning_loop import LearningLoop
        from kernel.meta_controller import MetaController
        from kernel.system_optimizer import SystemOptimizer

        self.learning_loop = LearningLoop(
            self,
            event_publisher=event_publisher,
        )
        self.meta_controller = MetaController(
            self,
            event_publisher=event_publisher,
        )
        self.system_optimizer = SystemOptimizer(
            self,
            event_publisher=event_publisher,
        )
        self.kernel_id = short_id("sh3-kernel")

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must implement EventPublisher")

        self._event_publisher = publisher
        self.runtime.set_event_publisher(publisher)
        self.learning_loop.set_event_publisher(publisher)
        self.meta_controller.set_event_publisher(publisher)
        self.system_optimizer.set_event_publisher(publisher)

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
        self.learning_loop.set_propagation_context(context)
        self.meta_controller.set_propagation_context(context)
        self.system_optimizer.set_propagation_context(context)

    def _new_propagation(
        self,
        context: EventPropagationContext | None = None,
    ) -> EventPropagationContext:
        if context is not None:
            return context

        if self._propagation_context is not None:
            return self._propagation_context

        return EventPropagationContext.create(
            correlation_id=f"kernel:{self.kernel_id}",
            trace_id=self.context_manager.get("trace_id"),
            tenant_id=self.context_manager.get("tenant_id"),
        )

    def _publish(
        self,
        event_name: str,
        payload: dict[str, Any],
        event_type: EventType,
        context: EventPropagationContext,
    ) -> EventPropagationContext:
        publisher = self._event_publisher
        if publisher is None:
            return context

        try:
            event = Event.create(
                event_name=event_name,
                producer=self.kernel_id,
                payload=payload,
                category=Category.LIFECYCLE,
                event_type=event_type,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                tenant_id=context.tenant_id,
            )
            publisher.publish(event)
            self._last_event_id = event.metadata.event_id
            next_context = context.next(event.metadata.event_id)
            self._propagation_context = next_context
            return next_context
        except Exception as exc:
            error("Kernel event publication failed", {"error": str(exc)})
            return context

    @staticmethod
    def _validate_goal(goal: str) -> str:
        if not isinstance(goal, str):
            raise TypeError("goal must be str")
        if not goal.strip():
            raise ValueError("goal must not be empty")
        return goal

    def execute(
        self,
        goal: str,
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        goal = self._validate_goal(goal)
        propagation = self._new_propagation(context)
        self._propagation_context = propagation
        self.context_manager.push("kernel")
        cycle_id = IdentifierGenerator.entity()

        try:
            info(
                "Kernel execution started",
                {"goal": goal, "kernel_id": self.kernel_id},
            )

            propagation = self._publish(
                "KernelCycleStarted",
                {
                    "cycle_id": cycle_id,
                    "kernel_id": self.kernel_id,
                    "goal": goal,
                },
                EventType.START,
                propagation,
            )
            cycle_id = propagation.causation_id or cycle_id

            cognition = self.cognition.run(goal)
            plan = self.planner.build_plan(goal)
            decision = self.policy.decide(plan["goal"])

            memory_key = self.memory.write(
                key=short_id(goal),
                value={
                    "goal": goal,
                    "cognition": cognition,
                    "plan": plan,
                    "decision": decision,
                },
                tags=["kernel", "execution"],
            )

            self.context_manager.set("last_execution", memory_key)

            result = {
                "kernel_id": self.kernel_id,
                "goal": goal,
                "cognition": cognition,
                "plan": plan,
                "decision": decision,
                "memory_key": memory_key,
            }

            self._publish(
                "KernelCycleCompleted",
                {
                    "cycle_id": cycle_id,
                    "kernel_id": self.kernel_id,
                    "goal": goal,
                    "memory_key": memory_key,
                    "success": True,
                },
                EventType.COMPLETE,
                propagation,
            )

            info(
                "Kernel execution completed",
                {"memory_key": memory_key},
            )
            return result

        except SH3Exception as exc:
            self._publish(
                "KernelCycleFailed",
                {
                    "cycle_id": cycle_id,
                    "kernel_id": self.kernel_id,
                    "goal": goal,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "success": False,
                },
                EventType.FAILURE,
                propagation,
            )
            raise
        except Exception as exc:
            wrapped = KernelException(str(exc))
            error("Kernel unhandled exception", wrapped.to_dict())
            self._publish(
                "KernelCycleFailed",
                {
                    "cycle_id": cycle_id,
                    "kernel_id": self.kernel_id,
                    "goal": goal,
                    "error": str(wrapped),
                    "error_type": type(exc).__name__,
                    "success": False,
                },
                EventType.FAILURE,
                propagation,
            )
            raise wrapped from exc
        finally:
            self.context_manager.pop()

    def step(
        self,
        goal: str,
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        goal = self._validate_goal(goal)
        self._propagation_context = self._new_propagation(context)
        self.context_manager.push("kernel-step")

        try:
            cognitive_state = self.cognition.create_state(goal)
            plan = self.planner.build_plan(goal)

            return {
                "goal": goal,
                "cognitive_state": cognitive_state.to_dict(),
                "plan": plan,
            }
        finally:
            self.context_manager.pop()

    def learning_cycle(
        self,
        execution_result: dict[str, Any],
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        if not isinstance(execution_result, dict):
            raise TypeError("execution_result must be dict")
        propagation = self._new_propagation(context)
        self._propagation_context = propagation
        return self.learning_loop.run(
            execution_result,
            context=propagation,
        )

    def meta_cycle(
        self,
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        propagation = self._new_propagation(context)
        self._propagation_context = propagation
        return self.meta_controller.run_cycle(context=propagation)

    def optimize(
        self,
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        propagation = self._new_propagation(context)
        self._propagation_context = propagation
        self.system_optimizer.set_propagation_context(propagation)
        return self.system_optimizer.optimize(context=propagation)

    def recover(
        self,
        exc: Exception,
        context: dict[str, Any] | None = None,
    ) -> Any:
        snapshot = self.meta_controller.healer.detect(exc, context or {})
        return self.meta_controller.healer.recover(snapshot)

    def execute_safe(
        self,
        fn: Callable[..., Any],
        *args: Any,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self.meta_controller.healer.execute_safe(
            fn,
            *args,
            context=context,
            **kwargs,
        )

    def add_policy(self, rule: Any) -> None:
        self.policy.add_rule(rule)

    def recall(self, key: str) -> Any:
        return self.memory.read(key)

    def history(self, limit: int = 10) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be int")
        if limit < 0:
            raise ValueError("limit must be >= 0")
        return self.memory.timeline(limit)

    def snapshot(self) -> dict[str, Any]:
        return {
            "kernel_id": self.kernel_id,
            "context": self.context_manager.snapshot(),
            "memory": self.history(limit=100),
            "policy_rules": len(self.policy.rules),
            "learning_loop_id": self.learning_loop.loop_id,
            "meta_controller_id": self.meta_controller.meta_id,
            "system_optimizer_id": self.system_optimizer.optimizer_id,
        }
