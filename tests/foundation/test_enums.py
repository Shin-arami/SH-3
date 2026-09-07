from __future__ import annotations

from enum import Enum

from foundation.enums import (
    FOUNDATION_ENUMS,
    LifecycleState,
    Severity,
)


def test_lifecycle_state_is_string_enum() -> None:
    assert issubclass(LifecycleState, str)
    assert issubclass(LifecycleState, Enum)


def test_lifecycle_state_values() -> None:
    assert LifecycleState.CREATED.value == "CREATED"
    assert LifecycleState.ACTIVE.value == "ACTIVE"
    assert LifecycleState.SUSPENDED.value == "SUSPENDED"
    assert LifecycleState.TERMINATED.value == "TERMINATED"


def test_severity_is_string_enum() -> None:
    assert issubclass(Severity, str)
    assert issubclass(Severity, Enum)


def test_severity_values() -> None:
    assert Severity.INFO.value == "INFO"
    assert Severity.LOW.value == "LOW"
    assert Severity.MEDIUM.value == "MEDIUM"
    assert Severity.HIGH.value == "HIGH"
    assert Severity.CRITICAL.value == "CRITICAL"


def test_enum_values_are_unique() -> None:
    for enum_type in FOUNDATION_ENUMS:
        values = tuple(member.value for member in enum_type)
        assert len(values) == len(set(values))


def test_foundation_enums_are_registered() -> None:
    assert LifecycleState in FOUNDATION_ENUMS
    assert Severity in FOUNDATION_ENUMS
