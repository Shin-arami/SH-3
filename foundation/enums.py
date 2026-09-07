from __future__ import annotations

from enum import StrEnum
from typing import Final


class LifecycleState(StrEnum):
    """SH-3 component lifecycle state."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class Severity(StrEnum):
    """SH-3 severity classification."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


FOUNDATION_ENUMS: Final[tuple[type[StrEnum], ...]] = (
    LifecycleState,
    Severity,
)


__all__: Final[tuple[str, ...]] = (
    "FOUNDATION_ENUMS",
    "LifecycleState",
    "Severity",
)
