from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock

from runtime.execution import ExecutionSnapshot, ExecutionState

__all__ = ["ExecutionStateMachineError", "RuntimeExecutionStateMachine"]


class ExecutionStateMachineError(RuntimeError):
    pass


_TRANSITIONS: dict[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.CREATED: frozenset({ExecutionState.QUEUED, ExecutionState.CANCELLED}),
    ExecutionState.QUEUED: frozenset({ExecutionState.RUNNING, ExecutionState.CANCELLED}),
    ExecutionState.RUNNING: frozenset(
        {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCEL_REQUESTED,
            ExecutionState.TIMED_OUT,
        }
    ),
    ExecutionState.CANCEL_REQUESTED: frozenset({ExecutionState.CANCELLED}),
    ExecutionState.COMPLETED: frozenset(),
    ExecutionState.FAILED: frozenset(),
    ExecutionState.CANCELLED: frozenset(),
    ExecutionState.TIMED_OUT: frozenset(),
}


class RuntimeExecutionStateMachine:
    __slots__ = ("_lock", "_snapshots")

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshots: dict[str, ExecutionSnapshot] = {}

    def register(self, snapshot: ExecutionSnapshot) -> ExecutionSnapshot:
        if not isinstance(snapshot, ExecutionSnapshot):
            raise TypeError("snapshot must be ExecutionSnapshot")
        with self._lock:
            existing = self._snapshots.get(snapshot.execution_id)
            if existing is not None:
                if existing != snapshot:
                    raise ExecutionStateMachineError(
                        f"execution already registered: {snapshot.execution_id}"
                    )
                return existing
            self._snapshots[snapshot.execution_id] = snapshot
            return snapshot

    def get(self, execution_id: str) -> ExecutionSnapshot | None:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return self._snapshots.get(execution_id)

    def transition(
        self,
        execution_id: str,
        target: ExecutionState,
        *,
        now: datetime | None = None,
        result: object = None,
        error_type: str | None = None,
        error_message: str | None = None,
        attempt: int | None = None,
    ) -> ExecutionSnapshot:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        if not isinstance(target, ExecutionState):
            raise TypeError("target must be ExecutionState")
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        with self._lock:
            current = self._snapshots.get(execution_id)
            if current is None:
                raise ExecutionStateMachineError(
                    f"execution not registered: {execution_id}"
                )
            if target not in _TRANSITIONS[current.state]:
                raise ExecutionStateMachineError(
                    f"invalid execution transition: {current.state} -> {target}"
                )
            updated = self._build_snapshot(
                current,
                target,
                timestamp,
                result=result,
                error_type=error_type,
                error_message=error_message,
            )
            self._snapshots[execution_id] = updated
            return updated

    def can_transition(
        self,
        execution_id: str,
        target: ExecutionState,
    ) -> bool:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        if not isinstance(target, ExecutionState):
            raise TypeError("target must be ExecutionState")
        with self._lock:
            current = self._snapshots.get(execution_id)
            return current is not None and target in _TRANSITIONS[current.state]

    def current_state(self, execution_id: str) -> ExecutionState:
        snapshot = self.get(execution_id)
        if snapshot is None:
            raise ExecutionStateMachineError(
                f"execution not registered: {execution_id}"
            )
        return snapshot.state

    def snapshots(self) -> tuple[ExecutionSnapshot, ...]:
        with self._lock:
            return tuple(self._snapshots.values())

    def remove(self, execution_id: str) -> ExecutionSnapshot | None:
        if not execution_id:
            raise ValueError("execution_id must not be empty")
        with self._lock:
            return self._snapshots.pop(execution_id, None)


    @staticmethod
    def _build_snapshot(
        current: ExecutionSnapshot,
        target: ExecutionState,
        timestamp: datetime,
        *,
        result: object,
        error_type: str | None,
        error_message: str | None,
    ) -> ExecutionSnapshot:
        snapshot=current
        if target is ExecutionState.QUEUED:
            return replace(current, state=target, queued_at=timestamp)
        if target is ExecutionState.RUNNING:
            return replace(
                current,
                state=target,
                started_at=timestamp,
                attempt=current.attempt + 1,
                error_type=error_type if error_type is not None else snapshot.error_type,
                error_message=error_message if error_message is not None else snapshot.error_message,
            )
        if target is ExecutionState.COMPLETED:
            return replace(
                snapshot,
                state=target,
                completed_at=timestamp,
                result=result,
                error_type=error_type if error_type is not None else snapshot.error_type,
                error_message=error_message if error_message is not None else snapshot.error_message,
            )
        if target is ExecutionState.FAILED:
            return replace(
                snapshot,
                state=target,
                completed_at=timestamp,
                result=result,
                error_type=error_type if error_type is not None else snapshot.error_type,
                error_message=error_message if error_message is not None else snapshot.error_message,
            )
        if target is ExecutionState.CANCEL_REQUESTED:
            return replace(
                current,
                state=target,
                result=current.result,
                error_type=None,
                error_message=None,
            )
        if target is ExecutionState.CANCELLED:
            return replace(
                current,
                state=target,
                completed_at=timestamp,
                result=current.result,
                error_type=error_type if error_type is not None else snapshot.error_type,
                error_message=error_message if error_message is not None else snapshot.error_message,
            )
        if target is ExecutionState.TIMED_OUT:
            return replace(
                snapshot,
                state=target,
                completed_at=timestamp,
                result=result,
                error_type=error_type if error_type is not None else snapshot.error_type,
                error_message=error_message if error_message is not None else snapshot.error_message,
            )
        raise ExecutionStateMachineError(f"unsupported execution state: {target}")
