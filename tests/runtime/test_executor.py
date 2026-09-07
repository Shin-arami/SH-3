from __future__ import annotations

import pytest

from foundation.utils.exceptions import RuntimeException, SH3Exception
from runtime.context_manager import RuntimeContext
from runtime.executor import ExecutionResult, RuntimeExecutor


def test_execute_returns_result() -> None:
    executor = RuntimeExecutor()
    result = executor.execute(lambda x: x + 1, 1)
    assert isinstance(result, ExecutionResult)
    assert result.value == 2
    assert result.succeeded


def test_run_returns_value() -> None:
    executor = RuntimeExecutor()
    assert executor.run(lambda x: x + 1, 1) == 2


def test_execute_preserves_arguments() -> None:
    executor = RuntimeExecutor()
    assert executor.run(lambda a, b=0: a + b, 2, b=3) == 5


def test_execute_records_function_name() -> None:
    executor = RuntimeExecutor()

    def operation() -> str:
        return "ok"

    result = executor.execute(operation)
    assert result.function == "operation"


def test_execute_uses_context_trace_id() -> None:
    executor = RuntimeExecutor()
    context = RuntimeContext("test-context")
    result = executor.execute(lambda: "ok", context=context)
    assert result.trace_id == context.trace_id


def test_execute_rejects_non_callable() -> None:
    executor = RuntimeExecutor()

    with pytest.raises(RuntimeException):
        executor.execute(123)  # type: ignore[arg-type]


def test_sh3_exception_is_preserved() -> None:
    executor = RuntimeExecutor()

    class TestSH3Exception(SH3Exception):
        pass

    def fail() -> None:
        raise TestSH3Exception("failure")

    with pytest.raises(TestSH3Exception):
        executor.run(fail)


def test_unhandled_exception_becomes_runtime_exception() -> None:
    executor = RuntimeExecutor()

    def fail() -> None:
        raise ValueError("failure")

    with pytest.raises(RuntimeException):
        executor.run(fail)


def test_kwargs_are_forwarded() -> None:
    executor = RuntimeExecutor()

    def operation(*, value: int) -> int:
        return value * 2

    assert executor.run(operation, value=5) == 10


def test_empty_context_has_empty_trace_id() -> None:
    executor = RuntimeExecutor()
    result = executor.execute(lambda: "ok")
    assert result.trace_id == ""
