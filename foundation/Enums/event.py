"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
event.py
"""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["EventType"]


@unique
class EventType(StrEnum):
    UNKNOWN = "unknown"

    CREATED = "created"
    INITIALIZED = "initialized"
    UPDATED = "updated"
    DELETED = "deleted"

    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART = "restart"

    LOAD = "load"
    SAVE = "save"
    IMPORT = "import"
    EXPORT = "export"

    SEND = "send"
    RECEIVE = "receive"
    REQUEST = "request"
    RESPONSE = "response"

    EXECUTE = "execute"
    COMPLETE = "complete"
    CANCEL = "cancel"
    TIMEOUT = "timeout"

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    WARNING = "warning"

    VALIDATE = "validate"
    SERIALIZE = "serialize"
    DESERIALIZE = "deserialize"

    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_CLEAR = "cache_clear"

    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MEMORY_DELETE = "memory_delete"

    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    PLAN_COMPLETED = "plan_completed"

    LEARNING_START = "learning_start"
    LEARNING_END = "learning_end"

    REASONING_START = "reasoning_start"
    REASONING_END = "reasoning_end"

    REFLECTION_START = "reflection_start"
    REFLECTION_END = "reflection_end"

    WORLDMODEL_UPDATE = "worldmodel_update"

    NODE_CREATED = "node_created"
    NODE_UPDATED = "node_updated"
    NODE_REMOVED = "node_removed"

    PACKET_CREATED = "packet_created"
    PACKET_SENT = "packet_sent"
    PACKET_RECEIVED = "packet_received"
    PACKET_DROPPED = "packet_dropped"

    SHUTDOWN = "shutdown"

    @property
    def lifecycle(self) -> bool:
        return self in {
            EventType.CREATED,
            EventType.INITIALIZED,
            EventType.UPDATED,
            EventType.DELETED,
            EventType.START,
            EventType.STOP,
            EventType.PAUSE,
            EventType.RESUME,
            EventType.RESTART,
            EventType.SHUTDOWN,
        }

    @property
    def execution(self) -> bool:
        return self in {
            EventType.EXECUTE,
            EventType.COMPLETE,
            EventType.CANCEL,
            EventType.TIMEOUT,
        }

    @property
    def communication(self) -> bool:
        return self in {
            EventType.SEND,
            EventType.RECEIVE,
            EventType.REQUEST,
            EventType.RESPONSE,
        }

    @property
    def packet(self) -> bool:
        return self in {
            EventType.PACKET_CREATED,
            EventType.PACKET_SENT,
            EventType.PACKET_RECEIVED,
            EventType.PACKET_DROPPED,
        }

    @property
    def memory(self) -> bool:
        return self in {
            EventType.MEMORY_READ,
            EventType.MEMORY_WRITE,
            EventType.MEMORY_DELETE,
        }

    @property
    def planning(self) -> bool:
        return self in {
            EventType.PLAN_CREATED,
            EventType.PLAN_UPDATED,
            EventType.PLAN_COMPLETED,
        }

    @property
    def reasoning(self) -> bool:
        return self in {
            EventType.REASONING_START,
            EventType.REASONING_END,
        }

    @property
    def learning(self) -> bool:
        return self in {
            EventType.LEARNING_START,
            EventType.LEARNING_END,
        }

    @property
    def reflection(self) -> bool:
        return self in {
            EventType.REFLECTION_START,
            EventType.REFLECTION_END,
        }

    @property
    def success(self) -> bool:
        return self is EventType.SUCCESS

    @property
    def failure(self) -> bool:
        return self in {
            EventType.FAILURE,
            EventType.ERROR,
            EventType.TIMEOUT,
        }
