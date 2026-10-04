from __future__ import annotations

from foundation.Enums.priority import Priority
from runtime.execution import ExecutionRequest
from runtime.scheduler import RuntimeExecutionScheduler


def _request(
    execution_id: str,
    *,
    priority: Priority = Priority.NORMAL,
) -> ExecutionRequest:
    return ExecutionRequest.create(
        execution_id=execution_id,
        operation="runtime.execute",
        priority=priority,
        correlation_id=f"corr-{execution_id}",
    )


def test_enqueue_assigns_monotonic_sequence() -> None:
    scheduler = RuntimeExecutionScheduler()

    first = scheduler.enqueue(_request("exec-1"))
    second = scheduler.enqueue(_request("exec-2"))

    assert first.sequence == 0
    assert second.sequence == 1


def test_peek_does_not_remove_item() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("exec-1"))

    item = scheduler.peek()

    assert item is not None
    assert item.execution_id == "exec-1"
    assert scheduler.size == 1


def test_dequeue_removes_highest_priority_first() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("low", priority=Priority.LOW))
    scheduler.enqueue(_request("critical", priority=Priority.CRITICAL))
    scheduler.enqueue(_request("normal", priority=Priority.NORMAL))
    scheduler.enqueue(_request("high", priority=Priority.HIGH))

    result = tuple(item.execution_id for item in scheduler.clear())

    assert result == ("critical", "high", "normal", "low")


def test_same_priority_preserves_creation_sequence() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("exec-3"))
    scheduler.enqueue(_request("exec-1"))
    scheduler.enqueue(_request("exec-2"))

    result = tuple(item.execution_id for item in scheduler.clear())

    assert result == ("exec-3", "exec-1", "exec-2")

'''
def test_execution_id_is_final_deterministic_tiebreaker() -> None:
    scheduler = RuntimeExecutionScheduler()
    first = scheduler.enqueue(_request("exec-b"))
    second = ScheduledExecution(request=_request("exec-a"), sequence=first.sequence)

    assert scheduler._sort_key(first) > scheduler._sort_key(second)
'''

def test_get_and_contains() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("exec-1"))

    assert scheduler.contains("exec-1")
    assert scheduler.get("exec-1") is not None
    assert scheduler.get("missing") is None


def test_remove_returns_removed_item() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("exec-1"))

    removed = scheduler.remove("exec-1")

    assert removed is not None
    assert removed.execution_id == "exec-1"
    assert scheduler.empty


def test_duplicate_execution_id_is_rejected() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("exec-1"))

    try:
        scheduler.enqueue(_request("exec-1"))
    except ValueError as exc:
        assert "execution already scheduled" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_empty_scheduler_returns_none() -> None:
    scheduler = RuntimeExecutionScheduler()

    assert scheduler.peek() is None
    assert scheduler.dequeue() is None
    assert scheduler.empty
    assert scheduler.size == 0


def test_pending_is_sorted_without_mutation() -> None:
    scheduler = RuntimeExecutionScheduler()
    scheduler.enqueue(_request("low", priority=Priority.LOW))
    scheduler.enqueue(_request("high", priority=Priority.HIGH))
    scheduler.enqueue(_request("normal", priority=Priority.NORMAL))

    pending = scheduler.pending()

    assert tuple(item.execution_id for item in pending) == (
        "high",
        "normal",
        "low",
    )
    assert scheduler.size == 3
