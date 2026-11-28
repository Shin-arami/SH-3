from __future__ import annotations

from datetime import UTC, datetime

from infrastructure.security.evidence import EvidenceStore
from runtime.execution import ExecutionRequest, ExecutionSnapshot, ExecutionState
from runtime.execution_cleanup import RuntimeExecutionCleanupManager
from runtime.execution_controller import RuntimeExecutionController
from runtime.execution_engine import RuntimeExecutionEngine
from runtime.observability import RuntimeExecutionObservability
from runtime.state_machine import RuntimeExecutionStateMachine


def test_completed_execution_records_evidence() -> None:
    store = EvidenceStore()
    engine = RuntimeExecutionEngine(evidence_store=store)
    request = engine.create_request("runtime.test", {"value": 1})

    outcome = engine.execute(request, lambda payload: {"value": payload["value"] + 1})

    assert outcome.success
    assert outcome.snapshot is not None
    evidence = engine.evidence(request.execution_id)

    assert evidence is not None
    assert evidence.kind == "runtime.execution"
    assert evidence.source == "runtime"
    assert evidence.subject_id == request.execution_id
    assert evidence.trace_id == request.trace_id
    assert evidence.payload["state"] == ExecutionState.COMPLETED.value
    assert evidence.payload["result"] == {"value": 2}
    assert evidence.verify()
    assert store.verify(evidence.evidence_id)


def test_failed_execution_records_error_evidence() -> None:
    engine = RuntimeExecutionEngine()
    request = engine.create_request("runtime.test")

    def fail(_: object) -> None:
        raise ValueError("boom")

    outcome = engine.execute(request, fail)

    assert not outcome.success
    evidence = engine.evidence(request.execution_id)

    assert evidence is not None
    assert evidence.payload["state"] == ExecutionState.FAILED.value
    assert evidence.payload["error_type"] == "ValueError"
    assert evidence.payload["error_message"] == "boom"
    assert evidence.verify()


def test_cancelled_execution_records_evidence() -> None:
    state_machine = RuntimeExecutionStateMachine()
    cleanup_manager = RuntimeExecutionCleanupManager()
    controller = RuntimeExecutionController(
        state_machine,
        cleanup_manager=cleanup_manager,
    )
    request = ExecutionRequest.create(
        execution_id="cancel-evidence",
        operation="runtime.test",
    )
    snapshot = ExecutionSnapshot.create(
        request,
        now=datetime.now(UTC),
    )
    state_machine.register(snapshot)

    assert snapshot.state is ExecutionState.CREATED

    result = controller.cancel(request.execution_id)

    assert result.state is ExecutionState.CANCELLED
    evidence = controller.evidence(request.execution_id)

    assert evidence is not None
    assert evidence.payload["state"] == ExecutionState.CANCELLED.value
    assert evidence.verify()


def test_timed_out_execution_records_evidence() -> None:
    state_machine = RuntimeExecutionStateMachine()
    controller = RuntimeExecutionController(state_machine)
    request = ExecutionRequest.create(
        execution_id="timeout-evidence",
        operation="runtime.test",
        timeout=1.0,
    )
    from runtime.execution import ExecutionSnapshot

    snapshot = ExecutionSnapshot.create(
        request,
        now=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    )
    state_machine.register(snapshot)
    state_machine.transition(
        request.execution_id,
        ExecutionState.QUEUED,
        now=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    state_machine.transition(
        request.execution_id,
        ExecutionState.RUNNING,
        now=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC),
    )

    result = controller.timeout(
        request.execution_id,
        now=datetime(2026, 1, 1, 0, 0, 4, tzinfo=UTC),
    )

    assert result.timed_out
    evidence = controller.evidence(request.execution_id)

    assert evidence is not None
    assert evidence.payload["state"] == ExecutionState.TIMED_OUT.value
    assert evidence.payload["error_type"] == "TimeoutError"
    assert evidence.verify()


def test_evidence_is_idempotent() -> None:
    store = EvidenceStore()
    observability = RuntimeExecutionObservability(store)
    engine = RuntimeExecutionEngine(evidence_store=store)
    request = engine.create_request("runtime.test")
    outcome = engine.execute(request, lambda _: "ok")

    assert outcome.snapshot is not None

    first = observability.record(
        outcome.snapshot,
        result=outcome.result,
        cleanup=outcome.cleanup,
    )
    second = observability.record(
        outcome.snapshot,
        result=outcome.result,
        cleanup=outcome.cleanup,
    )

    assert first is second
    assert len(store.records()) == 1
    assert store.verify(first.evidence_id)


def test_cleanup_failure_is_recorded_in_evidence() -> None:
    store = EvidenceStore()
    cleanup_manager = RuntimeExecutionCleanupManager()
    engine = RuntimeExecutionEngine(
        cleanup_manager=cleanup_manager,
        evidence_store=store,
    )
    request = engine.create_request("runtime.test")

    cleanup_manager.register(
        request.execution_id,
        lambda: (_ for _ in ()).throw(RuntimeError("cleanup boom")),
        name="broken-cleanup",
    )

    outcome = engine.execute(request, lambda _: "ok")

    assert outcome.success
    assert outcome.cleanup is not None
    assert outcome.cleanup.failed

    evidence = engine.evidence(request.execution_id)

    assert evidence is not None
    assert evidence.payload["cleanup"]["failed"] is True
    assert evidence.payload["cleanup"]["failures"][0]["name"] == "broken-cleanup"
    assert evidence.verify()
