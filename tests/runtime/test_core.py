from __future__ import annotations

from typing import Any

import pytest

from foundation.utils.exceptions import RuntimeException, SH3Exception
from runtime.context_manager import RuntimeContext
from runtime.core import RuntimeCore


def test_runtime_core_initialization() -> None:
    runtime = RuntimeCore()
    assert runtime.name == "sh3-runtime"
    assert runtime.context.name == "sh3-runtime"
    assert runtime.context.trace_id
    assert runtime.hooks == {}


def test_run_returns_result() -> None:
    runtime = RuntimeCore()
    assert runtime.run(lambda: 42) == 42


def test_run_passes_args_and_kwargs() -> None:
    runtime = RuntimeCore()

    def operation(a: int, b: int, *, scale: int = 1) -> int:
        return (a + b) * scale

    assert runtime.run(operation, 2, 3, scale=4) == 20


def test_run_uses_custom_context() -> None:
    runtime = RuntimeCore()
    context = RuntimeContext("custom")
    context.set("value", 100)

    def operation() -> int:
        return 7

    assert runtime.run(operation, context=context) == 7


def test_pipe_executes_functions_in_order() -> None:
    runtime = RuntimeCore()
    result = runtime.pipe(
        2,
        lambda value: value + 3,
        lambda value: value * 4,
        lambda value: value - 5,
    )
    assert result == 15


def test_state_management() -> None:
    runtime = RuntimeCore()
    runtime.set_state("x", 10)
    assert runtime.get_state("x") == 10
    assert runtime.get_state("missing") is None
    assert runtime.get_state("missing", 99) == 99


def test_hook_is_called() -> None:
    runtime = RuntimeCore()
    calls: list[tuple[str, dict[str, Any]]] = []

    def hook(payload: dict[str, Any]) -> None:
        calls.append(("hook", payload))

    runtime.register_hook("before_run", hook)
    assert runtime.run(lambda: "ok") == "ok"
    assert len(calls) == 1
    assert calls[0][1]["function"] == "<lambda>"


def test_after_run_hook_is_called() -> None:
    runtime = RuntimeCore()
    results: list[dict[str, Any]] = []

    runtime.register_hook("after_run", lambda payload: results.append(payload))
    assert runtime.run(lambda: 123) == 123
    assert len(results) == 1
    assert results[0]["result"] == "123"


def test_pipe_before_hook_is_called() -> None:
    runtime = RuntimeCore()
    calls: list[dict[str, Any]] = []

    runtime.register_hook("before_pipe", lambda payload: calls.append(payload))
    assert runtime.pipe(1, lambda value: value + 1) == 2
    assert len(calls) == 1
    assert calls[0]["function"] == "<lambda>"


def test_snapshot() -> None:
    runtime = RuntimeCore("test-runtime")
    runtime.register_hook("before_run", lambda _: None)
    snapshot = runtime.snapshot()
    assert snapshot["name"] == "test-runtime"
    assert snapshot["context"]["name"] == "test-runtime"
    assert snapshot["hooks"] == ["before_run"]


def test_sh3_exception_is_preserved() -> None:
    runtime = RuntimeCore()

    class TestSH3Exception(SH3Exception):
        pass

    with pytest.raises(TestSH3Exception):
        runtime.run(lambda: (_ for _ in ()).throw(TestSH3Exception("failure")))


def test_unhandled_exception_becomes_runtime_exception() -> None:
    runtime = RuntimeCore()

    with pytest.raises(RuntimeException):
        runtime.run(lambda: (_ for _ in ()).throw(ValueError("failure")))
