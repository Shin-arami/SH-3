from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cognition.core import CognitionCore
from cognition.execution_boundary import CognitiveExecutionBoundary
from cognition.feedback_boundary import CognitiveFeedbackBoundary
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
from infrastructure.security import EvidenceStore
from infrastructure.security.persistent_operation_store import (
    SQLiteReplayOperationStore,
)
from infrastructure.security.persistent_store import (
    SQLiteEvidenceStore,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from runtime.context_manager import ContextManager
from runtime.core import RuntimeCore
from runtime.execution_engine import RuntimeExecutionEngine

__all__ = ["SH3Kernel"]


class SH3Kernel:
    __slots__ = (
        "_event_publisher",
        "_last_event_id",
        "_propagation_context",
        "cognition",
        "cognitive_learning_boundary",
        "context_manager",
        "feedback_boundary",
        "kernel_id",
        "learning_closed_loop_evidence_boundary",
        "learning_feedback_loop",
        "learning_loop",
        "learning_optimizer_boundary",
        "memory",
        "meta_controller",
        "optimizer_evidence_boundary",
        "optimizer_healing_boundary",
        "optimizer_update_boundary",
        "planner",
        "policy",
        "recovery_execution_boundary",
        "recovery_strategy_boundary",
        "replay_operation_store",
        "replay_stage_store",
        "runtime",
        "system_optimizer",
    )

    def __init__(
        self,
        *,
        event_publisher: EventPublisher | None = None,
        evidence_store: EvidenceStore | None = None,
        replay_claim_store: SQLiteReplayClaimStore | None = None,
        replay_stage_store: SQLiteReplayStageStore | None = None,
        replay_operation_store: SQLiteReplayOperationStore | None = None,
    ) -> None:
        if evidence_store is not None and not isinstance(evidence_store, EvidenceStore):
            raise TypeError("evidence_store must be EvidenceStore or None")
        if replay_claim_store is not None and not isinstance(
            replay_claim_store, SQLiteReplayClaimStore
        ):
            raise TypeError("replay_claim_store must be SQLiteReplayClaimStore or None")
        if replay_stage_store is not None and not isinstance(
            replay_stage_store, SQLiteReplayStageStore
        ):
            raise TypeError("replay_stage_store must be SQLiteReplayStageStore or None")
        if replay_stage_store is not None:
            if replay_claim_store is None:
                raise ValueError(
                    "replay_stage_store requires replay_claim_store"
                )
            if replay_stage_store.database_path != replay_claim_store.database_path:
                raise ValueError(
                    "replay claim and stage stores must share one SQLite database"
                )
        if replay_operation_store is not None:
            if replay_claim_store is None or replay_stage_store is None:
                raise ValueError(
                    "replay_operation_store requires replay_claim_store and replay_stage_store"
                )
            if replay_operation_store.database_path != replay_claim_store.database_path:
                raise ValueError(
                    "operation and replay claim stores must share one SQLite database"
                )
            if replay_operation_store.database_path != replay_stage_store.database_path:
                raise ValueError(
                    "operation and replay stage stores must share one SQLite database"
                )
        if replay_claim_store is not None:
            if not isinstance(evidence_store, SQLiteEvidenceStore):
                raise ValueError("replay_claim_store requires SQLiteEvidenceStore")
            if replay_claim_store.database_path != evidence_store.database_path:
                raise ValueError("evidence and replay claims must share one SQLite database")
        self._event_publisher = event_publisher
        self._last_event_id: str | None = None
        self._propagation_context: EventPropagationContext | None = None
        self.replay_stage_store = replay_stage_store
        self.replay_operation_store = replay_operation_store

        self.runtime = RuntimeCore(event_publisher=event_publisher)
        self.context_manager = ContextManager()
        if evidence_store is None:
            # Preserve the legacy in-memory construction path by default.
            self.cognition = CognitionCore(
                self.context_manager, event_publisher=event_publisher
            )
        else:
            # Persistent kernels share their evidence boundary with cognition and runtime.
            execution_engine = RuntimeExecutionEngine(
                event_publisher=event_publisher, evidence_store=evidence_store
            )
            self.cognition = CognitionCore(
                self.context_manager,
                execution_boundary=CognitiveExecutionBoundary(execution_engine),
                event_publisher=event_publisher,
                evidence_store=evidence_store,
            )
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
            replay_operation_store=replay_operation_store,
        )
        from kernel.cognitive_learning_boundary import CognitiveLearningBoundary
        from kernel.learning_closed_loop_evidence_boundary import LearningClosedLoopEvidenceBoundary
        from kernel.learning_feedback_loop import LearningClosedLoopCoordinator
        from kernel.learning_optimizer_boundary import LearningOptimizerBoundary
        from kernel.optimizer_evidence_boundary import OptimizationEvidenceBoundary
        from kernel.optimizer_healing_boundary import OptimizerHealingBoundary
        from kernel.optimizer_update_boundary import OptimizationUpdateBoundary
        from kernel.recovery_execution_boundary import RecoveryExecutionBoundary
        from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary
        self.cognitive_learning_boundary = CognitiveLearningBoundary(
            self.learning_loop,
            event_publisher=event_publisher,
            replay_stage_store=replay_stage_store,
        )
        self.feedback_boundary = CognitiveFeedbackBoundary(
            self.cognition,
            event_publisher=event_publisher,
        )
        self.optimizer_evidence_boundary = OptimizationEvidenceBoundary(
            evidence_store=evidence_store,
            event_publisher=event_publisher,
        )
        self.learning_closed_loop_evidence_boundary = LearningClosedLoopEvidenceBoundary(
            self.optimizer_evidence_boundary.evidence_store,
            event_publisher=event_publisher,
        )
        self.optimizer_update_boundary = OptimizationUpdateBoundary(
            self.system_optimizer,
            event_publisher=event_publisher,
            evidence_boundary=self.optimizer_evidence_boundary,
        )
        self.learning_optimizer_boundary = LearningOptimizerBoundary(
            self.system_optimizer,
            event_publisher=event_publisher,
            update_boundary=self.optimizer_update_boundary,
            replay_stage_store=replay_stage_store,
        )
        self.recovery_strategy_boundary = RecoveryStrategyBoundary(
            self.meta_controller.healer,
            event_publisher=event_publisher,
            replay_stage_store=replay_stage_store,
        )
        self.recovery_execution_boundary = RecoveryExecutionBoundary(
            self.meta_controller.healer,
            event_publisher=event_publisher,
            replay_stage_store=replay_stage_store,
            replay_operation_store=replay_operation_store,
        )
        self.optimizer_healing_boundary = OptimizerHealingBoundary(
            self.meta_controller.healer,
            event_publisher=event_publisher,
            strategy_boundary=self.recovery_strategy_boundary,
            execution_boundary=self.recovery_execution_boundary,
        )
        self.learning_feedback_loop = LearningClosedLoopCoordinator(
            self,
            event_publisher=event_publisher,
            learning_boundary=self.cognitive_learning_boundary,
            optimizer_boundary=self.learning_optimizer_boundary,
            healing_boundary=self.optimizer_healing_boundary,
            recovery_strategy_boundary=self.recovery_strategy_boundary,
            recovery_execution_boundary=self.recovery_execution_boundary,
            feedback_boundary=self.feedback_boundary,
            closed_loop_evidence_boundary=self.learning_closed_loop_evidence_boundary,
            replay_claim_store=replay_claim_store,
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
        self.cognition.set_event_publisher(publisher)
        execution_backend = self.cognition.execution_boundary.backend
        if isinstance(execution_backend, RuntimeExecutionEngine):
            execution_backend.set_event_publisher(publisher)
        self.learning_loop.set_event_publisher(publisher)
        self.meta_controller.set_event_publisher(publisher)
        self.system_optimizer.set_event_publisher(publisher)
        self.learning_feedback_loop.set_event_publisher(publisher)
        self.cognitive_learning_boundary.set_event_publisher(publisher)
        self.feedback_boundary.set_event_publisher(publisher)
        self.learning_optimizer_boundary.set_event_publisher(publisher)
        self.optimizer_update_boundary.set_event_publisher(publisher)
        self.optimizer_evidence_boundary.set_event_publisher(publisher)
        self.learning_closed_loop_evidence_boundary.set_event_publisher(publisher)
        self.optimizer_healing_boundary.set_event_publisher(publisher)
        self.recovery_strategy_boundary.set_event_publisher(publisher)
        self.recovery_execution_boundary.set_event_publisher(publisher)

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

    def learning_feedback_cycle(
        self,
        result: Any,
        *,
        context: EventPropagationContext | None = None,
        optimize: bool = True,
        recover: bool = True,
    ) -> Any:
        from cognition.contracts import CognitiveResult
        if not isinstance(result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")
        propagation = self._new_propagation(context)
        self._propagation_context = propagation
        return self.learning_feedback_loop.run(
            result,
            context=propagation,
            optimize=optimize,
            recover=recover,
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
        propagation = self._new_propagation()
        self._propagation_context = propagation
        self.meta_controller.healer.set_propagation_context(propagation)
        snapshot = self.meta_controller.healer.detect(exc, context or {})
        strategy = self.recovery_strategy_boundary.request(
            snapshot,
            context=propagation,
        )
        execution = self.recovery_execution_boundary.request(
            strategy,
            snapshot,
            context=strategy.propagation_context,
        )
        self._propagation_context = execution.propagation_context
        if not execution.success:
            raise RuntimeError(execution.error or "recovery execution failed")
        return execution.result

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
