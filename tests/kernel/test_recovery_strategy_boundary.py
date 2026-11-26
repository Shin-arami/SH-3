from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security.persistent_store import (
    ReplayClaim,
    ReplayClaimStatus,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteReplayClaimStore,
    SQLiteReplayStageStore,
)
from kernel import SH3Kernel
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary, RecoveryStrategyResult
from self_healing.core import FailureSnapshot, SelfHealingCore

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


def _snapshot() -> FailureSnapshot:
    return FailureSnapshot.create(ValueError("strategy boundary"), {"operation": "strategy"})


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="strategy-correlation",
        trace_id="strategy-trace",
        tenant_id="strategy-tenant",
    )


def test_boundary_evaluates_and_selects_deterministically() -> None:
    healer = SelfHealingCore()
    boundary = RecoveryStrategyBoundary(healer)
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    assert isinstance(result, RecoveryStrategyResult)
    assert result.selected_strategy == "rebuild_context"
    assert [item.strategy for item in result.evaluations] == [
        "rebuild_context",
        "retry_safe",
        "fallback_default",
    ]
    assert result.selected.strategy == result.selected_strategy
    assert result.learned is False
    assert result.confidence == 0.0


def test_recovery_strategy_identity_is_context_scoped() -> None:
    healer = SelfHealingCore()
    boundary = RecoveryStrategyBoundary(healer)
    snapshot = _snapshot()
    first_context = _context()
    second_context = EventPropagationContext.create(
        correlation_id="strategy-correlation-other",
        causation_id="strategy-cause-other",
        trace_id="strategy-trace-other",
        tenant_id="strategy-tenant-other",
    )

    first = boundary.request(snapshot, context=first_context, created_at=NOW)
    replay = boundary.request(snapshot, context=first_context, created_at=NOW)
    other_trace = boundary.request(snapshot, context=second_context, created_at=NOW)

    assert first.request_id == replay.request_id
    assert first.request_id != other_trace.request_id


def test_boundary_uses_existing_learned_selection() -> None:
    from services.learning import LearningService

    learning = LearningService()
    learning.start()
    for _ in range(3):
        learning.record("self_healing.recovery", 1.0, success=True, details={"strategy": "retry_safe"})
        learning.record("self_healing.recovery", 0.0, success=False, details={"strategy": "rebuild_context"})
    healer = SelfHealingCore(learning_service=learning)
    boundary = RecoveryStrategyBoundary(healer)
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    assert result.selected_strategy == "retry_safe"
    rates = {item.strategy: item.success_rate for item in result.evaluations}
    assert rates["retry_safe"] == 1.0
    assert rates["rebuild_context"] == 0.0


def test_event_path_preserves_causation_and_contract() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer = SelfHealingCore(event_publisher=publisher)
    boundary = RecoveryStrategyBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="strategy-audit", handler=events.append, priority=200))
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    names = [event.name for event in events]
    assert result.selected_strategy == "rebuild_context"
    assert names == ["RecoveryStrategyRequested", "RecoveryStrategyEvaluated", "RecoveryStrategySelected"]
    assert all(event.category is Category.STRATEGY for event in events)
    assert events[0].event_type is EventType.START
    assert events[1].event_type is EventType.UPDATED
    assert events[2].event_type is EventType.COMPLETE
    assert events[1].metadata.causation_id == events[0].metadata.event_id
    assert events[2].metadata.causation_id == events[1].metadata.event_id
    assert result.correlation_id == "strategy-correlation"
    assert result.trace_id == "strategy-trace"
    assert result.tenant_id == "strategy-tenant"


def test_boundary_is_idempotent_and_thread_safe() -> None:
    healer = SelfHealingCore()
    boundary = RecoveryStrategyBoundary(healer)
    snapshot = _snapshot()
    context = _context()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _: boundary.request(snapshot, context=context, created_at=NOW), range(32)))
    assert all(item is results[0] for item in results)
    assert len(boundary.records()) == 1


def test_publisher_replacement_rebinds_subscription() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    boundary = RecoveryStrategyBoundary(SelfHealingCore(), EventBusPublisher(first_bus))
    assert first_bus.router.contains("recovery.strategy-boundary")
    boundary.set_event_publisher(EventBusPublisher(second_bus))
    assert not first_bus.router.contains("recovery.strategy-boundary")
    assert second_bus.router.contains("recovery.strategy-boundary")


def test_kernel_ownership_and_optimizer_healing_use_strategy_boundary() -> None:
    kernel = SH3Kernel()
    assert kernel.recovery_strategy_boundary is kernel.learning_feedback_loop.recovery_strategy_boundary
    assert kernel.optimizer_healing_boundary.strategy_boundary is kernel.recovery_strategy_boundary


def test_serialized_result_is_immutable() -> None:
    boundary = RecoveryStrategyBoundary(SelfHealingCore())
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    data = result.to_dict()
    data["evaluations"][0]["strategy"] = "mutated"
    assert result.evaluations[0].strategy != "mutated"

class _CountingStrategyBackend(SelfHealingCore):
    def __init__(self, event_publisher: EventBusPublisher | None = None) -> None:
        super().__init__(event_publisher=event_publisher)
        self.evaluation_calls = 0
        self.selection_calls = 0

    def evaluate_strategies(
        self,
        snapshot: FailureSnapshot,
    ) -> Mapping[str, tuple[int, int, float]]:
        self.evaluation_calls += 1
        return super().evaluate_strategies(snapshot)

    def select_strategy(self, snapshot: FailureSnapshot) -> str:
        self.selection_calls += 1
        return super().select_strategy(snapshot)


def _persistent_recovery_input() -> dict[str, str]:
    return {
        "source": "cognition",
        "result_id": "result:p2-1-recovery",
        "error_type": "ValueError",
        "error_message": "stable recovery failure",
    }


def _persistent_request(
    boundary: RecoveryStrategyBoundary,
    snapshot: FailureSnapshot,
    context: EventPropagationContext,
    claim: ReplayClaim,
) -> RecoveryStrategyResult:
    owner_token = claim.owner_token
    generation = claim.generation
    return boundary.request(
        snapshot,
        context=context,
        created_at=NOW,
        replay_cycle_id="learning-cycle:result:p2-1-recovery",
        replay_cycle_fingerprint="sha256:p2-1-recovery-strategy",
        replay_claim_owner_token=owner_token,
        replay_claim_generation=generation,
        replay_stage_input=_persistent_recovery_input(),
    )


def test_recovery_strategy_stage_is_reused_after_claim_takeover(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-strategy-stage.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    cycle_id = "learning-cycle:result:p2-1-recovery"
    fingerprint = "sha256:p2-1-recovery-strategy"
    first_claim = claims.claim(cycle_id, fingerprint, lease_seconds=60.0)
    assert first_claim.status is ReplayClaimStatus.CLAIMED
    assert first_claim.owner_token is not None

    first_bus = EventBus()
    first_publisher = EventBusPublisher(first_bus)
    first_backend = _CountingStrategyBackend(first_publisher)
    first_boundary = RecoveryStrategyBoundary(
        first_backend,
        first_publisher,
        replay_stage_store=stages,
    )
    first_events: list[Event] = []
    first_bus.subscribe(
        EventSubscription(
            subscriber_id="p2-1-first-audit",
            handler=first_events.append,
            priority=200,
        )
    )
    first_snapshot = FailureSnapshot.create(
        ValueError("stable recovery failure"),
        {"source": "cognition", "cycle_id": cycle_id, "result_id": "result:p2-1-recovery"},
    )
    first_context = EventPropagationContext.create(
        correlation_id="p2-1-correlation-first",
        trace_id="p2-1-trace-first",
        tenant_id="p2-1-tenant",
    )
    first_result = _persistent_request(
        first_boundary,
        first_snapshot,
        first_context,
        first_claim,
    )

    stage_key = ReplayStageKey.create(
        cycle_id,
        fingerprint,
        "recovery_strategy.select.v1",
        {
            "contract": "recovery-strategy-v1",
            "recovery_input": _persistent_recovery_input(),
        },
    )
    stored = stages.get(stage_key)
    assert stored is not None
    assert stored.status is ReplayStageStatus.COMPLETED
    assert stored.result is not None
    assert stored.result["contract"] == "recovery-strategy-v1"
    assert first_backend.evaluation_calls == 1
    assert first_backend.selection_calls == 1
    assert [event.name for event in first_events] == [
        "RecoveryStrategyRequested",
        "RecoveryStrategyEvaluated",
        "RecoveryStrategySelected",
    ]
    assert first_events[0].payload["idempotency_key"] == stage_key.idempotency_key
    assert first_events[0].payload["replayed"] is False

    assert claims.release(cycle_id, first_claim.owner_token, first_claim.generation)
    second_claim = claims.claim(
        cycle_id,
        fingerprint,
        lease_seconds=60.0,
        now=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert second_claim.status is ReplayClaimStatus.CLAIMED
    assert second_claim.owner_token is not None
    assert second_claim.generation == first_claim.generation + 1

    second_bus = EventBus()
    second_publisher = EventBusPublisher(second_bus)
    second_backend = _CountingStrategyBackend(second_publisher)
    second_boundary = RecoveryStrategyBoundary(
        second_backend,
        second_publisher,
        replay_stage_store=stages,
    )
    second_events: list[Event] = []
    second_bus.subscribe(
        EventSubscription(
            subscriber_id="p2-1-second-audit",
            handler=second_events.append,
            priority=200,
        )
    )
    second_snapshot = FailureSnapshot.create(
        ValueError("stable recovery failure"),
        {"source": "cognition", "cycle_id": cycle_id, "result_id": "result:p2-1-recovery"},
    )
    second_context = EventPropagationContext.create(
        correlation_id="p2-1-correlation-second",
        causation_id="p2-1-retry-event",
        trace_id="p2-1-trace-second",
        tenant_id="p2-1-tenant",
    )
    replayed_result = _persistent_request(
        second_boundary,
        second_snapshot,
        second_context,
        second_claim,
    )

    assert first_snapshot.trace_id != second_snapshot.trace_id
    assert first_result.request_id != replayed_result.request_id
    assert first_result.failure_id != replayed_result.failure_id
    assert replayed_result.selected_strategy == first_result.selected_strategy
    assert replayed_result.evaluations == first_result.evaluations
    assert replayed_result.learned == first_result.learned
    assert replayed_result.correlation_id == second_context.correlation_id
    assert replayed_result.trace_id == second_context.trace_id
    assert replayed_result.metadata["idempotency_key"] == stage_key.idempotency_key
    assert replayed_result.metadata["replayed"] is True
    assert second_backend.evaluation_calls == 0
    assert second_backend.selection_calls == 0
    assert [event.name for event in second_events] == [
        "RecoveryStrategyRequested",
        "RecoveryStrategyEvaluated",
        "RecoveryStrategySelected",
    ]
    assert second_events[0].payload["replayed"] is True
    assert second_events[0].payload["idempotency_key"] == stage_key.idempotency_key
    assert second_events[1].payload["replayed"] is True
    assert second_events[2].payload["replayed"] is True


def test_persistent_recovery_requires_complete_claim_metadata(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery-strategy-validation.sqlite3"
    claims = SQLiteReplayClaimStore(database)
    stages = SQLiteReplayStageStore(database)
    _ = claims
    boundary = RecoveryStrategyBoundary(
        SelfHealingCore(),
        replay_stage_store=stages,
    )

    with pytest.raises(ValueError, match="complete replay claim metadata"):
        boundary.request(
            _snapshot(),
            context=_context(),
            replay_cycle_id="cycle:partial",
            replay_stage_input=_persistent_recovery_input(),
        )

    # Direct/non-persistent callers retain the legacy in-memory behavior.
    result = boundary.request(_snapshot(), context=_context(), created_at=NOW)
    assert result.selected_strategy == "rebuild_context"
    assert stages.get(
        ReplayStageKey.create(
            "cycle:partial",
            "sha256:partial",
            "recovery_strategy.select.v1",
            {
                "contract": "recovery-strategy-v1",
                "recovery_input": _persistent_recovery_input(),
            },
        )
    ) is None
