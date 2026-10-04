from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4

from foundation.Enums.event import EventType
from infrastructure.event_bus import EventPublisher
from infrastructure.events import EventPropagationContext
from infrastructure.security import EvidenceRecord, EvidenceStore
from runtime.execution_context import ExecutionContext

from .events import publish_runtime_event
from .execution import ExecutionRequest, ExecutionSnapshot, ExecutionState
from .execution_cleanup import CleanupAction, CleanupResult, RuntimeExecutionCleanupManager
from .observability import RuntimeExecutionObservability
from .state_machine import RuntimeExecutionStateMachine

__all__ = [
    "ExecutionHandle",
    "ExecutionOperation",
    "ExecutionOutcome",
    "RuntimeExecutionEngine",
]

ExecutionOperation = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    execution_id: str
    success: bool
    state: ExecutionState
    result: Any = None
    error: BaseException | None = None
    snapshot: ExecutionSnapshot | None = None
    cleanup: CleanupResult | None = None

    @property
    def failed(self) -> bool:
        return not self.success


@dataclass(frozen=True, slots=True)
class ExecutionHandle:
    execution_id: str
    _engine: RuntimeExecutionEngine

    def snapshot(self) -> ExecutionSnapshot:
        return self._engine.snapshot(self.execution_id)

    def outcome(self) -> ExecutionOutcome | None:
        return self._engine.outcome(self.execution_id)

    @property
    def state(self) -> ExecutionState:
        return self.snapshot().state


class RuntimeExecutionEngine:
    __slots__ = (
        "_cleanup_manager",
        "_event_publisher",
        "_lock",
        "_observability",
        "_operations",
        "_outcomes",
        "_state_machine",
    )

    def __init__(
        self,
        state_machine: RuntimeExecutionStateMachine | None = None,
        cleanup_manager: RuntimeExecutionCleanupManager | None = None,
        event_publisher: EventPublisher | None = None,
        evidence_store: EvidenceStore | None = None,
        observability: RuntimeExecutionObservability | None = None,
    ) -> None:
        self._lock = RLock()
        self._operations: dict[str, ExecutionOperation] = {}
        self._outcomes: dict[str, ExecutionOutcome] = {}
        self._state_machine = state_machine or RuntimeExecutionStateMachine()
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
    def operations(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._operations))

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

    def create_request(
        self,
        operation: str,
        payload: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ExecutionRequest:
        return ExecutionRequest.create(
            execution_id=uuid4().hex,
            operation=operation,
            payload=payload,
            **kwargs,
        )

    def register_operation(
        self,
        name: str,
        operation: ExecutionOperation,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("name must not be empty")
        if not callable(operation):
            raise TypeError("operation must be callable")
        with self._lock:
            if name in self._operations and not replace:
                raise ValueError(f"operation already registered: {name}")
            self._operations[name] = operation

    def unregister_operation(self, name: str) -> bool:
        if not isinstance(name, str) or not name:
            raise ValueError("name must not be empty")
        with self._lock:
            return self._operations.pop(name, None) is not None

    def get_operation(self, name: str) -> ExecutionOperation | None:
        if not isinstance(name, str) or not name:
            raise ValueError("name must not be empty")
        with self._lock:
            return self._operations.get(name)

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

    def submit(
        self,
        request: ExecutionRequest,
        operation: ExecutionOperation | None = None,
    ) -> ExecutionHandle:
        self.execute(request, operation)
        return ExecutionHandle(request.execution_id, self)

    def execute(
        self,
        request: ExecutionRequest,
        operation: ExecutionOperation | None = None,
        cleanup: CleanupResult | None = None,
    ) -> ExecutionOutcome:
        if not isinstance(request, ExecutionRequest):
            raise TypeError("request must be ExecutionRequest")

        snapshot = ExecutionSnapshot.create(request, now=datetime.now(UTC))
        self._state_machine.register(snapshot)
        context = EventPropagationContext.create(
            correlation_id=request.correlation_id or request.execution_id,
            causation_id=request.causation_id,
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
        )
        submitted_event_id = publish_runtime_event(
            self._event_publisher,
            event_name="RuntimeExecutionSubmitted",
            producer="runtime.execution_engine",
            payload={
                "execution_id": request.execution_id,
                "operation": request.operation,
                "priority": request.priority,
            },
            event_type=EventType.CREATED,
            context=context,
        )
        self._state_machine.transition(request.execution_id, ExecutionState.QUEUED)
        self._state_machine.transition(request.execution_id, ExecutionState.RUNNING)

        started_context = (
            context.next(submitted_event_id)
            if submitted_event_id is not None
            else context
        )

        started_event_id = publish_runtime_event(
            self._event_publisher,
            event_name="RuntimeExecutionStarted",
            producer="runtime.execution_engine",
            payload={
                "execution_id": request.execution_id,
                "operation": request.operation,
                "attempt": snapshot.attempt,
            },
            event_type=EventType.START,
            context=started_context,
        )

        target = operation or self.get_operation(request.operation)
        if target is None:
            return self._fail(
                request,
                LookupError(
                    f"execution operation is not registered: {request.operation}"
                ),
                context=started_context,
                causation_id=started_event_id,
            )

        try:
            result = target(request.payload)
        except Exception as exc:
            return self._fail(
                request,
                exc,
                context=started_context,
                causation_id=started_event_id,
            )

        self._state_machine.transition(
            request.execution_id,
            ExecutionState.COMPLETED,
        )
        completed = self._state_machine.get(request.execution_id)
        if completed is None:
            raise RuntimeError(
                f"execution snapshot not found: {request.execution_id}"
            )
        completed_context = (
            started_context.next(started_event_id)
            if started_event_id is not None
            else started_context
        )

        completed_event_id = publish_runtime_event(
            self._event_publisher,
            event_name="RuntimeExecutionCompleted",
            producer="runtime.execution_engine",
            payload={
                "execution_id": request.execution_id,
                "operation": request.operation,
                "attempt": completed.attempt if completed else snapshot.attempt,
                "result": result,
            },
            event_type=EventType.COMPLETE,
            context=completed_context,
        )

        cleanup = self._cleanup_manager.cleanup(request.execution_id)
        evidence_snapshot = self._state_machine.get(request.execution_id)
        if evidence_snapshot is None:
            raise RuntimeError(
                f"execution snapshot not found: {request.execution_id}"
            )
        self._observability.record(
            evidence_snapshot,
            result=result,
            cleanup=cleanup,
        )
        outcome = ExecutionOutcome(
            execution_id=request.execution_id,
            success=True,
            state=ExecutionState.COMPLETED,
            result=result,
            snapshot=completed,
            cleanup=cleanup,
        )
        if cleanup.failed:
            cleanup_context = (
                completed_context.next(completed_event_id)
                if completed_event_id is not None
                else completed_context
            )

            publish_runtime_event(
                self._event_publisher,
                event_name="CleanupFailed",
                producer="runtime.execution_engine",
                payload={
                    "execution_id": request.execution_id,
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
        with self._lock:
            self._outcomes[request.execution_id] = outcome
        return outcome

    def snapshot(self, execution_id: str) -> ExecutionSnapshot:
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("execution_id must not be empty")
        snapshot = self._state_machine.get(execution_id)
        if snapshot is None:
            raise KeyError(f"execution not found: {execution_id}")
        return snapshot

    def outcome(self, execution_id: str) -> ExecutionOutcome | None:
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return self._outcomes.get(execution_id)

    def executions(self) -> tuple[ExecutionSnapshot, ...]:
        return self._state_machine.snapshots()

    def _fail(
        self,
        request: ExecutionRequest,
        error: BaseException,
        *,
        context: EventPropagationContext | None = None,
        causation_id: str | None = None,
    ) -> ExecutionOutcome:
        self._state_machine.transition(
            request.execution_id,
            ExecutionState.FAILED,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        failure_context = (
            context.next(causation_id)
            if context is not None and causation_id is not None
            else context
            or EventPropagationContext.create(
                correlation_id=request.correlation_id or request.execution_id,
                causation_id=causation_id,
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
            )
        )

        failed_event_id = publish_runtime_event(
            self._event_publisher,
            event_name="RuntimeExecutionFailed",
            producer="runtime.execution_engine",
            payload={
                "execution_id": request.execution_id,
                "operation": request.operation,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            event_type=EventType.FAILURE,
            context=failure_context,
        )
        cleanup = self._cleanup_manager.cleanup(request.execution_id)
        evidence_snapshot = self._state_machine.get(request.execution_id)
        if evidence_snapshot is None:
            raise RuntimeError(
                f"execution snapshot not found: {request.execution_id}"
            )
        self._observability.record(
            evidence_snapshot,
            error=error,
            cleanup=cleanup,
        )
        if cleanup.failed:
            cleanup_context = (
                failure_context.next(failed_event_id)
                if failed_event_id is not None
                else failure_context
            )
            publish_runtime_event(
                self._event_publisher,
                event_name="CleanupFailed",
                producer="runtime.execution_engine",
                payload={
                    "execution_id": request.execution_id,
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
        outcome = ExecutionOutcome(
            execution_id=request.execution_id,
            success=False,
            state=ExecutionState.FAILED,
            error=error,
            snapshot=evidence_snapshot,
            cleanup=cleanup,
        )
        self._observability.record(
            self._snapshot_for_observability(request.execution_id),
            error=error,
            cleanup=cleanup,
        )
        with self._lock:
            self._outcomes[request.execution_id] = outcome
        return outcome

    def context(self, execution_id: str) -> ExecutionContext:
        snapshot = self.snapshot(execution_id)
        return snapshot.context

    def _snapshot_for_observability(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = self._state_machine.get(execution_id)
        if snapshot is None:
            raise RuntimeError(f"execution snapshot not found: {execution_id}")
        return snapshot
