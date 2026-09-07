from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from cognition.core import CognitionCore
from cognition.memory import MemoryCore
from cognition.planner import Planner
from cognition.policy import PolicyEngine
from foundation.utils.exceptions import KernelException, SH3Exception
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from runtime.context_manager import ContextManager
from runtime.core import RuntimeCore

if TYPE_CHECKING:
    pass

__all__ = ["SH3Kernel"]


class SH3Kernel:
    __slots__ = (
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

    def __init__(self) -> None:
        self.runtime = RuntimeCore()
        self.context_manager = ContextManager()
        self.cognition = CognitionCore(self.context_manager)
        self.planner = Planner()
        self.policy = PolicyEngine()
        self.memory = MemoryCore()

        from kernel.learning_loop import LearningLoop
        from kernel.meta_controller import MetaController
        from kernel.system_optimizer import SystemOptimizer

        self.learning_loop = LearningLoop(self)
        self.meta_controller = MetaController(self)
        self.system_optimizer = SystemOptimizer(self)
        self.kernel_id = short_id("sh3-kernel")

    @staticmethod
    def _validate_goal(goal: str) -> str:
        if not isinstance(goal, str):
            raise TypeError("goal must be str")
        if not goal.strip():
            raise ValueError("goal must not be empty")
        return goal

    def execute(self, goal: str) -> dict[str, Any]:
        goal = self._validate_goal(goal)
        self.context_manager.push("kernel")

        try:
            info(
                "Kernel execution started",
                {"goal": goal, "kernel_id": self.kernel_id},
            )

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

            info(
                "Kernel execution completed",
                {"memory_key": memory_key},
            )
            return result

        except SH3Exception:
            raise
        except Exception as exc:
            wrapped = KernelException(str(exc))
            error("Kernel unhandled exception", wrapped.to_dict())
            raise wrapped from exc
        finally:
            self.context_manager.pop()

    def step(self, goal: str) -> dict[str, Any]:
        goal = self._validate_goal(goal)
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
    ) -> dict[str, Any]:
        if not isinstance(execution_result, dict):
            raise TypeError("execution_result must be dict")
        return self.learning_loop.run(execution_result)

    def meta_cycle(self) -> dict[str, Any]:
        return self.meta_controller.run_cycle()

    def optimize(self) -> dict[str, Any]:
        return self.system_optimizer.optimize()

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
