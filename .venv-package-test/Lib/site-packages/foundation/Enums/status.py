"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
status.py
"""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["Status"]


@unique
class Status(StrEnum):
    UNKNOWN = "unknown"
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    READY = "ready"
    IDLE = "idle"
    WAITING = "waiting"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    RESUMING = "resuming"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    SHUTDOWN = "shutdown"
    DISABLED = "disabled"
    DELETED = "deleted"
    ARCHIVED = "archived"
    ERROR = "error"

    @property
    def active(self) -> bool:
        return self in {
            Status.READY,
            Status.IDLE,
            Status.WAITING,
            Status.QUEUED,
            Status.RUNNING,
            Status.PAUSED,
            Status.RESUMING,
            Status.RETRYING,
        }

    @property
    def finished(self) -> bool:
        return self in {
            Status.SUCCESS,
            Status.COMPLETED,
            Status.FAILED,
            Status.CANCELLED,
            Status.TIMEOUT,
            Status.TERMINATED,
            Status.DELETED,
            Status.ARCHIVED,
        }

    @property
    def failed(self) -> bool:
        return self in {
            Status.ERROR,
            Status.FAILED,
            Status.TIMEOUT,
        }

    @property
    def executable(self) -> bool:
        return self in {
            Status.CREATED,
            Status.INITIALIZED,
            Status.READY,
            Status.IDLE,
            Status.WAITING,
            Status.QUEUED,
        }

    @property
    def terminal(self) -> bool:
        return self.finished
