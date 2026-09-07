"""
SH-3 Complete Edition v1.0
Foundation Layer
Types Subsystem

identifiers.py

Kernel identifier utilities.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from .aliases import (
    ComponentId,
    EntityId,
    Identifier,
    NodeId,
    PacketId,
    SessionId,
    TaskId,
    TraceId,
)

__all__ = [
    "IdentifierGenerator",
    "IdentifierInfo",
    "IdentifierValidator",
]

# ==========================================================
# Prefix
# ==========================================================

_SEPARATOR: Final[str] = "_"

_PREFIX_NODE: Final[str] = "nd"
_PREFIX_COMPONENT: Final[str] = "cmp"
_PREFIX_ENTITY: Final[str] = "ent"
_PREFIX_PACKET: Final[str] = "pkt"
_PREFIX_SESSION: Final[str] = "ses"
_PREFIX_TRACE: Final[str] = "trc"
_PREFIX_TASK: Final[str] = "tsk"

# ==========================================================
# Info
# ==========================================================


@dataclass(slots=True, frozen=True)
class IdentifierInfo:
    prefix: str

    value: str

    timestamp: str


# ==========================================================
# Generator
# ==========================================================


class IdentifierGenerator:
    @staticmethod
    def uuid() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def short(length: int = 16) -> str:
        return secrets.token_hex(length // 2)

    @staticmethod
    def timestamp() -> str:
        return datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    @classmethod
    def create(
        cls,
        prefix: str,
    ) -> Identifier:

        return prefix + _SEPARATOR + cls.timestamp() + _SEPARATOR + cls.short()

    @classmethod
    def node(cls) -> NodeId:
        return cls.create(_PREFIX_NODE)

    @classmethod
    def component(cls) -> ComponentId:
        return cls.create(_PREFIX_COMPONENT)

    @classmethod
    def entity(cls) -> EntityId:
        return cls.create(_PREFIX_ENTITY)

    @classmethod
    def packet(cls) -> PacketId:
        return cls.create(_PREFIX_PACKET)

    @classmethod
    def session(cls) -> SessionId:
        return cls.create(_PREFIX_SESSION)

    @classmethod
    def trace(cls) -> TraceId:
        return cls.create(_PREFIX_TRACE)

    @classmethod
    def task(cls) -> TaskId:
        return cls.create(_PREFIX_TASK)


# ==========================================================
# Validator
# ==========================================================


class IdentifierValidator:
    @staticmethod
    def is_valid(
        value: str,
    ) -> bool:

        if not value:
            return False

        parts = value.split(_SEPARATOR)

        if len(parts) != 3:
            return False

        prefix, stamp, token = parts

        if not prefix:
            return False

        if len(stamp) != 14:
            return False

        if not stamp.isdigit():
            return False

        return len(token) >= 8

    @staticmethod
    def parse(
        value: str,
    ) -> IdentifierInfo:

        if not IdentifierValidator.is_valid(value):
            raise ValueError(f"Invalid identifier: {value}")

        prefix, stamp, token = value.split(_SEPARATOR)

        return IdentifierInfo(
            prefix=prefix,
            value=token,
            timestamp=stamp,
        )
