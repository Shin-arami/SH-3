
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cognition.contracts import (
    CognitiveGoal,
    CognitiveLifecycleState,
    CognitiveResult,
    CognitiveResultStatus,
)
from infrastructure.events import EventPropagationContext
from kernel.cognitive_closed_loop_boundary import (
    CognitiveClosedLoopBoundary,
    CognitiveClosedLoopRequest,
)
from kernel.learning_feedback_loop import (
    ClosedLoopStatus,
    LearningClosedLoopReport,
)

NOW = datetime(2026, 10, 31, 0, 0, tzinfo=UTC)


def _result() -> CognitiveResult:
    goal = CognitiveGoal.create(
        "verify closed-loop identity isolation",
        created_at=NOW,
        correlation_id="result-correlation",
        trace_id="result-trace",
    )
    return CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        lifecycle_state=CognitiveLifecycleState.COMPLETED,
        created_at=NOW,
        output={"operation": "identity-isolation"},
        result_id="result:closed-loop-identity-isolation",
    )


def _context(
    *,
    correlation_id: str = "correlation-a",
    causation_id: str = "cause-a",
    trace_id: str = "trace-a",
    tenant_id: str = "tenant-a",
) -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=trace_id,
        tenant_id=tenant_id,
    )


def test_request_identity_is_deterministic_and_immutable() -> None:
    result = _result()
    context = _context()

    first = CognitiveClosedLoopRequest.from_result(
        result,
        context=context,
    )
    replay = CognitiveClosedLoopRequest.from_result(
        result,
        context=context,
    )

    assert first == replay
    assert first.request_id == replay.request_id

    with pytest.raises(AttributeError):
        first.request_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "context",
    [
        _context(correlation_id="correlation-b"),
        _context(causation_id="cause-b"),
        _context(trace_id="trace-b"),
        _context(tenant_id="tenant-b"),
    ],
    ids=[
        "correlation-isolated",
        "causation-isolated",
        "trace-isolated",
        "tenant-isolated",
    ],
)
def test_request_identity_is_scoped_to_propagation_context(
    context: EventPropagationContext,
) -> None:
    result = _result()

    original = CognitiveClosedLoopRequest.from_result(
        result,
        context=_context(),
    )
    isolated = CognitiveClosedLoopRequest.from_result(
        result,
        context=context,
    )

    assert original.request_id != isolated.request_id


class RecordingBackend:
    def __init__(self) -> None:
        self.contexts: list[EventPropagationContext] = []

    def run(
        self,
        result: CognitiveResult,
        *,
        context: EventPropagationContext | None = None,
        optimize: bool = True,
        recover: bool = True,
    ) -> LearningClosedLoopReport:
        if context is None:
            raise ValueError("context is required")

        self.contexts.append(context)

        return LearningClosedLoopReport(
            cycle_id=f"cycle:{len(self.contexts)}",
            result_id=result.result_id,
            goal_id=result.goal_id,
            status=ClosedLoopStatus.COMPLETED,
            created_at=NOW,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            optimize=optimize,
            recover=recover,
        )


def test_boundary_does_not_reuse_results_across_tenants() -> None:
    backend = RecordingBackend()
    boundary = CognitiveClosedLoopBoundary(backend)
    result = _result()

    tenant_a = boundary.request(
        result,
        context=_context(tenant_id="tenant-a"),
    )
    tenant_a_replay = boundary.request(
        result,
        context=_context(tenant_id="tenant-a"),
    )
    tenant_b = boundary.request(
        result,
        context=_context(tenant_id="tenant-b"),
    )

    assert tenant_a is tenant_a_replay
    assert tenant_a.request_id != tenant_b.request_id
    assert tenant_a is not tenant_b
    assert tenant_a.tenant_id == "tenant-a"
    assert tenant_b.tenant_id == "tenant-b"
    assert len(backend.contexts) == 2
    assert len(boundary.records()) == 2
