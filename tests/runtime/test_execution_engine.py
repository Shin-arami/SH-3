from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from runtime.execution import ExecutionState
from runtime.execution_engine import RuntimeExecutionEngine


def test_engine_executes_registered_operation() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("add", lambda payload: payload["a"] + payload["b"])
    request = engine.create_request("add", {"a": 2, "b": 3})

    outcome = engine.execute(request)

    assert outcome.success
    assert outcome.state is ExecutionState.COMPLETED
    assert outcome.result == 5
    assert outcome.error is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.state is ExecutionState.COMPLETED


def test_engine_executes_explicit_operation() -> None:
    engine = RuntimeExecutionEngine()
    request = engine.create_request("dynamic", {"value": 7})

    outcome = engine.execute(request, lambda payload: payload["value"] * 2)

    assert outcome.success
    assert outcome.result == 14


def test_engine_records_failed_operation() -> None:
    engine = RuntimeExecutionEngine()

    def fail(_: Mapping[str, Any]) -> None:
        raise ValueError("boom")

    request = engine.create_request("fail", {})
    outcome = engine.execute(request, fail)

    assert not outcome.success
    assert outcome.failed
    assert outcome.state is ExecutionState.FAILED
    assert isinstance(outcome.error, ValueError)
    assert outcome.snapshot is not None
    assert outcome.snapshot.state is ExecutionState.FAILED
    assert outcome.snapshot.error_type == "ValueError"
    assert outcome.snapshot.error_message == "boom"

    stored = engine.snapshot(request.execution_id)

    assert stored.state is ExecutionState.FAILED
    assert stored.error_type == "ValueError"
    assert stored.error_message == "boom"


def test_engine_fails_when_operation_is_missing() -> None:
    engine = RuntimeExecutionEngine()
    request = engine.create_request("missing", {})

    outcome = engine.execute(request)

    assert not outcome.success
    assert outcome.state is ExecutionState.FAILED
    assert isinstance(outcome.error, LookupError)


def test_engine_submit_returns_handle() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("echo", lambda payload: payload["value"])
    request = engine.create_request("echo", {"value": "ok"})

    handle = engine.submit(request)

    assert handle.execution_id == request.execution_id
    assert handle.state is ExecutionState.COMPLETED
    assert handle.snapshot().execution_id == request.execution_id
    outcome = handle.outcome()
    assert outcome is not None
    assert outcome.result == "ok"


def test_engine_snapshot_is_retrievable() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("noop", lambda _: None)
    request = engine.create_request("noop")

    engine.execute(request)
    snapshot = engine.snapshot(request.execution_id)

    assert snapshot.execution_id == request.execution_id
    assert snapshot.operation == "noop"
    assert snapshot.state is ExecutionState.COMPLETED


def test_engine_outcome_is_retrievable() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("value", lambda _: 42)
    request = engine.create_request("value")

    outcome = engine.execute(request)

    assert engine.outcome(request.execution_id) == outcome


def test_engine_rejects_invalid_request() -> None:
    engine = RuntimeExecutionEngine()

    with pytest.raises(TypeError, match="request must be ExecutionRequest"):
        engine.execute(object())  # type: ignore[arg-type]


def test_engine_registers_and_unregisters_operations() -> None:
    engine = RuntimeExecutionEngine()
    def operation(_: Mapping[str, Any]) -> None:
        return None

    engine.register_operation("test", operation)

    assert engine.get_operation("test") is operation
    assert "test" in engine.operations
    assert engine.unregister_operation("test")
    assert engine.get_operation("test") is None
    assert not engine.unregister_operation("test")


def test_engine_rejects_duplicate_operation_without_replace() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("test", lambda _: 1)

    with pytest.raises(ValueError, match="already registered"):
        engine.register_operation("test", lambda _: 2)


def test_engine_replaces_registered_operation() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("test", lambda _: 1)
    engine.register_operation("test", lambda _: 2, replace=True)
    request = engine.create_request("test")

    outcome = engine.execute(request)

    assert outcome.result == 2


def test_engine_rejects_invalid_operation_registration() -> None:
    engine = RuntimeExecutionEngine()

    with pytest.raises(ValueError, match="name must not be empty"):
        engine.register_operation("", lambda _: None)

    with pytest.raises(TypeError, match="operation must be callable"):
        engine.register_operation("invalid", object())  # type: ignore[arg-type]


def test_engine_lists_execution_snapshots() -> None:
    engine = RuntimeExecutionEngine()
    engine.register_operation("noop", lambda _: None)

    first = engine.create_request("noop")
    second = engine.create_request("noop")

    engine.execute(first)
    engine.execute(second)

    executions = engine.executions()

    assert len(executions) == 2
    assert {item.execution_id for item in executions} == {
        first.execution_id,
        second.execution_id,
    }
