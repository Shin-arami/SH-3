from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock

from foundation.Enums.event import EventType
from infrastructure.event_bus.publisher import EventPublisher
from infrastructure.events import EventPropagationContext
from infrastructure.security import EvidenceRecord, EvidenceStore

from .events import publish_runtime_event
from .execution import ExecutionSnapshot, ExecutionState
from .execution_cleanup import CleanupAction, CleanupResult, RuntimeExecutionCleanupManager
from .observability import RuntimeExecutionObservability
from .state_machine import RuntimeExecutionStateMachine

__all__ = [
    "ExecutionCancellationResult",
    "ExecutionTimeoutResult",
    "RuntimeExecutionController",
]


@dataclass(frozen=True, slots=True)
class ExecutionCancellationResult:
    execution_id: str
    state: ExecutionState
    requested: bool
    cleanup: CleanupResult | None = None


@dataclass(frozen=True, slots=True)
class ExecutionTimeoutResult:
    execution_id: str
    state: ExecutionState
    timed_out: bool
    cleanup: CleanupResult | None = None


class RuntimeExecutionController:
    __slots__ = (
        "_cleanup_manager",
        "_event_publisher",
        "_lock",
        "_observability",
        "_state_machine",
    )

    def __init__(
        self,
        state_machine: RuntimeExecutionStateMachine,
        cleanup_manager: RuntimeExecutionCleanupManager | None = None,
        event_publisher: EventPublisher | None = None,
        evidence_store: EvidenceStore | None = None,
        observability: RuntimeExecutionObservability | None = None,
    ) -> None:
        if not isinstance(state_machine, RuntimeExecutionStateMachine):
            raise TypeError("state_machine must be RuntimeExecutionStateMachine")
        self._lock = RLock()
        self._state_machine = state_machine
        self._cleanup_manager = cleanup_manager or RuntimeExecutionCleanupManager()
        self._event_publisher = event_publisher
        self._observability = RuntimeExecutionObservability(evidence_store)

    @property
    def state_machine(self) -> RuntimeExecutionStateMachine:
        return self._state_machine

    @property
    def cleanup_manager(self) -> RuntimeExecutionCleanupManager:
        return self._cleanup_manager

    @property
    def event_publisher(self) -> EventPublisher | None:
        return self._event_publisher

    @property
    def observability(self) -> RuntimeExecutionObservability:
        return self._observability

    @property
    def evidence_store(self) -> EvidenceStore:
        return self._observability.evidence_store

    def evidence(self, execution_id: str) -> EvidenceRecord | None:
        return self._observability.get(execution_id)

    def verify_evidence(self, execution_id: str) -> bool:
        return self._observability.verify(execution_id)

    def register_cleanup(
        self,
        execution_id: str,
        action: CleanupAction,
        *,
        name: str = "cleanup",
    ) -> None:
        self._cleanup_manager.register(execution_id, action, name=name)

    def cleanup(self, execution_id: str) -> CleanupResult:
        return self._cleanup_manager.cleanup(execution_id)

    def cancel(
        self,
        execution_id: str,
        *,
        now: datetime | None = None,
    ) -> ExecutionCancellationResult:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        timestamp = now or datetime.now(UTC)
        with self._lock:
            snapshot = self._require_snapshot(execution_id)
            state = snapshot.state
            if state is ExecutionState.RUNNING:
                updated = self._state_machine.transition(
                    execution_id,
                    ExecutionState.CANCEL_REQUESTED,
                    now=timestamp,
                )
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=updated.state,
                    requested=True,
                )
            if state is ExecutionState.CANCEL_REQUESTED:
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=state,
                    requested=True,
                )
            if state is ExecutionState.CANCELLED:
                cleanup = self._cleanup_manager.cleanup(execution_id)
                evidence_snapshot = self._state_machine.get(execution_id)
                if evidence_snapshot is None:
                    raise RuntimeError(
                        f"execution snapshot not found: {execution_id}"
                    )
                self._observability.record(
                    evidence_snapshot,
                    cleanup=cleanup,
                )
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=state,
                    requested=True,
                    cleanup=cleanup,
                )
            if state in (
                ExecutionState.COMPLETED,
                ExecutionState.FAILED,
                ExecutionState.TIMED_OUT,
            ):
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=state,
                    requested=False,
                )
            if state in (ExecutionState.CREATED, ExecutionState.QUEUED):
                updated = self._state_machine.transition(
                    execution_id,
                    ExecutionState.CANCELLED,
                    now=timestamp,
                )
                context = self._event_context(snapshot, execution_id)
                event_id = publish_runtime_event(
                    self._event_publisher,
                    event_name="RuntimeExecutionCancelled",
                    producer="runtime.execution_controller",
                    payload={
                        "execution_id": execution_id,
                        "state": ExecutionState.CANCELLED.value,
                    },
                    event_type=EventType.CANCEL,
                    context=context,
                )
                cleanup = self._cleanup_manager.cleanup(execution_id)
                evidence_snapshot = self._state_machine.get(execution_id)
                if evidence_snapshot is None:
                    raise RuntimeError(
                        f"execution snapshot not found: {execution_id}"
                    )
                self._observability.record(
                    evidence_snapshot,
                    cleanup=cleanup,
                )
                self._observability.record(
                    updated,
                    cleanup=cleanup,
                )
                self._publish_cleanup_failed(
                    execution_id,
                    cleanup,
                    context,
                    event_id,
                )
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=updated.state,
                    requested=True,
                    cleanup=cleanup,
                )
            raise RuntimeError(f"unsupported execution state: {state!r}")

    def complete_cancellation(
        self,
        execution_id: str,
        *,
        now: datetime | None = None,
    ) -> ExecutionCancellationResult:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        timestamp = now or datetime.now(UTC)
        with self._lock:
            snapshot = self._require_snapshot(execution_id)
            if snapshot.state is ExecutionState.CANCELLED:
                cleanup = self._cleanup_manager.cleanup(execution_id)
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    requested=True,
                    cleanup=cleanup,
                )
            if snapshot.state is not ExecutionState.CANCEL_REQUESTED:
                return ExecutionCancellationResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    requested=False,
                )
            updated = self._state_machine.transition(
                execution_id,
                ExecutionState.CANCELLED,
                now=timestamp,
            )
            context = self._event_context(snapshot, execution_id)
            event_id = publish_runtime_event(
                self._event_publisher,
                event_name="RuntimeExecutionCancelled",
                producer="runtime.execution_controller",
                payload={
                    "execution_id": execution_id,
                    "state": ExecutionState.CANCELLED.value,
                },
                event_type=EventType.CANCEL,
                context=context,
            )
            cleanup = self._cleanup_manager.cleanup(execution_id)
            evidence_snapshot = self._state_machine.get(execution_id)
            if evidence_snapshot is None:
                raise RuntimeError(
                    f"execution snapshot not found: {execution_id}"
                )
            self._observability.record(
                evidence_snapshot,
                cleanup=cleanup,
            )
            self._observability.record(
                updated,
                cleanup=cleanup,
            )
            self._publish_cleanup_failed(
                execution_id,
                cleanup,
                context,
                event_id,
            )
            return ExecutionCancellationResult(
                execution_id=execution_id,
                state=updated.state,
                requested=True,
                cleanup=cleanup,
            )

    def timeout(
        self,
        execution_id: str,
        *,
        now: datetime | None = None,
    ) -> ExecutionTimeoutResult:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        timestamp = now or datetime.now(UTC)
        with self._lock:
            snapshot = self._require_snapshot(execution_id)
            if snapshot.state is ExecutionState.TIMED_OUT:
                cleanup = self._cleanup_manager.cleanup(execution_id)
                return ExecutionTimeoutResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    timed_out=True,
                    cleanup=cleanup,
                )
            if snapshot.state.terminal:
                return ExecutionTimeoutResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    timed_out=False,
                )
            if snapshot.timeout is None:
                return ExecutionTimeoutResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    timed_out=False,
                )
            if snapshot.started_at is None:
                return ExecutionTimeoutResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    timed_out=False,
                )
            elapsed = timestamp - snapshot.started_at
            if elapsed.total_seconds() < snapshot.timeout:
                return ExecutionTimeoutResult(
                    execution_id=execution_id,
                    state=snapshot.state,
                    timed_out=False,
                )
            updated = self._state_machine.transition(
                execution_id,
                ExecutionState.TIMED_OUT,
                error_type="TimeoutError",
                error_message="execution timed out",
            )
            context = self._event_context(snapshot, execution_id)
            event_id = publish_runtime_event(
                self._event_publisher,
                event_name="RuntimeExecutionTimedOut",
                producer="runtime.execution_controller",
                payload={
                    "execution_id": execution_id,
                    "timeout": snapshot.timeout,
                },
                event_type=EventType.TIMEOUT,
                context=context,
            )
            cleanup = self._cleanup_manager.cleanup(execution_id)
            evidence_snapshot = self._state_machine.get(execution_id)
            if evidence_snapshot is None:
                raise RuntimeError(
                    f"execution snapshot not found: {execution_id}"
                )
            self._observability.record(
                evidence_snapshot,
                cleanup=cleanup,
            )
            self._observability.record(
                updated,
                cleanup=cleanup,
            )
            self._publish_cleanup_failed(
                execution_id,
                cleanup,
                context,
                event_id,
            )
            return ExecutionTimeoutResult(
                execution_id=execution_id,
                state=updated.state,
                timed_out=True,
                cleanup=cleanup,
            )

    def check_timeout(
        self,
        execution_id: str,
        *,
        now: datetime | None = None,
    ) -> ExecutionTimeoutResult:
        return self.timeout(execution_id, now=now)

    def snapshot(self, execution_id: str) -> ExecutionSnapshot | None:
        return self._state_machine.get(execution_id)

    def _event_context(
        self,
        snapshot: ExecutionSnapshot,
        execution_id: str,
    ) -> EventPropagationContext:
        return EventPropagationContext.create(
            correlation_id=snapshot.correlation_id or execution_id,
            causation_id=snapshot.causation_id,
            trace_id=snapshot.trace_id,
            tenant_id=snapshot.tenant_id,
        )

    def _publish_cleanup_failed(
        self,
        execution_id: str,
        cleanup: CleanupResult,
        context: EventPropagationContext,
        causation_id: str | None,
    ) -> None:
        if not cleanup.attempted or not cleanup.failed:
            return
        cleanup_context = (
            context.next(causation_id)
            if causation_id is not None
            else context
        )
        publish_runtime_event(
            self._event_publisher,
            event_name="CleanupFailed",
            producer="runtime.execution_controller",
            payload={
                "execution_id": execution_id,
                "failures": [
                    {
                        "name": failure.name,
                        "error_type": failure.error_type,
                        "error_message": failure.error_message,
                    }
                    for failure in cleanup.failures
                ],
            },
            event_type=EventType.FAILURE,
            context=cleanup_context,
        )

    def _require_snapshot(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = self._state_machine.get(execution_id)
        if snapshot is None:
            raise KeyError(f"execution not found: {execution_id}")
        return snapshot

    def _snapshot_for_observability(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = self._state_machine.get(execution_id)
        if snapshot is None:
            raise RuntimeError(f"execution snapshot not found: {execution_id}")
        return snapshot
