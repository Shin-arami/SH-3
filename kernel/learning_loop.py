from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from threading import RLock
from typing import Any

from cognition.memory import MemoryCore
from cognition.planner import Planner
from cognition.policy import PolicyEngine
from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from foundation.types.identifiers import IdentifierGenerator
from foundation.utils.hash import short_id
from foundation.utils.logging import info
from infrastructure.event_bus import EventBus, EventPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from kernel.core import SH3Kernel

__all__ = ["LearningLoop"]


class LearningLoop:
    __slots__ = (
        "_event_bus",
        "_event_publisher",
        "_lock",
        "_propagation_context",
        "_records",
        "kernel",
        "loop_id",
        "max_chunk_size",
        "max_weight",
        "memory",
        "min_chunk_size",
        "min_weight",
        "planner",
        "policy",
    )

    def __init__(
        self,
        kernel: SH3Kernel,
        *,
        min_weight: float = 0.1,
        max_weight: float = 5.0,
        min_chunk_size: int = 1,
        max_chunk_size: int = 8,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        if min_weight <= 0:
            raise ValueError("min_weight must be > 0")
        if max_weight < min_weight:
            raise ValueError("max_weight must be >= min_weight")
        if min_chunk_size < 1:
            raise ValueError("min_chunk_size must be >= 1")
        if max_chunk_size < min_chunk_size:
            raise ValueError("max_chunk_size must be >= min_chunk_size")

        self.kernel = kernel
        self.policy: PolicyEngine = kernel.policy
        self.planner: Planner = kernel.planner
        self.memory: MemoryCore = kernel.memory
        self.loop_id = short_id("learning-loop")
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self._event_publisher = event_publisher
        self._event_bus: EventBus | None = None
        self._lock = RLock()
        self._records: list[dict[str, Any]] = []
        self._propagation_context: EventPropagationContext | None = None
        self._configure_event_subscription()

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    def set_event_publisher(
        self,
        publisher: EventPublisher | None,
    ) -> None:
        if publisher is not None and not isinstance(publisher, EventPublisher):
            raise TypeError("publisher must implement EventPublisher")

        self._event_publisher = publisher
        self._configure_event_subscription()

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

    def _publish(
        self,
        event_name: str,
        payload: dict[str, Any],
        event_type: Any,
        context: EventPropagationContext | None = None,
        category: Category = Category.LEARNING,
    ) -> EventPropagationContext | None:
        publisher = self._event_publisher
        propagation = context or self._propagation_context

        if publisher is None:
            return propagation

        try:
            if propagation is None:
                event = Event.create(
                    event_name=event_name,
                    producer=self.loop_id,
                    payload=payload,
                    category=category,
                    event_type=event_type,
                )
            else:
                event = Event.create(
                    event_name=event_name,
                    producer=self.loop_id,
                    payload=payload,
                    category=category,
                    event_type=event_type,
                    correlation_id=propagation.correlation_id,
                    causation_id=propagation.causation_id,
                    trace_id=propagation.trace_id,
                    tenant_id=propagation.tenant_id,
                )

            publisher.publish(event)
            next_context = EventPropagationContext.from_event(event)
            self._propagation_context = next_context
            return next_context
        except Exception as exc:
            info(
                "Learning event publication failed",
                {"event_name": event_name, "error": str(exc)},
            )
            return propagation

    def collect(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(execution_result, dict):
            raise TypeError("execution_result must be dict")

        plan = execution_result.get("plan")
        if not isinstance(plan, dict):
            plan = {}

        tree = plan.get("tree")
        if not isinstance(tree, dict):
            tree = {}

        children = tree.get("children")
        plan_size = len(children) if isinstance(children, list) else 0

        decision = execution_result.get("decision")

        experience = {
            "goal": execution_result.get("goal"),
            "decision": decision,
            "plan_size": plan_size,
            "success": decision is not None,
        }

        info("Experience collected", experience)
        return experience

    def evaluate(self, experience: dict[str, Any]) -> float:
        if not isinstance(experience, dict):
            raise TypeError("experience must be dict")

        score = 0.0

        if bool(experience.get("success")):
            score += 0.6

        plan_size = experience.get("plan_size", 0)
        if isinstance(plan_size, bool) or not isinstance(plan_size, int):
            raise TypeError("experience plan_size must be int")
        if plan_size < 0:
            raise ValueError("experience plan_size must be >= 0")

        score += min(0.4, plan_size * 0.05)

        return round(score, 3)

    def update_policy(
        self,
        experience: dict[str, Any],
        score: float,
    ) -> None:
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        if score < 0.3:
            factor = 0.95
            action = "weakened"
        elif score > 0.7:
            factor = 1.02
            action = "reinforced"
        else:
            info("Policy unchanged", {"score": score})
            return

        for rule in self.policy.rules:
            rule.weight = min(
                self.max_weight,
                max(self.min_weight, rule.weight * factor),
            )

        info(
            "Policy updated",
            {
                "score": score,
                "factor": factor,
                "action": action,
                "rules": len(self.policy.rules),
            },
        )

    def tune_planner(
        self,
        experience: dict[str, Any],
        score: float,
    ) -> None:
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        current = self.planner.chunk_size

        if score < 0.3:
            target = max(self.min_chunk_size, current - 1)
            action = "finer"
        elif score > 0.8:
            target = min(self.max_chunk_size, current + 1)
            action = "coarser"
        else:
            target = current
            action = "unchanged"

        if target != current:
            self.planner.set_chunk_size(target)

        info(
            "Planner tuned",
            {
                "score": score,
                "previous_chunk_size": current,
                "chunk_size": target,
                "action": action,
            },
        )

    def store_experience(
        self,
        experience: dict[str, Any],
        score: float,
    ) -> str:
        if not isinstance(experience, dict):
            raise TypeError("experience must be dict")
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")

        key = short_id(str(experience))

        self.memory.write(
            key=key,
            value={
                "experience": experience,
                "score": score,
            },
            tags=["learning", "experience"],
        )

        return key

    def run(
        self,
        execution_result: dict[str, Any],
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        propagation = context or self._propagation_context

        try:
            propagation = self._publish(
                "LearningStarted",
                {
                    "loop_id": self.loop_id,
                },
                EventType.START,
                propagation,
            )

            experience = self.collect(execution_result)

            propagation = self._publish(
                "LearningRecordCreated",
                {
                    "loop_id": self.loop_id,
                    "experience": experience,
                },
                EventType.CREATED,
                propagation,
            )

            score = self.evaluate(experience)
            self.update_policy(experience, score)
            self.tune_planner(experience, score)
            memory_key = self.store_experience(experience, score)

            result = {
                "loop_id": self.loop_id,
                "experience": experience,
                "score": score,
                "memory_key": memory_key,
            }

            propagation = self._publish(
                "LearningResultRecorded",
                {
                    "loop_id": self.loop_id,
                    "memory_key": memory_key,
                    "score": score,
                    "success": True,
                },
                EventType.CREATED,
                propagation,
            )

            self._publish(
                "LearningCompleted",
                {
                    "loop_id": self.loop_id,
                    "memory_key": memory_key,
                    "score": score,
                    "success": True,
                },
                EventType.COMPLETE,
                propagation,
            )

            info("Learning loop completed", result)
            return result

        except Exception as exc:
            self._publish(
                "LearningFailed",
                {
                    "loop_id": self.loop_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "success": False,
                },
                EventType.FAILURE,
                propagation,
            )
            raise

    def _configure_event_subscription(self) -> None:
        publisher = self._event_publisher
        event_bus = getattr(publisher, "event_bus", None) if publisher is not None else None

        if event_bus is not None and not isinstance(event_bus, EventBus):
            event_bus = None

        if self._event_bus is event_bus:
            return

        if self._event_bus is not None:
            with suppress(KeyError):
                self._event_bus.unsubscribe(self.loop_id)

        self._event_bus = event_bus

        if event_bus is None:
            return

        event_bus.subscribe(
            EventSubscription(
                subscriber_id=self.loop_id,
                handler=self._handle_event,
                event_name="HealingFeedbackRecorded",
                priority=100,
            ),
            replace=True,
        )

    def record(
        self,
        domain: str,
        score: float,
        success: bool,
        details: Mapping[str, Any] | None = None,
        *,
        context: EventPropagationContext | None = None,
    ) -> str:
        if not domain:
            raise ValueError("domain must not be empty")
        record_id = IdentifierGenerator.entity()
        record = {
            "record_id": record_id,
            "domain": domain,
            "score": float(score),
            "success": bool(success),
            "details": dict(details or {}),
        }
        with self._lock:
            self._records.append(record)
        propagation = context or self._propagation_context
        if propagation is None:
            propagation = EventPropagationContext.create(
                correlation_id=f"learning:{self.loop_id}"
            )
        propagation = self._publish(
            "LearningRecordCreated",
            record,
            EventType.CREATED,
            propagation,
        )
        self._publish(
            "LearningResultRecorded",
            record,
            EventType.CREATED,
            propagation,
        )
        return record_id


    def records(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(
                {
                    **record,
                    "details": dict(record["details"]),
                }
                for record in self._records
            )


    def _handle_event(self, event: Event) -> None:
        if event.metadata.event_name != "HealingFeedbackRecorded":
            return
        payload = event.payload
        feedback = payload.get("feedback")
        if not isinstance(feedback, Mapping):
            return
        score = feedback.get("score")
        success = payload.get("success")
        details = feedback.get("details", {})
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            return
        if not isinstance(success, bool):
            return
        if not isinstance(details, Mapping):
            details = {}
        details = {
            **details,
            "strategy": payload.get("strategy"),
            "attempt": feedback.get("attempt"),
            "recovery_id": payload.get("recovery_id"),
        }
        context = EventPropagationContext.from_event(event)
        self.record(
            "self_healing.recovery",
            float(score),
            success,
            details,
            context=context,
        )
