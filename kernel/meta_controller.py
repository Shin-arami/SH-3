from __future__ import annotations

from typing import Any

from cognition.policy import PolicyEngine, default_policy
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.utils.hash import short_id
from foundation.utils.logging import error, info
from infrastructure.event_bus import EventPublisher
from infrastructure.events.model import Event
from infrastructure.events.propagation import EventPropagationContext
from kernel.core import SH3Kernel
from self_healing.core import SelfHealingCore

__all__ = ["MetaController"]


class MetaController:
    __slots__ = (
        "_event_publisher",
        "_last_event_id",
        "_propagation_context",
        "healer",
        "kernel",
        "meta_id",
        "policy_engine",

    )

    def __init__(
        self,
        kernel: SH3Kernel,
        *,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.kernel = kernel
        self._event_publisher = event_publisher
        self._last_event_id: str | None = None
        self.healer = SelfHealingCore(event_publisher=event_publisher)
        self.policy_engine: PolicyEngine = kernel.policy
        self.meta_id = short_id("meta-controller")
        self._propagation_context: EventPropagationContext | None = None

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(self, publisher: EventPublisher | None) -> None:
        self._event_publisher = publisher
        self.healer.set_event_publisher(publisher)

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
            event = Event.create(
                event_name=event_name,
                producer="optimizer",
                payload=payload,
                category=Category.ACTION,
                event_type=event_type,
                correlation_id=self._last_event_id,
                causation_id=self._last_event_id,
            )
            publisher.publish(event)
            self._last_event_id = event.id
        except Exception as exc:
            error(
                "MetaController event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )

    def observe(self) -> dict[str, Any]:
        snapshot = {
            "kernel": self.kernel.context_manager.snapshot(),
            "memory": self.kernel.memory.snapshot(),
            "policy_rules": len(self.policy_engine.rules),
        }
        info("Meta observation completed", snapshot)
        return snapshot

    def evaluate_health(self, snapshot: dict[str, Any]) -> dict[str, float]:
        context_depth = snapshot["kernel"]["depth"]
        memory_size = snapshot["memory"]["timeline_length"]
        policy_count = snapshot["policy_rules"]

        score = {
            "context_health": max(0.0, 1.0 - context_depth * 0.1),
            "memory_health": min(1.0, memory_size / 50),
            "policy_health": min(1.0, policy_count / 10),
        }

        info("System health evaluated", score)
        return score

    def decide_action(self, health: dict[str, float]) -> str:
        avg = sum(health.values()) / len(health)

        if avg < 0.3:
            return "rebuild"
        if avg < 0.6:
            return "heal"
        if avg < 0.8:
            return "optimize"
        return "stable"

    def tune_policy(self, snapshot: dict[str, Any]) -> None:
        if len(self.policy_engine.rules) >= 3:
            return

        tuning_id = short_id(f"policy-tuning:{self.meta_id}")
        self._publish(
            "PolicyTuningStarted",
            EventType.START,
            {"tuning_id": tuning_id},
        )

        try:
            new_policy = default_policy()
            self.policy_engine.rules = new_policy.rules
            info("Policy auto-tuned", {"rules": len(new_policy.rules)})
            self._publish(
                "PolicyTuningCompleted",
                EventType.COMPLETE,
                {"tuning_id": tuning_id, "success": True},
            )
        except Exception as exc:
            self._publish(
                "OptimizationFailed",
                EventType.FAILURE,
                {
                    "optimization_id": tuning_id,
                    "error": str(exc),
                },
            )
            raise

    def trigger(self, action: str, snapshot: dict[str, Any]) -> Any:
        decision_id = short_id(f"optimization-decision:{self.meta_id}")
        self._publish(
            "OptimizationDecisionCreated",
            EventType.CREATED,
            {
                "decision_id": decision_id,
                "action": action,
            },
        )

        if action == "heal":
            return self.healer.execute_safe(lambda: "heal_triggered")

        if action == "rebuild":
            self.kernel.context_manager.clear()
            return {"status": "kernel_rebuilt"}

        if action == "optimize":
            optimization = self.kernel.system_optimizer.optimize(
                context=self._propagation_context,
                execute=True,
            )
            self.tune_policy(snapshot)
            return {"status": "optimized", "optimization": optimization}

        return {"status": "stable"}

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

    def run_cycle(
            self,
            *,
            context: EventPropagationContext | None = None
        ) -> dict[str, Any]:
        if context is not None:
            self.set_propagation_context(context)
        optimization_id = short_id(f"meta-cycle:{self.meta_id}")

        try:
            snapshot = self.observe()
            health = self.evaluate_health(snapshot)
            action = self.decide_action(health)
            result = self.trigger(action, snapshot)

            payload = {
                "optimization_id": optimization_id,
                "success": True,
            }
            self._publish(
                "OptimizationCompleted",
                EventType.COMPLETE,
                payload,
            )

            return {
                "meta_id": self.meta_id,
                "snapshot": snapshot,
                "health": health,
                "action": action,
                "result": result,
            }
        except Exception as exc:
            self._publish(
                "OptimizationFailed",
                EventType.FAILURE,
                {
                    "optimization_id": optimization_id,
                    "error": str(exc),
                },
            )
            raise
