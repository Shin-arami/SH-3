"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
packet.py
"""

from __future__ import annotations

from enum import IntEnum, StrEnum, unique

__all__ = ["PacketFlag", "PacketType"]


@unique
class PacketType(StrEnum):
    UNKNOWN = "unknown"

    COMMAND = "command"
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"

    DATA = "data"
    MESSAGE = "message"
    STREAM = "stream"

    QUERY = "query"
    RESULT = "result"

    MEMORY = "memory"
    KNOWLEDGE = "knowledge"

    TASK = "task"
    PLAN = "plan"
    GOAL = "goal"
    ACTION = "action"

    MODEL = "model"
    REASONING = "reasoning"
    LEARNING = "learning"
    REFLECTION = "reflection"

    HEARTBEAT = "heartbeat"
    STATUS = "status"

    ERROR = "error"
    WARNING = "warning"

    CONTROL = "control"
    SYSTEM = "system"

    @property
    def request(self) -> bool:
        return self in {
            PacketType.REQUEST,
            PacketType.QUERY,
            PacketType.COMMAND,
        }

    @property
    def response(self) -> bool:
        return self in {
            PacketType.RESPONSE,
            PacketType.RESULT,
        }

    @property
    def communication(self) -> bool:
        return self in {
            PacketType.REQUEST,
            PacketType.RESPONSE,
            PacketType.MESSAGE,
            PacketType.STREAM,
            PacketType.EVENT,
        }

    @property
    def cognition(self) -> bool:
        return self in {
            PacketType.MEMORY,
            PacketType.KNOWLEDGE,
            PacketType.REASONING,
            PacketType.LEARNING,
            PacketType.REFLECTION,
            PacketType.PLAN,
            PacketType.GOAL,
            PacketType.ACTION,
        }

    @property
    def runtime(self) -> bool:
        return self in {
            PacketType.SYSTEM,
            PacketType.CONTROL,
            PacketType.STATUS,
            PacketType.HEARTBEAT,
        }

    @property
    def failure(self) -> bool:
        return self in {
            PacketType.ERROR,
            PacketType.WARNING,
        }


@unique
class PacketFlag(IntEnum):
    NONE = 0
    URGENT = 1 << 0
    COMPRESSED = 1 << 1
    ENCRYPTED = 1 << 2
    SIGNED = 1 << 3
    CACHED = 1 << 4
    PERSISTENT = 1 << 5
    BROADCAST = 1 << 6
    MULTICAST = 1 << 7
    INTERNAL = 1 << 8
    EXTERNAL = 1 << 9
    RETRY = 1 << 10
    FRAGMENT = 1 << 11
    LAST_FRAGMENT = 1 << 12
    ACK_REQUIRED = 1 << 13
    ACK = 1 << 14
    READONLY = 1 << 15

    @classmethod
    def has(cls, flags: int, flag: PacketFlag) -> bool:
        return (flags & flag) == flag

    @classmethod
    def add(cls, flags: int, flag: PacketFlag) -> int:
        return flags | flag

    @classmethod
    def remove(cls, flags: int, flag: PacketFlag) -> int:
        return flags & ~flag
