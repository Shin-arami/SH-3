from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from foundation.Enums.category import Category
from foundation.Enums.event import EventType
from infrastructure.event_bus import EventBus, EventBusPublisher, EventSubscription
from infrastructure.events import Event, EventPropagationContext
from infrastructure.security.persistent_store import (
    ReplayStageExecution,
    ReplayStageKey,
    ReplayStageStatus,
    SQLiteReplayStageStore,
)
from kernel import SH3Kernel
from kernel.recovery_execution_boundary import (
    RecoveryExecutionBoundary,
    RecoveryExecutionRequest,
    RecoveryExecutionResult,
)
from kernel.recovery_strategy_boundary import RecoveryStrategyBoundary, RecoveryStrategyResult
from runtime.context_manager import ContextManager
from self_healing.core import FailureSnapshot, SelfHealingCore

NOW = datetime(2026, 10, 6, 0, 0, tzinfo=UTC)


def _snapshot(message: str = "execution boundary") -> FailureSnapshot:
    return FailureSnapshot.create(ValueError(message), {"operation": "execution"})


def _context() -> EventPropagationContext:
    return EventPropagationContext.create(
        correlation_id="execution-correlation",
        trace_id="execution-trace",
        tenant_id="execution-tenant",
    )


def _strategy_result(
    healer: SelfHealingCore | None = None,
) -> tuple[SelfHealingCore, RecoveryStrategyBoundary, RecoveryStrategyResult, FailureSnapshot]:
    current = healer or SelfHealingCore()
    strategy = RecoveryStrategyBoundary(current)
    snapshot = _snapshot()
    result = strategy.request(snapshot, context=_context(), created_at=NOW)
    return current, strategy, result, snapshot


def test_recovery_execution_identity_is_context_scoped() -> None:
    _, _, strategy_result, snapshot = _strategy_result()
    first_context = _context()
    second_context = EventPropagationContext.create(
        correlation_id="execution-correlation-other",
        causation_id="execution-cause-other",
        trace_id="execution-trace-other",
        tenant_id="execution-tenant-other",
    )

    first = RecoveryExecutionRequest.from_strategy(
        strategy_result, snapshot=snapshot, context=first_context, created_at=NOW
    )
    replay = RecoveryExecutionRequest.from_strategy(
        strategy_result, snapshot=snapshot, context=first_context, created_at=NOW
    )
    other_trace = RecoveryExecutionRequest.from_strategy(
        strategy_result, snapshot=snapshot, context=second_context, created_at=NOW
    )

    assert first.request_id == replay.request_id
    assert first.request_id != other_trace.request_id


def test_boundary_executes_selected_strategy_directly() -> None:
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer)
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    assert isinstance(result, RecoveryExecutionResult)
    assert result.success is True
    assert result.strategy == "rebuild_context"
    assert result.error is None
    assert result.result is not None


def test_event_path_preserves_causation_and_contract() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="execution-audit", handler=events.append, priority=200))
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    relevant = [event for event in events if event.name.startswith("RecoveryExecution")]
    assert [event.name for event in relevant] == ["RecoveryExecutionRequested", "RecoveryExecutionCompleted"]
    assert relevant[0].category is Category.ACTION
    assert relevant[0].event_type is EventType.START
    assert relevant[1].event_type is EventType.COMPLETE
    assert relevant[1].metadata.causation_id == relevant[0].metadata.event_id
    assert result.correlation_id == "execution-correlation"
    assert result.trace_id == "execution-trace"
    assert result.tenant_id == "execution-tenant"


def test_event_versions_are_canonical() -> None:
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="execution-version", handler=events.append, priority=-100))
    boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    relevant = [event for event in events if event.name.startswith("RecoveryExecution")]
    assert relevant
    assert all(event.metadata.event_version == "1.0.0" for event in relevant)


def test_boundary_is_idempotent_and_thread_safe() -> None:
    healer, _, strategy_result, snapshot = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer)
    context = _context()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(
            executor.map(
                lambda _: boundary.request(strategy_result, snapshot, context=context, created_at=NOW),
                range(32),
            )
        )
    assert all(item is results[0] for item in results)
    assert len(boundary.records()) == 1


def test_publisher_replacement_rebinds_subscription() -> None:
    first_bus = EventBus()
    second_bus = EventBus()
    boundary = RecoveryExecutionBoundary(SelfHealingCore(), EventBusPublisher(first_bus))
    assert first_bus.router.contains("recovery.execution-boundary")
    boundary.set_event_publisher(EventBusPublisher(second_bus))
    assert not first_bus.router.contains("recovery.execution-boundary")
    assert second_bus.router.contains("recovery.execution-boundary")


def test_failure_is_captured_as_typed_result() -> None:
    class FailingHealer(SelfHealingCore):
        def recover_with_strategy(
        self,
        snapshot: FailureSnapshot,
        strategy: str,
        *,
        idempotency_key: str | None = None,
    ) -> Any:
            raise RuntimeError("execution failure")

    failing = FailingHealer()
    snapshot = _snapshot()
    strategy_result = RecoveryStrategyBoundary(failing).request(
        snapshot,
        context=_context(),
        created_at=NOW,
    )
    boundary = RecoveryExecutionBoundary(failing)
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    assert result.success is False
    assert result.error == "execution failure"
    assert result.result is None


def test_failure_event_is_published() -> None:
    class FailingHealer(SelfHealingCore):
        def recover_with_strategy(
        self,
        snapshot: FailureSnapshot,
        strategy: str,
        *,
        idempotency_key: str | None = None,
    ) -> Any:
            raise RuntimeError("execution failure")

    bus = EventBus()
    publisher = EventBusPublisher(bus)
    healer = FailingHealer()
    snapshot = _snapshot()
    strategy_result = RecoveryStrategyBoundary(healer).request(snapshot, context=_context(), created_at=NOW)
    boundary = RecoveryExecutionBoundary(healer, publisher)
    events: list[Event] = []
    bus.subscribe(EventSubscription(subscriber_id="execution-failure-audit", handler=events.append, priority=200))
    result = boundary.request(strategy_result, snapshot, context=_context(), created_at=NOW)
    relevant = [event for event in events if event.name.startswith("RecoveryExecution")]
    assert result.success is False
    assert [event.name for event in relevant] == ["RecoveryExecutionRequested", "RecoveryExecutionFailed"]
    assert relevant[-1].event_type is EventType.FAILURE
    assert relevant[-1].causation_id == relevant[0].id
    assert relevant[-1].payload["error"] == "execution failure"


def test_kernel_owns_shared_execution_boundary() -> None:
    kernel = SH3Kernel()
    assert kernel.recovery_execution_boundary is kernel.learning_feedback_loop.recovery_execution_boundary
    assert kernel.optimizer_healing_boundary.execution_boundary is kernel.recovery_execution_boundary


def test_kernel_recover_uses_execution_boundary() -> None:
    kernel = SH3Kernel()
    result = kernel.recover(RuntimeError("kernel recovery"), {"operation": "kernel"})
    assert result is not None
    assert kernel.recovery_execution_boundary.records()


def test_request_rejects_mismatched_failure() -> None:
    healer, _, strategy_result, _ = _strategy_result()
    boundary = RecoveryExecutionBoundary(healer)
    other = _snapshot("other")
    with pytest.raises(ValueError, match="failure_id"):
        boundary.request(strategy_result, other, context=_context(), created_at=NOW)


def test_request_requires_strategy_result_type() -> None:
    boundary = RecoveryExecutionBoundary(SelfHealingCore())
    with pytest.raises(TypeError, match="RecoveryStrategyResult"):
        boundary.request(cast(RecoveryStrategyResult, object()), _snapshot(), context=_context(), created_at=NOW)


# P2-2 persistent recovery execution regression coverage.
class _P22FakeReplayStageStore(SQLiteReplayStageStore):
    def __init__(self) -> None:
        self.completed: dict[str, ReplayStageExecution] = {}
        self.begin_calls: list[tuple[str, str, int]] = []
        self.complete_calls: list[tuple[str, str, int]] = []

    def begin(
        self,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        *,
        now: datetime | None = None,
    ) -> ReplayStageExecution:
        self.begin_calls.append((key.idempotency_key, owner_token, generation))
        persisted = self.completed.get(key.idempotency_key)
        if persisted is not None:
            return persisted
        return ReplayStageExecution(
            key=key,
            status=ReplayStageStatus.CLAIMED,
            generation=generation,
            attempts=1,
            owner_token=owner_token,
        )

    def complete(
        self,
        key: ReplayStageKey,
        owner_token: str,
        generation: int,
        result: Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> ReplayStageExecution:
        self.complete_calls.append((key.idempotency_key, owner_token, generation))
        execution = ReplayStageExecution(
            key=key,
            status=ReplayStageStatus.COMPLETED,
            generation=generation,
            attempts=1,
            owner_token=None,
            result=dict(result),
        )
        self.completed[key.idempotency_key] = execution
        return execution


def _p2_2_fake_replay_stage_store() -> _P22FakeReplayStageStore:
    return _P22FakeReplayStageStore()


class _PersistentReplayCountingHealer(SelfHealingCore):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.execution_calls = 0
        self.idempotency_keys: list[str | None] = []
        self.fail = fail

    def recover_with_strategy(
        self,
        snapshot: FailureSnapshot,
        strategy: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        self.execution_calls += 1
        self.idempotency_keys.append(idempotency_key)
        if self.fail:
            raise RuntimeError("persistent recovery failure")
        return {
            "status": "recovered",
            "strategy": strategy,
            "trace_id": snapshot.trace_id,
        }


def _p2_2_replay_arguments(
    *,
    generation: int,
    owner: str = "execution-owner",
    result_id: str = "result-1",
    error_message: str = "boom",
) -> dict[str, Any]:
    return {
        "replay_cycle_id": "execution-cycle",
        "replay_cycle_fingerprint": "execution-cycle-fingerprint",
        "replay_claim_owner_token": owner,
        "replay_claim_generation": generation,
        "replay_stage_input": {
            "source": "learning_feedback_loop",
            "result_id": result_id,
            "error_type": "ValueError",
            "error_message": error_message,
        },
    }


def test_persistent_recovery_execution_rejects_backend_without_idempotency_contract() -> None:
    class LegacyBackend:
        def recover_with_strategy(
            self,
            snapshot: FailureSnapshot,
            strategy: str,
        ) -> dict[str, str]:
            return {"strategy": strategy}

    store = _p2_2_fake_replay_stage_store()
    with pytest.raises(TypeError, match="must accept idempotency_key"):
        RecoveryExecutionBoundary(
            LegacyBackend(),
            replay_stage_store=store,
        )


def test_recovery_execution_propagates_stage_key_into_self_healing_action_and_events() -> None:
    class KeyAwareHealer(SelfHealingCore):
        def __init__(self) -> None:
            super().__init__()
            self.action_idempotency_key: str | None = None

        def _rebuild(
            self,
            snapshot: FailureSnapshot,
            *,
            idempotency_key: str | None = None,
        ) -> dict[str, Any]:
            self.action_idempotency_key = idempotency_key
            return super()._rebuild(
                snapshot,
                idempotency_key=idempotency_key,
            )

    store = _p2_2_fake_replay_stage_store()
    healer = KeyAwareHealer()
    snapshot = _snapshot()
    strategy = RecoveryStrategyBoundary(healer).request(
        snapshot,
        context=_context(),
        created_at=NOW,
    )
    bus = EventBus()
    publisher = EventBusPublisher(bus)
    events: list[Event] = []
    bus.subscribe(
        EventSubscription(
            subscriber_id="p3-1a-recovery-idempotency-audit",
            handler=events.append,
            priority=200,
        )
    )
    boundary = RecoveryExecutionBoundary(
        healer,
        publisher,
        replay_stage_store=store,
    )
    result = boundary.request(
        strategy,
        snapshot,
        context=_context(),
        created_at=NOW,
        **_p2_2_replay_arguments(generation=1),
    )

    expected_key = store.begin_calls[0][0]
    assert result.success is True
    assert healer.action_idempotency_key == expected_key
    recovery_events = [
        event
        for event in events
        if event.name in {"RecoveryExecutionRequested", "RecoveryExecutionCompleted"}
    ]
    assert [event.name for event in recovery_events] == [
        "RecoveryExecutionRequested",
        "RecoveryExecutionCompleted",
    ]
    assert all(
        event.payload["idempotency_key"] == expected_key
        for event in recovery_events
    )


def test_persistent_recovery_execution_replays_after_restart_without_backend_call() -> None:
    store = _p2_2_fake_replay_stage_store()
    first_healer = _PersistentReplayCountingHealer()
    _, _, first_strategy, first_snapshot = _strategy_result(first_healer)
    first_boundary = RecoveryExecutionBoundary(
        first_healer,
        replay_stage_store=store,
    )
    first = first_boundary.request(
        first_strategy,
        first_snapshot,
        context=_context(),
        created_at=NOW,
        **_p2_2_replay_arguments(generation=1, owner="owner-1"),
    )

    second_healer = _PersistentReplayCountingHealer()
    _, _, second_strategy, second_snapshot = _strategy_result(second_healer)
    second_boundary = RecoveryExecutionBoundary(
        second_healer,
        replay_stage_store=store,
    )
    second = second_boundary.request(
        second_strategy,
        second_snapshot,
        context=_context(),
        created_at=NOW,
        **_p2_2_replay_arguments(generation=2, owner="owner-2"),
    )

    assert first.success is True
    assert second.success is True
    assert first_healer.execution_calls == 1
    assert first_healer.idempotency_keys == [store.begin_calls[0][0]]
    assert second_healer.execution_calls == 0
    assert second_healer.idempotency_keys == []
    assert second.result == first.result
    assert len(store.complete_calls) == 1
    assert store.begin_calls[0][1:] == ("owner-1", 1)
    assert store.begin_calls[1][1:] == ("owner-2", 2)


def test_rebuild_propagates_idempotency_key_to_key_aware_context_manager() -> None:
    class KeyAwareContextManager(ContextManager):
        def __init__(self) -> None:
            super().__init__()
            self.received_keys: list[str | None] = []

        def clear(self, *, idempotency_key: str | None = None) -> None:
            self.received_keys.append(idempotency_key)
            super().clear(idempotency_key=idempotency_key)

    manager = KeyAwareContextManager()
    manager.push("root")
    healer = SelfHealingCore(context_manager=manager)
    key = "recovery-context-clear:stable"

    result = healer.recover_with_strategy(
        _snapshot("rebuild with idempotency"),
        "rebuild_context",
        idempotency_key=key,
    )

    assert manager.received_keys == [key]
    assert manager.snapshot()["depth"] == 0
    assert result["idempotency_key"] == key


def test_rebuild_preserves_legacy_context_manager_clear_signature() -> None:
    class LegacyContextManager:
        def __init__(self) -> None:
            self.clear_calls = 0

        def clear(self) -> None:
            self.clear_calls += 1

    manager = LegacyContextManager()
    healer = SelfHealingCore(context_manager=manager)

    result = healer.recover_with_strategy(
        _snapshot("legacy clear signature"),
        "rebuild_context",
        idempotency_key="recovery-context-clear:legacy",
    )

    assert manager.clear_calls == 1
    assert result["context_rebuilt"] is True


def test_persistent_recovery_execution_caches_failure_result_across_restart() -> None:
    store = _p2_2_fake_replay_stage_store()
    first_healer = _PersistentReplayCountingHealer(fail=True)
    _, _, first_strategy, first_snapshot = _strategy_result(first_healer)
    first = RecoveryExecutionBoundary(
        first_healer,
        replay_stage_store=store,
    ).request(
        first_strategy,
        first_snapshot,
        context=_context(),
        created_at=NOW,
        **_p2_2_replay_arguments(generation=1),
    )

    second_healer = _PersistentReplayCountingHealer(fail=True)
    _, _, second_strategy, second_snapshot = _strategy_result(second_healer)
    second = RecoveryExecutionBoundary(
        second_healer,
        replay_stage_store=store,
    ).request(
        second_strategy,
        second_snapshot,
        context=_context(),
        created_at=NOW,
        **_p2_2_replay_arguments(generation=2, owner="owner-2"),
    )

    assert first.success is False
    assert second.success is False
    assert first.error == "persistent recovery failure"
    assert second.error == first.error
    assert first_healer.execution_calls == 1
    assert second_healer.execution_calls == 0


def test_persistent_recovery_execution_uses_a_new_stage_for_different_input() -> None:
    store = _p2_2_fake_replay_stage_store()
    healer = _PersistentReplayCountingHealer()
    boundary = RecoveryExecutionBoundary(healer, replay_stage_store=store)

    _, _, first_strategy, first_snapshot = _strategy_result(healer)
    first = boundary.request(
        first_strategy,
        first_snapshot,
        context=_context(),
        created_at=NOW,
        **_p2_2_replay_arguments(generation=1, result_id="result-1"),
    )

    second_context = EventPropagationContext.create(
        correlation_id="execution-correlation-2",
        trace_id="execution-trace-2",
        tenant_id="execution-tenant",
    )
    second_snapshot = _snapshot("different recovery input")
    second_strategy_boundary = RecoveryStrategyBoundary(healer)
    second_strategy = second_strategy_boundary.request(
        second_snapshot,
        context=second_context,
        created_at=NOW,
    )
    second = boundary.request(
        second_strategy,
        second_snapshot,
        context=second_context,
        created_at=NOW,
        **_p2_2_replay_arguments(generation=1, result_id="result-2"),
    )

    assert first.success is True
    assert second.success is True
    assert healer.execution_calls == 2
    assert len(store.complete_calls) == 2


def test_persistent_recovery_execution_rejects_partial_replay_metadata() -> None:
    store = _p2_2_fake_replay_stage_store()
    healer = _PersistentReplayCountingHealer()
    _, _, strategy, snapshot = _strategy_result(healer)
    boundary = RecoveryExecutionBoundary(healer, replay_stage_store=store)

    try:
        boundary.request(
            strategy,
            snapshot,
            context=_context(),
            created_at=NOW,
            replay_cycle_id="cycle-only",
        )
    except ValueError as exc:
        assert "completely" in str(exc)
    else:
        raise AssertionError("partial replay metadata must be rejected")

    assert healer.execution_calls == 0
    assert store.begin_calls == []


def test_recovery_execution_without_replay_metadata_keeps_legacy_behavior() -> None:
    store = _p2_2_fake_replay_stage_store()
    healer = _PersistentReplayCountingHealer()
    _, _, strategy, snapshot = _strategy_result(healer)
    result = RecoveryExecutionBoundary(
        healer,
        replay_stage_store=store,
    ).request(
        strategy,
        snapshot,
        context=_context(),
        created_at=NOW,
    )

    assert result.success is True
    assert healer.execution_calls == 1
    assert store.begin_calls == []
    assert store.complete_calls == []
