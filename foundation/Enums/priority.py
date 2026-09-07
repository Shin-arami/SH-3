"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
priority.py
"""

from __future__ import annotations

from enum import IntEnum, unique

__all__ = ["Priority"]


@unique
class Priority(IntEnum):
    LOWEST = 0
    VERY_LOW = 10
    LOW = 20
    BELOW_NORMAL = 30
    NORMAL = 50
    ABOVE_NORMAL = 70
    HIGH = 80
    VERY_HIGH = 90
    CRITICAL = 95
    EMERGENCY = 99
    REALTIME = 100

    @property
    def score(self) -> int:
        return int(self)

    @property
    def is_realtime(self) -> bool:
        return self is Priority.REALTIME

    @property
    def is_emergency(self) -> bool:
        return self >= Priority.EMERGENCY

    @property
    def is_critical(self) -> bool:
        return self >= Priority.CRITICAL

    @property
    def is_high(self) -> bool:
        return self >= Priority.HIGH

    @property
    def is_normal(self) -> bool:
        return Priority.LOW < self < Priority.HIGH

    @property
    def is_low(self) -> bool:
        return self <= Priority.LOW

    @classmethod
    def clamp(cls, value: int) -> Priority:
        if value <= cls.LOWEST:
            return cls.LOWEST
        if value >= cls.REALTIME:
            return cls.REALTIME
        nearest = cls.NORMAL
        distance = abs(value - int(cls.NORMAL))
        for item in cls:
            d = abs(value - int(item))
            if d < distance:
                nearest = item
                distance = d
        return nearest

    @classmethod
    def from_value(cls, value: int) -> Priority:
        return cls.clamp(value)

    @classmethod
    def elevate(cls, p: Priority) -> Priority:
        order = (
            cls.LOWEST,
            cls.VERY_LOW,
            cls.LOW,
            cls.BELOW_NORMAL,
            cls.NORMAL,
            cls.ABOVE_NORMAL,
            cls.HIGH,
            cls.VERY_HIGH,
            cls.CRITICAL,
            cls.EMERGENCY,
            cls.REALTIME,
        )
        i = order.index(p)
        return order[min(i + 1, len(order) - 1)]

    @classmethod
    def lower(cls, p: Priority) -> Priority:
        order = (
            cls.LOWEST,
            cls.VERY_LOW,
            cls.LOW,
            cls.BELOW_NORMAL,
            cls.NORMAL,
            cls.ABOVE_NORMAL,
            cls.HIGH,
            cls.VERY_HIGH,
            cls.CRITICAL,
            cls.EMERGENCY,
            cls.REALTIME,
        )
        i = order.index(p)
        return order[max(i - 1, 0)]
