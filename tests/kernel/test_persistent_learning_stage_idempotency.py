from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from cognition.contracts import (
    CognitiveGoal,
    CognitiveResult,
    CognitiveResultStatus,
)
from cognition.policy import PolicyRule
from infrastructure.event_bus import EventBus, PublishResult
from infrastructure.events import EventPropagationContext
from infrastructure.security.persistent_replay_ops import check_database
from infrastructure.security.persistent_store import (
    ReplayClaimStatus,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel.cognitive_learning_boundary import (
    CognitiveLearningBoundary,
    CognitiveLearningRequest,
)
from kernel.core import SH3Kernel
from kernel.learning_loop import LearningLoop
from kernel.persistent_factory import create_persistent_sh3_kernel

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)
CYCLE_FINGERPRINT = "sha256:p1-2b-learning-stage"


class RecordingLearning:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail
        self.idempotency_keys: list[str | None] = []

    def run(
        self,
        execution_result: dict[str, Any],
        *,
        context: EventPropagationContext | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        self.idempotency_keys.append(idempotency_key)
        if self.fail:
            raise RuntimeError("persistent learning stage failure")
        return {
            "loop_id": "learning:p1-2b",
            "score": 0.8,
            "memory_key": "memory:p1-2b",
            "input": execution_result,
        }


class LegacyLearning:
    def run(
        self,
        execution_result: dict[str, Any],
        *,
        context: EventPropagationContext | None = None,
    ) -> dict[str, Any]:
        return {"loop_id": "legacy-learning"}


def _result() -> CognitiveResult:
    goal = CognitiveGoal.create(
        "verify persistent learning stage idempotency",
        owner="test",
        created_at=NOW,
        correlation_id="corr:p1-2b",
        trace_id="trace:p1-2b",
        tenant_id="tenant:p1-2b",
    )
    return CognitiveResult.create(
        goal,
        status=CognitiveResultStatus.SUCCESS,
        created_at=NOW,
        result_id="result:p1-2b",
        output={
            "goal": goal.to_dict(),
            "plan": {"steps": ["verify persistent learning stage idempotency"]},
            "decision": {"selected_option": "verify"},
        },
        correlation_id=goal.correlation_id,
        trace_id=goal.trace_id,
        tenant_id=goal.tenant_id,
    )


def _context(causation_id: str = "result:p1-2b") -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="corr:p1-2b",
        causation_id=causation_id,
        trace_id="trace:p1-2b",
        tenant_id="tenant:p1-2b",
    )


def _record_with_claim(
    boundary: CognitiveLearningBoundary,
    result: CognitiveResult,
    context: EventPropagationContext,
    claim: Any,
) -> Any:
    assert claim.owner_token is not None
    return boundary.record(
        result,
        context=context,
        created_at=NOW,
        replay_cycle_id=f"learning-cycle:{result.result_id}",
        replay_cycle_fingerprint=CYCLE_FINGERPRINT,
        replay_claim_owner_token=claim.owner_token,
        replay_claim_generation=claim.generation,
    )


def test_completed_learning_stage_is_reused_after_generation_takeover(
    tmp_path: Path,
) -> None:
    database = tmp_path / "learning-stage-replay.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"

    first_claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=60.0,
        now=datetime.now(UTC),
    )

    assert first_claim.status is ReplayClaimStatus.CLAIMED
    assert first_claim.owner_token is not None

    first_backend = RecordingLearning()
    first_boundary = CognitiveLearningBoundary(
        first_backend,
        replay_stage_store=stages,
    )
    first_context = _context()

    first_result = _record_with_claim(
        first_boundary,
        result,
        first_context,
        first_claim,
    )

    request = CognitiveLearningRequest.from_result(
        result,
        context=first_context,
        created_at=NOW,
    )
    stage_key = ReplayStageKey.create(
        cycle_id,
        CYCLE_FINGERPRINT,
        "cognitive_learning.record.v1",
        {
            "contract": "cognitive-learning-v1",
            "learning_input": dict(request.learning_input),
        },
    )

    stored = stages.get(stage_key)
    assert stored is not None
    assert stored.status is ReplayStageStatus.COMPLETED
    assert first_backend.calls == 1
    assert first_backend.idempotency_keys == [stage_key.idempotency_key]

    assert claims.release(
        cycle_id,
        first_claim.owner_token,
        first_claim.generation,
    )

    second_claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=60.0,
        now=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert second_claim.status is ReplayClaimStatus.CLAIMED
    assert second_claim.owner_token is not None
    assert second_claim.generation == first_claim.generation + 1

    second_backend = RecordingLearning()
    second_boundary = CognitiveLearningBoundary(
        second_backend,
        replay_stage_store=stages,
    )
    replay_context = _context("retry-event:p1-2b")

    replayed_result = _record_with_claim(
        second_boundary,
        result,
        replay_context,
        second_claim,
    )

    replay_request = CognitiveLearningRequest.from_result(
        result,
        context=replay_context,
        created_at=NOW,
    )

    assert replay_request.request_id != request.request_id
    assert replayed_result.request_id == replay_request.request_id
    assert replayed_result.success is True
    assert replayed_result.learning == first_result.learning
    assert second_backend.calls == 0
    persisted_stage = stages.get(stage_key)
    assert persisted_stage is not None
    assert persisted_stage.status is ReplayStageStatus.COMPLETED


def test_failed_learning_result_is_durably_reused_after_takeover(
    tmp_path: Path,
) -> None:
    database = tmp_path / "learning-stage-failure.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    result = _result()
    cycle_id = f"learning-cycle:{result.result_id}"

    first_claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=60.0,
        now=datetime.now(UTC),
    )

    assert first_claim.owner_token is not None

    first_backend = RecordingLearning(fail=True)
    first_boundary = CognitiveLearningBoundary(
        first_backend,
        replay_stage_store=stages,
    )
    failed_result = _record_with_claim(
        first_boundary,
        result,
        _context(),
        first_claim,
    )

    assert failed_result.success is False
    assert "persistent learning stage failure" in (failed_result.error or "")
    assert first_backend.calls == 1

    assert claims.release(
        cycle_id,
        first_claim.owner_token,
        first_claim.generation,
    )

    second_claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=60.0,
        now=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert second_claim.owner_token is not None

    second_backend = RecordingLearning()
    second_boundary = CognitiveLearningBoundary(
        second_backend,
        replay_stage_store=stages,
    )
    replayed = _record_with_claim(
        second_boundary,
        result,
        _context("retry-event:p1-2b-failure"),
        second_claim,
    )

    assert replayed.success is False
    assert replayed.error == failed_result.error
    assert second_backend.calls == 0


def test_persistent_boundary_requires_claim_context(
    tmp_path: Path,
) -> None:
    database = tmp_path / "learning-stage-claim-required.sqlite3"
    SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    backend = RecordingLearning()
    boundary = CognitiveLearningBoundary(
        backend,
        replay_stage_store=stages,
    )

    with pytest.raises(ValueError, match="complete replay claim metadata"):
        boundary.record(
            _result(),
            context=_context(),
            created_at=NOW,
        )

    assert backend.calls == 0


def test_persistent_boundary_rejects_backend_without_idempotency_support(
    tmp_path: Path,
) -> None:
    database = tmp_path / "learning-stage-backend-contract.sqlite3"
    SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)

    with pytest.raises(TypeError, match="idempotency_key"):
        CognitiveLearningBoundary(
            LegacyLearning(),
            replay_stage_store=stages,
        )


def test_learning_loop_reuses_same_stage_result_without_duplicate_effects() -> None:
    kernel = SH3Kernel()
    kernel.policy.add_rule(PolicyRule("stage-idempotency-test", weight=1.0))

    execution_result = {
        "goal": "verify learning stage",
        "plan": {
            "tree": {
                "children": ["one", "two", "three", "four", "five"],
            }
        },
        "decision": "continue",
        "result_id": "result:learning-loop-stage",
        "success": True,
    }

    first = kernel.learning_loop.run(
        execution_result,
        idempotency_key="sh3-stage-v1:learning-loop-test",
    )
    first_snapshot = kernel.memory.snapshot()
    first_weight = kernel.policy.rules[0].weight
    first_chunk_size = kernel.planner.chunk_size

    replay = kernel.learning_loop.run(
        execution_result,
        idempotency_key="sh3-stage-v1:learning-loop-test",
    )

    assert replay == first
    assert kernel.memory.snapshot() == first_snapshot
    assert len(kernel.memory.timeline()) == 1
    assert kernel.policy.rules[0].weight == first_weight
    assert kernel.planner.chunk_size == first_chunk_size
    assert first_weight == pytest.approx(1.02)
    assert first_chunk_size == 3


def test_persistent_coordinator_passes_stage_key_to_learning_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "learning-stage-coordinator.sqlite3"
    runtime = create_persistent_sh3_kernel(
        database,
        create_if_missing=True,
    )

    observed_keys: list[str | None] = []
    original_run = LearningLoop.run

    def track_run(
        self: LearningLoop,
        execution_result: dict[str, Any],
        *,
        context: EventPropagationContext | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        observed_keys.append(idempotency_key)
        return original_run(
            self,
            execution_result,
            context=context,
            idempotency_key=idempotency_key,
        )

    monkeypatch.setattr(LearningLoop, "run", track_run)

    report = runtime.kernel.learning_feedback_loop.run(
        _result(),
        optimize=False,
        recover=False,
    )

    assert report.status.value == "completed"
    assert report.replay_claim_generation == 1
    assert len(observed_keys) == 1
    assert observed_keys[0] is not None
    assert observed_keys[0].startswith("sh3-stage-v1:")
    assert check_database(database).replay_stage_execution_count == 1

class RecordingPublisher:
    """Capture events while exposing the EventBus marker expected by boundaries."""

    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.events: list[Any] = []

    def publish(self, event: Any) -> PublishResult:
        self.events.append(event)
        return PublishResult(
            event_id=event.id,
            accepted=True,
            queued=True,
            delivered=True,
        )


def _learning_stage_key(
    result: CognitiveResult,
    context: EventPropagationContext,
) -> ReplayStageKey:
    request = CognitiveLearningRequest.from_result(
        result, context=context, created_at=NOW
    )
    return ReplayStageKey.create(
        f"learning-cycle:{result.result_id}",
        CYCLE_FINGERPRINT,
        "cognitive_learning.record.v1",
        {
            "contract": "cognitive-learning-v1",
            "learning_input": dict(request.learning_input),
        },
    )


def test_same_request_id_with_different_learning_input_uses_distinct_stages(
    tmp_path: Path,
) -> None:
    database = tmp_path / "learning-same-request-different-input.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    first_result = _result()
    second_output = dict(first_result.output)
    second_plan = dict(second_output["plan"])
    second_plan["steps"] = ["a different learning step"]
    second_output["plan"] = second_plan
    second_result = replace(first_result, output=second_output)
    context = _context()

    first_request = CognitiveLearningRequest.from_result(
        first_result, context=context, created_at=NOW
    )
    second_request = CognitiveLearningRequest.from_result(
        second_result, context=context, created_at=NOW
    )
    assert first_request.request_id == second_request.request_id
    assert first_request.learning_input != second_request.learning_input

    cycle_id = f"learning-cycle:{first_result.result_id}"
    claim = claims.claim(
        cycle_id, CYCLE_FINGERPRINT, lease_seconds=60.0, now=datetime.now(UTC)
    )
    backend = RecordingLearning()
    boundary = CognitiveLearningBoundary(backend, replay_stage_store=stages)

    first_value = _record_with_claim(boundary, first_result, context, claim)
    second_value = _record_with_claim(boundary, second_result, context, claim)
    first_key = _learning_stage_key(first_result, context)
    second_key = _learning_stage_key(second_result, context)

    assert first_key.idempotency_key != second_key.idempotency_key
    assert first_value.request_id == second_value.request_id
    assert backend.calls == 2
    assert backend.idempotency_keys == [
        first_key.idempotency_key,
        second_key.idempotency_key,
    ]
    assert first_value.learning["input"] != second_value.learning["input"]


@pytest.mark.parametrize("fail", [False, True])
def test_persistent_cognitive_events_propagate_the_same_stage_key(
    tmp_path: Path,
    fail: bool,
) -> None:
    database = tmp_path / f"learning-event-key-{fail}.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    result = _result()
    context = _context()
    claim = claims.claim(
        f"learning-cycle:{result.result_id}",
        CYCLE_FINGERPRINT,
        lease_seconds=60.0,
        now=datetime.now(UTC),
    )
    publisher = RecordingPublisher()
    backend = RecordingLearning(fail=fail)
    boundary = CognitiveLearningBoundary(
        backend, event_publisher=publisher, replay_stage_store=stages
    )

    _record_with_claim(boundary, result, context, claim)
    key = _learning_stage_key(result, context).idempotency_key
    terminal_name = (
        "CognitiveLearningFailed" if fail else "CognitiveLearningCompleted"
    )
    events = {event.metadata.event_name: event for event in publisher.events}
    assert "CognitiveLearningRequested" in events
    assert terminal_name in events
    assert events["CognitiveLearningRequested"].payload["idempotency_key"] == key
    assert events[terminal_name].payload["idempotency_key"] == key


def test_native_learning_loop_events_propagate_stage_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "sh3-stage-v1:native-learning-event-test"
    execution_result = {
        "goal": "verify native learning event key propagation",
        "plan": {"tree": {"children": ["one", "two"]}},
        "decision": "continue",
        "success": True,
    }
    success_publisher = RecordingPublisher()
    success_loop = LearningLoop(SH3Kernel(), event_publisher=success_publisher)
    success_loop.run(execution_result, idempotency_key=key)
    successful = {
        event.metadata.event_name: event for event in success_publisher.events
    }
    for name in (
        "LearningStarted",
        "LearningRecordCreated",
        "LearningResultRecorded",
        "LearningCompleted",
    ):
        assert successful[name].payload["idempotency_key"] == key

    failure_publisher = RecordingPublisher()
    failure_loop = LearningLoop(SH3Kernel(), event_publisher=failure_publisher)

    def fail_store(
        self: LearningLoop,
        experience: dict[str, Any],
        score: float,
        *,
        idempotency_key: str | None = None,
    ) -> str:
        del self, experience, score, idempotency_key
        raise RuntimeError("injected learning store failure")

    monkeypatch.setattr(LearningLoop, "store_experience", fail_store)
    with pytest.raises(RuntimeError, match="injected learning store failure"):
        failure_loop.run(execution_result, idempotency_key=key)
    failed_event = next(
        event for event in failure_publisher.events
        if event.metadata.event_name == "LearningFailed"
    )
    assert failed_event.payload["idempotency_key"] == key


def test_learning_loop_cached_result_is_deep_copied() -> None:
    loop = LearningLoop(SH3Kernel())
    execution_result = {
        "goal": "verify defensive stage result cache",
        "plan": {"tree": {"children": ["one"]}},
        "decision": "continue",
        "success": True,
    }
    key = "sh3-stage-v1:deep-copy-cache-test"
    first = loop.run(execution_result, idempotency_key=key)
    first["experience"]["goal"] = "caller mutation"

    replay = loop.run(execution_result, idempotency_key=key)
    assert replay["experience"]["goal"] == execution_result["goal"]


def test_backend_retry_after_stage_completion_write_failure_reuses_stage_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retry after the backend effect but before Stage completion keeps its key."""
    database = tmp_path / "learning-stage-completion-crash-window.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    result = _result()
    context = _context()
    cycle_id = f"learning-cycle:{result.result_id}"
    first_claim_time = datetime.now(UTC)

    first_claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=5.0,
        now=first_claim_time,
    )
    assert first_claim.status is ReplayClaimStatus.CLAIMED
    assert first_claim.owner_token is not None

    backend = RecordingLearning()
    boundary = CognitiveLearningBoundary(backend, replay_stage_store=stages)

    def fail_completion_write(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("injected crash before Stage completion commit")

    # Model a process crash after backend execution but before the durable
    # Stage completion write. The claimed row must remain available for takeover.
    with monkeypatch.context() as patcher:
        patcher.setattr(
            SQLiteReplayStageStore,
            "complete",
            fail_completion_write,
        )
        with pytest.raises(
            RuntimeError,
            match="injected crash before Stage completion commit",
        ):
            _record_with_claim(boundary, result, context, first_claim)

    assert backend.calls == 1
    first_key = backend.idempotency_keys[0]
    assert first_key is not None

    stage_key = _learning_stage_key(result, context)
    assert first_key == stage_key.idempotency_key
    incomplete = stages.get(stage_key)
    assert incomplete is not None
    assert incomplete.status is ReplayStageStatus.CLAIMED
    assert incomplete.attempts == 1

    # Advance the claim clock beyond the first lease without sleeping.
    takeover_time = max(
        first_claim_time + timedelta(seconds=6),
        datetime.now(UTC),
    )
    second_claim = claims.claim(
        cycle_id,
        CYCLE_FINGERPRINT,
        lease_seconds=60.0,
        now=takeover_time,
    )
    assert second_claim.status is ReplayClaimStatus.CLAIMED
    assert second_claim.owner_token is not None
    assert second_claim.generation == first_claim.generation + 1

    replayed = _record_with_claim(boundary, result, context, second_claim)

    assert replayed.success is True
    assert backend.calls == 2
    assert backend.idempotency_keys == [first_key, first_key]

    completed = stages.get(stage_key)
    assert completed is not None
    assert completed.status is ReplayStageStatus.COMPLETED
    assert completed.attempts == 2
