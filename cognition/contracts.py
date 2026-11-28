from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, unique
from math import isfinite
from types import MappingProxyType
from typing import Any

from foundation.utils.hash import short_id
from foundation.version import COGNITION_CONTRACT_VERSION, validate_semantic_version

__all__ = [
    "COGNITION_CONTRACT_VERSION",
    "CognitiveContext",
    "CognitiveDecision",
    "CognitiveGoal",
    "CognitiveLifecycleState",
    "CognitivePlan",
    "CognitiveResult",
    "CognitiveResultStatus",
    "CognitiveState",
]


@unique
class CognitiveLifecycleState(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


def _validate_text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_timestamp(name: str, value: datetime) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be datetime")
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")


def _validate_score(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric or None")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def _validate_trace_fields(
    correlation_id: str,
    causation_id: str | None,
    trace_id: str | None,
    tenant_id: str | None,
) -> None:
    _validate_text("correlation_id", correlation_id)
    for name, value in (("causation_id", causation_id), ("trace_id", trace_id), ("tenant_id", tenant_id)):
        if value is not None:
            _validate_text(name, value)


def _mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


def _text_tuple(name: str, values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(values)
    for value in result:
        _validate_text(name, value)
    return result


@dataclass(frozen=True, slots=True)
class CognitiveContext:
    context_id: str
    goal_id: str
    correlation_id: str
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    values: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_text("context_id", self.context_id)
        _validate_text("goal_id", self.goal_id)
        _validate_trace_fields(self.correlation_id, self.causation_id, self.trace_id, self.tenant_id)
        object.__setattr__(self, "values", _mapping(self.values))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def create(
        cls,
        goal_id: str,
        *,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        values: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CognitiveContext:
        _validate_text("goal_id", goal_id)
        resolved_correlation = correlation_id or f"cognition:{goal_id}"
        context_id = short_id(
            {
                "goal_id": goal_id,
                "correlation_id": resolved_correlation,
                "causation_id": causation_id,
                "trace_id": trace_id,
                "tenant_id": tenant_id,
                "values": values or {},
                "metadata": metadata or {},
            },
            prefix="ctx:",
        )
        return cls(
            context_id=context_id,
            goal_id=goal_id,
            correlation_id=resolved_correlation,
            causation_id=causation_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            values=values if values is not None else {},
            metadata=metadata if metadata is not None else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "goal_id": self.goal_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "values": dict(self.values),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveGoal:
    goal_id: str
    goal_type: str
    owner: str
    version: str
    created_at: datetime
    lifecycle_state: CognitiveLifecycleState
    intent: str
    success_criteria: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)
    priority: float = 0.0
    time_horizon: str | None = None
    correlation_id: str = ""
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("goal_id", self.goal_id),
            ("goal_type", self.goal_type),
            ("owner", self.owner),
            ("version", self.version),
            ("intent", self.intent),
        ):
            _validate_text(name, value)
        validate_semantic_version(self.version, field="version")
        _validate_timestamp("created_at", self.created_at)
        if not isinstance(self.lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        if not isinstance(self.priority, (int, float)) or isinstance(self.priority, bool):
            raise TypeError("priority must be numeric")
        if not isfinite(float(self.priority)):
            raise ValueError("priority must be finite")
        if self.time_horizon is not None:
            _validate_text("time_horizon", self.time_horizon)
        _validate_trace_fields(self.correlation_id, self.causation_id, self.trace_id, self.tenant_id)
        object.__setattr__(self, "success_criteria", _text_tuple("success_criteria", self.success_criteria))
        object.__setattr__(self, "constraints", _mapping(self.constraints))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def create(
        cls,
        intent: str,
        *,
        owner: str = "cognition",
        goal_type: str = "goal",
        version: str = COGNITION_CONTRACT_VERSION,
        created_at: datetime | None = None,
        lifecycle_state: CognitiveLifecycleState = CognitiveLifecycleState.CREATED,
        success_criteria: Iterable[str] = (),
        constraints: Mapping[str, Any] | None = None,
        priority: float = 0.0,
        time_horizon: str | None = None,
        goal_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CognitiveGoal:
        _validate_text("intent", intent)
        _validate_text("owner", owner)
        _validate_text("goal_type", goal_type)
        resolved_criteria = tuple(success_criteria)
        resolved_id = goal_id or short_id(
            {"goal_type": goal_type, "owner": owner, "intent": intent, "version": version, "success_criteria": resolved_criteria, "constraints": constraints or {}, "priority": priority, "time_horizon": time_horizon},
            prefix="goal:",
        )
        resolved_correlation = correlation_id or f"goal:{resolved_id}"
        resolved_trace = trace_id or resolved_id
        return cls(
            goal_id=resolved_id,
            goal_type=goal_type,
            owner=owner,
            version=version,
            created_at=created_at or datetime.now(UTC),
            lifecycle_state=lifecycle_state,
            intent=intent,
            success_criteria=resolved_criteria,
            constraints=constraints if constraints is not None else {},
            priority=priority,
            time_horizon=time_horizon,
            correlation_id=resolved_correlation,
            causation_id=causation_id,
            trace_id=resolved_trace,
            tenant_id=tenant_id,
            metadata=metadata if metadata is not None else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_type": self.goal_type,
            "owner": self.owner,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "lifecycle_state": self.lifecycle_state.value,
            "intent": self.intent,
            "success_criteria": list(self.success_criteria),
            "constraints": dict(self.constraints),
            "priority": self.priority,
            "time_horizon": self.time_horizon,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveState:
    state_id: str
    goal_id: str
    lifecycle_state: CognitiveLifecycleState
    steps: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    results: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    context: CognitiveContext | None = None
    correlation_id: str = ""
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_text("state_id", self.state_id)
        _validate_text("goal_id", self.goal_id)
        if not isinstance(self.lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        _validate_timestamp("created_at", self.created_at)
        if self.updated_at is not None:
            _validate_timestamp("updated_at", self.updated_at)
            if self.updated_at < self.created_at:
                raise ValueError("updated_at must be >= created_at")
        _validate_trace_fields(self.correlation_id, self.causation_id, self.trace_id, self.tenant_id)
        object.__setattr__(self, "steps", _text_tuple("steps", self.steps))
        object.__setattr__(self, "assumptions", _text_tuple("assumptions", self.assumptions))
        object.__setattr__(self, "results", _mapping(self.results))
        object.__setattr__(self, "metadata", _mapping(self.metadata))
        if self.context is not None and self.context.goal_id != self.goal_id:
            raise ValueError("context goal_id must match goal_id")

    @classmethod
    def from_goal(
        cls,
        goal: CognitiveGoal,
        *,
        context: CognitiveContext | None = None,
        steps: Iterable[str] = (),
        assumptions: Iterable[str] = (),
        results: Mapping[str, Any] | None = None,
        lifecycle_state: CognitiveLifecycleState | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CognitiveState:
        if not isinstance(goal, CognitiveGoal):
            raise TypeError("goal must be CognitiveGoal")
        if context is not None and context.goal_id != goal.goal_id:
            raise ValueError("context goal_id must match goal_id")
        timestamp = created_at or goal.created_at
        resolved_steps = tuple(steps)
        resolved_assumptions = tuple(assumptions)
        return cls(
            state_id=short_id(
                {
                    "goal_id": goal.goal_id,
                    "steps": resolved_steps,
                    "assumptions": resolved_assumptions,
                    "results": results or {},
                    "lifecycle_state": (lifecycle_state or goal.lifecycle_state).value,
                },
                prefix="state:",
            ),
            goal_id=goal.goal_id,
            lifecycle_state=lifecycle_state if lifecycle_state is not None else goal.lifecycle_state,
            steps=resolved_steps,
            assumptions=resolved_assumptions,
            results=results if results is not None else {},
            created_at=timestamp,
            updated_at=updated_at,
            context=context,
            correlation_id=goal.correlation_id,
            causation_id=goal.causation_id,
            trace_id=goal.trace_id,
            tenant_id=goal.tenant_id,
            metadata=metadata if metadata is not None else goal.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "goal_id": self.goal_id,
            "lifecycle_state": self.lifecycle_state.value,
            "steps": list(self.steps),
            "assumptions": list(self.assumptions),
            "results": dict(self.results),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at is not None else None,
            "context": self.context.to_dict() if self.context is not None else None,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitivePlan:
    plan_id: str
    goal_id: str
    planning_type: str
    owner: str
    version: str
    created_at: datetime
    lifecycle_state: CognitiveLifecycleState
    steps: tuple[str, ...]
    dependencies: tuple[tuple[str, str], ...] = ()
    resources: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("plan_id", self.plan_id), ("goal_id", self.goal_id), ("planning_type", self.planning_type), ("owner", self.owner), ("version", self.version)):
            _validate_text(name, value)
        validate_semantic_version(self.version, field="version")
        _validate_timestamp("created_at", self.created_at)
        if not isinstance(self.lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        _validate_trace_fields(self.correlation_id, self.causation_id, self.trace_id, self.tenant_id)
        object.__setattr__(self, "steps", _text_tuple("steps", self.steps))
        normalized_dependencies = tuple(tuple(item) for item in self.dependencies)
        if any(len(item) != 2 for item in normalized_dependencies):
            raise ValueError("dependencies must contain pairs")
        step_names = set(self.steps)
        for dependency in normalized_dependencies:
            _validate_text("dependencies", dependency[0])
            _validate_text("dependencies", dependency[1])
            if dependency[0] == dependency[1]:
                raise ValueError("dependencies must not self-reference")
            if dependency[0] not in step_names or dependency[1] not in step_names:
                raise ValueError("dependencies must reference plan steps")
        object.__setattr__(self, "dependencies", normalized_dependencies)
        object.__setattr__(self, "resources", _mapping(self.resources))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def create(
        cls,
        goal: CognitiveGoal | str,
        steps: Iterable[str],
        *,
        planning_type: str = "execution",
        owner: str = "cognition",
        version: str = COGNITION_CONTRACT_VERSION,
        created_at: datetime | None = None,
        lifecycle_state: CognitiveLifecycleState = CognitiveLifecycleState.CREATED,
        dependencies: Iterable[tuple[str, str]] = (),
        resources: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        plan_id: str | None = None,
    ) -> CognitivePlan:
        goal_id = goal.goal_id if isinstance(goal, CognitiveGoal) else goal
        _validate_text("goal_id", goal_id)
        resolved_steps = tuple(steps)
        resolved_dependencies = tuple(dependencies)
        resolved_id = plan_id or short_id(
            {
                "goal_id": goal_id,
                "steps": resolved_steps,
                "dependencies": resolved_dependencies,
                "resources": resources or {},
                "planning_type": planning_type,
                "owner": owner,
                "version": version,
            },
            prefix="plan:",
        )
        return cls(
            plan_id=resolved_id,
            goal_id=goal_id,
            planning_type=planning_type,
            owner=owner,
            version=version,
            created_at=created_at or datetime.now(UTC),
            lifecycle_state=lifecycle_state,
            steps=resolved_steps,
            dependencies=resolved_dependencies,
            resources=resources if resources is not None else {},
            correlation_id=correlation_id if correlation_id is not None else (goal.correlation_id if isinstance(goal, CognitiveGoal) else f"goal:{goal_id}"),
            causation_id=causation_id,
            trace_id=trace_id if trace_id is not None else (goal.trace_id if isinstance(goal, CognitiveGoal) else goal_id),
            tenant_id=tenant_id if tenant_id is not None else (goal.tenant_id if isinstance(goal, CognitiveGoal) else None),
            metadata=metadata if metadata is not None else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "planning_type": self.planning_type,
            "owner": self.owner,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "lifecycle_state": self.lifecycle_state.value,
            "steps": list(self.steps),
            "dependencies": [list(item) for item in self.dependencies],
            "resources": dict(self.resources),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveDecision:
    decision_id: str
    goal_id: str
    decision_type: str
    owner: str
    version: str
    created_at: datetime
    lifecycle_state: CognitiveLifecycleState
    options: tuple[str, ...]
    selected_option: str | None = None
    rationale: str = ""
    utility: float | None = None
    risk: float | None = None
    correlation_id: str = ""
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("decision_id", self.decision_id), ("goal_id", self.goal_id), ("decision_type", self.decision_type), ("owner", self.owner), ("version", self.version)):
            _validate_text(name, value)
        validate_semantic_version(self.version, field="version")
        _validate_timestamp("created_at", self.created_at)
        if not isinstance(self.lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        if len(set(self.options)) != len(self.options):
            raise ValueError("options must be unique")
        if self.selected_option is not None:
            _validate_text("selected_option", self.selected_option)
            if self.selected_option not in self.options:
                raise ValueError("selected_option must be one of options")
        _validate_trace_fields(self.correlation_id, self.causation_id, self.trace_id, self.tenant_id)
        _validate_score("utility", self.utility)
        _validate_score("risk", self.risk)
        if self.rationale:
            _validate_text("rationale", self.rationale)
        object.__setattr__(self, "options", _text_tuple("options", self.options))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def create(
        cls,
        goal: CognitiveGoal | str,
        options: Iterable[str],
        *,
        selected_option: str | None = None,
        decision_type: str = "selection",
        owner: str = "cognition",
        version: str = COGNITION_CONTRACT_VERSION,
        created_at: datetime | None = None,
        lifecycle_state: CognitiveLifecycleState = CognitiveLifecycleState.CREATED,
        rationale: str = "",
        utility: float | None = None,
        risk: float | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        decision_id: str | None = None,
    ) -> CognitiveDecision:
        goal_id = goal.goal_id if isinstance(goal, CognitiveGoal) else goal
        _validate_text("goal_id", goal_id)
        resolved_options = tuple(options)
        resolved_id = decision_id or short_id(
            {
                "goal_id": goal_id,
                "options": resolved_options,
                "selected_option": selected_option,
                "decision_type": decision_type,
                "owner": owner,
                "version": version,
                "rationale": rationale,
                "utility": utility,
                "risk": risk,
            },
            prefix="decision:",
        )
        return cls(
            decision_id=resolved_id,
            goal_id=goal_id,
            decision_type=decision_type,
            owner=owner,
            version=version,
            created_at=created_at or datetime.now(UTC),
            lifecycle_state=lifecycle_state,
            options=resolved_options,
            selected_option=selected_option,
            rationale=rationale,
            utility=utility,
            risk=risk,
            correlation_id=correlation_id if correlation_id is not None else (goal.correlation_id if isinstance(goal, CognitiveGoal) else f"goal:{goal_id}"),
            causation_id=causation_id,
            trace_id=trace_id if trace_id is not None else (goal.trace_id if isinstance(goal, CognitiveGoal) else goal_id),
            tenant_id=tenant_id if tenant_id is not None else (goal.tenant_id if isinstance(goal, CognitiveGoal) else None),
            metadata=metadata if metadata is not None else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "goal_id": self.goal_id,
            "decision_type": self.decision_type,
            "owner": self.owner,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "lifecycle_state": self.lifecycle_state.value,
            "options": list(self.options),
            "selected_option": self.selected_option,
            "rationale": self.rationale,
            "utility": self.utility,
            "risk": self.risk,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }


@unique
class CognitiveResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class CognitiveResult:
    result_id: str
    goal_id: str
    result_type: str
    owner: str
    version: str
    created_at: datetime
    lifecycle_state: CognitiveLifecycleState
    status: CognitiveResultStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    correlation_id: str = ""
    causation_id: str | None = None
    trace_id: str | None = None
    tenant_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (("result_id", self.result_id), ("goal_id", self.goal_id), ("result_type", self.result_type), ("owner", self.owner), ("version", self.version)):
            _validate_text(name, value)
        validate_semantic_version(self.version, field="version")
        _validate_timestamp("created_at", self.created_at)
        if not isinstance(self.lifecycle_state, CognitiveLifecycleState):
            raise TypeError("lifecycle_state must be CognitiveLifecycleState")
        if not isinstance(self.status, CognitiveResultStatus):
            raise TypeError("status must be CognitiveResultStatus")
        if self.error_type is not None:
            _validate_text("error_type", self.error_type)
        if self.error_message is not None:
            _validate_text("error_message", self.error_message)
        _validate_trace_fields(self.correlation_id, self.causation_id, self.trace_id, self.tenant_id)
        object.__setattr__(self, "output", _mapping(self.output))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def create(
        cls,
        goal: CognitiveGoal | str,
        *,
        status: CognitiveResultStatus,
        output: Mapping[str, Any] | None = None,
        result_type: str = "cognition",
        owner: str = "cognition",
        version: str = COGNITION_CONTRACT_VERSION,
        created_at: datetime | None = None,
        lifecycle_state: CognitiveLifecycleState = CognitiveLifecycleState.COMPLETED,
        error_type: str | None = None,
        error_message: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        tenant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        result_id: str | None = None,
    ) -> CognitiveResult:
        goal_id = goal.goal_id if isinstance(goal, CognitiveGoal) else goal
        _validate_text("goal_id", goal_id)
        if not isinstance(status, CognitiveResultStatus):
            raise TypeError("status must be CognitiveResultStatus")
        resolved_id = result_id or short_id(
            {
                "goal_id": goal_id,
                "status": status.value,
                "output": output or {},
                "result_type": result_type,
                "owner": owner,
                "version": version,
                "error_type": error_type,
                "error_message": error_message,
            },
            prefix="result:",
        )
        return cls(
            result_id=resolved_id,
            goal_id=goal_id,
            result_type=result_type,
            owner=owner,
            version=version,
            created_at=created_at or datetime.now(UTC),
            lifecycle_state=lifecycle_state,
            status=status,
            output=output if output is not None else {},
            error_type=error_type,
            error_message=error_message,
            correlation_id=correlation_id if correlation_id is not None else (goal.correlation_id if isinstance(goal, CognitiveGoal) else f"goal:{goal_id}"),
            causation_id=causation_id,
            trace_id=trace_id if trace_id is not None else (goal.trace_id if isinstance(goal, CognitiveGoal) else goal_id),
            tenant_id=tenant_id if tenant_id is not None else (goal.tenant_id if isinstance(goal, CognitiveGoal) else None),
            metadata=metadata if metadata is not None else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "goal_id": self.goal_id,
            "result_type": self.result_type,
            "owner": self.owner,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "lifecycle_state": self.lifecycle_state.value,
            "status": self.status.value,
            "output": dict(self.output),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "metadata": dict(self.metadata),
        }
