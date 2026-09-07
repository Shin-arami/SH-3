"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
runtime.py
"""

from __future__ import annotations

from enum import IntEnum, StrEnum, unique

__all__ = ["ExecutionMode", "RuntimeState"]


@unique
class RuntimeState(StrEnum):
    UNKNOWN = "unknown"
    CREATED = "created"
    BOOTING = "booting"
    INITIALIZING = "initializing"
    READY = "ready"
    IDLE = "idle"
    RUNNING = "running"
    BUSY = "busy"
    WAITING = "waiting"
    SLEEPING = "sleeping"
    PAUSED = "paused"
    RESUMING = "resuming"
    STOPPING = "stopping"
    STOPPED = "stopped"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"
    FAILED = "failed"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"

    @property
    def active(self) -> bool:
        return self in {
            RuntimeState.READY,
            RuntimeState.IDLE,
            RuntimeState.RUNNING,
            RuntimeState.BUSY,
            RuntimeState.WAITING,
            RuntimeState.SLEEPING,
            RuntimeState.PAUSED,
            RuntimeState.RESUMING,
        }

    @property
    def executable(self) -> bool:
        return self in {
            RuntimeState.READY,
            RuntimeState.IDLE,
            RuntimeState.RUNNING,
            RuntimeState.BUSY,
        }

    @property
    def recoverable(self) -> bool:
        return self in {
            RuntimeState.FAILED,
            RuntimeState.STOPPED,
            RuntimeState.TERMINATED,
        }

    @property
    def terminal(self) -> bool:
        return self in {
            RuntimeState.STOPPED,
            RuntimeState.TERMINATED,
        }

    @property
    def failed(self) -> bool:
        return self is RuntimeState.FAILED


@unique
class ExecutionMode(IntEnum):
    DISABLED = 0
    MANUAL = 1
    STEP = 2
    SINGLE = 3
    NORMAL = 4
    CONTINUOUS = 5
    PARALLEL = 6
    ASYNC = 7
    DISTRIBUTED = 8
    REALTIME = 9

    @property
    def automatic(self) -> bool:
        return self >= ExecutionMode.NORMAL

    @property
    def concurrent(self) -> bool:
        return self in {
            ExecutionMode.PARALLEL,
            ExecutionMode.ASYNC,
            ExecutionMode.DISTRIBUTED,
        }

    @property
    def realtime(self) -> bool:
        return self is ExecutionMode.REALTIME

    @classmethod
    def default(cls) -> ExecutionMode:
        return cls.NORMAL

    @classmethod
    def safest(cls) -> ExecutionMode:
        return cls.MANUAL

    @classmethod
    def fastest(cls) -> ExecutionMode:
        return cls.REALTIME
