from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, unique
from threading import RLock
from typing import Final

from cognition.contracts import (
    CognitiveContext,
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitiveResult,
)
from foundation.utils.hash import short_id

__all__ = [
    "CognitiveLifecycleStage",
    "CognitiveLifecycleStateMachine",
    "CognitiveLifecycleTransition",
]


@unique
class CognitiveLifecycleStage(StrEnum):
    GOAL = "goal"
    PLANNING = "planning"
    POLICY = "policy"
    DECISION = "decision"
    EXECUTION = "execution"
    RESULT = "result"


_STAGE_TRANSITIONS: Final[dict[CognitiveLifecycleStage, tuple[CognitiveLifecycleStage, ...]]] = {
    CognitiveLifecycleStage.GOAL: (CognitiveLifecycleStage.PLANNING, CognitiveLifecycleStage.RESULT),
    CognitiveLifecycleStage.PLANNING: (CognitiveLifecycleStage.POLICY, CognitiveLifecycleStage.RESULT),
    CognitiveLifecycleStage.POLICY: (CognitiveLifecycleStage.DECISION, CognitiveLifecycleStage.RESULT),
    CognitiveLifecycleStage.DECISION: (CognitiveLifecycleStage.EXECUTION, CognitiveLifecycleStage.RESULT),
    CognitiveLifecycleStage.EXECUTION: (CognitiveLifecycleStage.RESULT,),
    CognitiveLifecycleStage.RESULT: (),
}
_STATE_TRANSITIONS: Final[dict[CognitiveLifecycleState, tuple[CognitiveLifecycleState, ...]]] = {
    CognitiveLifecycleState.CREATED: (CognitiveLifecycleState.ACTIVE, CognitiveLifecycleState.FAILED, CognitiveLifecycleState.TERMINATED),
    CognitiveLifecycleState.ACTIVE: (
        CognitiveLifecycleState.COMPLETED,
        CognitiveLifecycleState.FAILED,
        CognitiveLifecycleState.SUSPENDED,
        CognitiveLifecycleState.TERMINATED,
    ),
    CognitiveLifecycleState.SUSPENDED: (CognitiveLifecycleState.ACTIVE, CognitiveLifecycleState.TERMINATED),
    CognitiveLifecycleState.COMPLETED: (),
    CognitiveLifecycleState.FAILED: (),
    CognitiveLifecycleState.TERMINATED: (),
}


@dataclass(frozen=True, slots=True)
class CognitiveLifecycleTransition:
    transition_id: str
    goal_id: str
    from_stage: CognitiveLifecycleStage
    to_stage: CognitiveLifecycleStage
    from_state: CognitiveLifecycleState
    to_state: CognitiveLifecycleState
    correlation_id: str
    causation_id: str | None
    trace_id: str | None
    tenant_id: str | None
    occurred_at: datetime
    sequence: int

    def __post_init__(self) -> None:
        if not self.transition_id.strip():
            raise ValueError("transition_id must not be empty")
        if not self.goal_id.strip():
            raise ValueError("goal_id must not be empty")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must not be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "transition_id": self.transition_id,
            "goal_id": self.goal_id,
            "from_stage": self.from_stage.value,
            "to_stage": self.to_stage.value,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "occurred_at": self.occurred_at.isoformat(),
            "sequence": self.sequence,
        }


class CognitiveLifecycleStateMachine:
    __slots__ = ("_context", "_goal", "_history", "_lock", "_stage", "_state")

    def __init__(self, goal: CognitiveGoal, *, context: CognitiveContext | None = None) -> None:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        if context is not None and not isinstance(context, CognitiveContext):
            raise TypeError("context must be CognitiveContext")
        if context is not None and context.goal_id != goal.goal_id:
            raise ValueError("context goal_id must match goal_id")
        self._goal = goal
        self._context = context
        self._stage = CognitiveLifecycleStage.GOAL
        self._state = goal.lifecycle_state
        self._history: list[CognitiveLifecycleTransition] = []
        self._lock = RLock()

    @property
    def goal(self) -> CognitiveGoal:
        return self._goal

    @property
    def context(self) -> CognitiveContext | None:
        return self._context

    @property
    def stage(self) -> CognitiveLifecycleStage:
        with self._lock:
            return self._stage

    @property
    def state(self) -> CognitiveLifecycleState:
        with self._lock:
            return self._state

    @property
    def history(self) -> tuple[CognitiveLifecycleTransition, ...]:
        with self._lock:
            return tuple(self._history)

    def advance(
        self,
        to_stage: CognitiveLifecycleStage,
        *,
        lifecycle_state: CognitiveLifecycleState = CognitiveLifecycleState.ACTIVE,
        causation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> CognitiveLifecycleTransition:
        if not isinstance(to_stage, CognitiveLifecycleStage):
            raise TypeError("to_stage must be CognitiveLifecycleStage")
        if not isinstance(lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        timestamp = occurred_at or datetime.now(UTC)
        with self._lock:
            if to_stage not in _STAGE_TRANSITIONS[self._stage]:
                raise ValueError(f"invalid lifecycle stage transition: {self._stage.value} -> {to_stage.value}")
            if self._state not in (CognitiveLifecycleState.CREATED, CognitiveLifecycleState.ACTIVE):
                raise ValueError(f"cannot advance from lifecycle state: {self._state.value}")
            if to_stage is not CognitiveLifecycleStage.RESULT and lifecycle_state is not CognitiveLifecycleState.ACTIVE:
                raise ValueError("non-result stages must enter ACTIVE state")
            if to_stage is CognitiveLifecycleStage.RESULT and lifecycle_state not in (
                CognitiveLifecycleState.ACTIVE,
                CognitiveLifecycleState.COMPLETED,
                CognitiveLifecycleState.FAILED,
                CognitiveLifecycleState.SUSPENDED,
                CognitiveLifecycleState.TERMINATED,
            ):
                raise ValueError("invalid result lifecycle state")
            transition = self._build_transition(to_stage, lifecycle_state, causation_id, timestamp)
            self._stage = to_stage
            self._state = lifecycle_state
            self._history.append(transition)
            return transition

    def transition_state(
        self,
        lifecycle_state: CognitiveLifecycleState,
        *,
        causation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> CognitiveLifecycleTransition:
        if not isinstance(lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        timestamp = occurred_at or datetime.now(UTC)
        with self._lock:
            if lifecycle_state not in _STATE_TRANSITIONS[self._state]:
                raise ValueError(f"invalid lifecycle state transition: {self._state.value} -> {lifecycle_state.value}")
            transition = self._build_transition(self._stage, lifecycle_state, causation_id, timestamp)
            self._state = lifecycle_state
            self._history.append(transition)
            return transition

    def finalize(self, result: CognitiveResult) -> CognitiveLifecycleTransition:
        if not isinstance(result, CognitiveResult):
            raise TypeError("result must be CognitiveResult")
        if result.goal_id != self._goal.goal_id:
            raise ValueError("result goal_id must match goal_id")
        if result.correlation_id != self._goal.correlation_id:
            raise ValueError("result correlation_id must match goal")
        if result.trace_id != self._goal.trace_id:
            raise ValueError("result trace_id must match goal")
        if result.tenant_id != self._goal.tenant_id:
            raise ValueError("result tenant_id must match goal")
        expected = {
            "success": CognitiveLifecycleState.COMPLETED,
            "failure": CognitiveLifecycleState.FAILED,
            "partial": CognitiveLifecycleState.ACTIVE,
        }[result.status.value]
        if result.lifecycle_state is not expected:
            raise ValueError("result status and lifecycle_state are inconsistent")
        return self.advance(
            CognitiveLifecycleStage.RESULT,
            lifecycle_state=result.lifecycle_state,
            causation_id=result.causation_id,
            occurred_at=result.created_at,
        )

    def to_dict(self) -> dict[str, object]:
        with self._lock:
            return {
                "lifecycle_id": short_id({"goal_id": self._goal.goal_id, "context_id": self._context.context_id if self._context is not None else None}, prefix="cognition.lifecycle:"),
                "goal_id": self._goal.goal_id,
                "stage": self._stage.value,
                "state": self._state.value,
                "correlation_id": self._goal.correlation_id,
                "trace_id": self._goal.trace_id,
                "tenant_id": self._goal.tenant_id,
                "context_id": self._context.context_id if self._context is not None else None,
                "history": [item.to_dict() for item in self._history],
            }

    def _build_transition(
        self,
        to_stage: CognitiveLifecycleStage,
        to_state: CognitiveLifecycleState,
        causation_id: str | None,
        occurred_at: datetime,
    ) -> CognitiveLifecycleTransition:
        sequence = len(self._history) + 1
        transition_id = short_id(
            {
                "goal_id": self._goal.goal_id,
                "from_stage": self._stage.value,
                "to_stage": to_stage.value,
                "from_state": self._state.value,
                "to_state": to_state.value,
                "causation_id": causation_id,
                "sequence": sequence,
            },
            prefix="cognition.transition:",
        )
        return CognitiveLifecycleTransition(
            transition_id=transition_id,
            goal_id=self._goal.goal_id,
            from_stage=self._stage,
            to_stage=to_stage,
            from_state=self._state,
            to_state=to_state,
            correlation_id=self._goal.correlation_id,
            causation_id=causation_id,
            trace_id=self._goal.trace_id,
            tenant_id=self._goal.tenant_id,
            occurred_at=occurred_at,
            sequence=sequence,
        )
