from __future__ import annotations

from types import MappingProxyType
from typing import Any, cast

import pytest

from runtime.execution_context import ExecutionContext


def test_context_create() -> None:
    context = ExecutionContext.create(
        execution_id="exec-1",
        correlation_id="corr-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        metadata={"component": "runtime"},
    )

    assert context.execution_id == "exec-1"
    assert context.correlation_id == "corr-1"
    assert context.trace_id == "trace-1"
    assert context.tenant_id == "tenant-1"
    assert context.attempt == 0
    assert context.metadata["component"] == "runtime"
    assert isinstance(context.metadata, MappingProxyType)


def test_context_is_immutable() -> None:
    context = ExecutionContext.create(
        execution_id="exec-1",
        correlation_id="corr-1",
    )

    with pytest.raises(TypeError):
        cast(dict[str, Any], context.metadata)["x"] = 1


def test_context_next_attempt() -> None:
    context = ExecutionContext.create(
        execution_id="exec-1",
        correlation_id="corr-1",
        trace_id="trace-1",
        metadata={"x": 1},
    )

    next_context = context.next_attempt()

    assert next_context.execution_id == context.execution_id
    assert next_context.correlation_id == context.correlation_id
    assert next_context.trace_id == context.trace_id
    assert next_context.attempt == 1
    assert next_context.metadata == context.metadata


def test_context_with_causation() -> None:
    context = ExecutionContext.create(
        execution_id="exec-1",
        correlation_id="corr-1",
    )

    updated = context.with_causation("event-1")

    assert updated.causation_id == "event-1"
    assert updated.execution_id == context.execution_id
    assert updated.correlation_id == context.correlation_id
    assert updated.attempt == context.attempt


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_id", ""),
        ("correlation_id", ""),
        ("causation_id", ""),
        ("trace_id", ""),
        ("tenant_id", ""),
    ],
)
def test_context_rejects_empty_identifiers(field: str, value: str) -> None:
    values: dict[str, Any] = {
        "execution_id": "exec-1",
        "correlation_id": "corr-1",
        "causation_id": None,
        "trace_id": None,
        "tenant_id": None,
    }
    values[field] = value

    with pytest.raises(ValueError):
        ExecutionContext.create(**values)


def test_context_rejects_invalid_attempt() -> None:
    with pytest.raises(ValueError):
        ExecutionContext.create(
            execution_id="exec-1",
            correlation_id="corr-1",
            attempt=-1,
        )
