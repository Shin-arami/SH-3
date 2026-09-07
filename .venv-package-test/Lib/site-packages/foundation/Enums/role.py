"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
role.py
"""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["Role"]


@unique
class Role(StrEnum):
    UNKNOWN = "unknown"
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    KERNEL = "kernel"
    CORE = "core"
    SERVICE = "service"
    RUNTIME = "runtime"
    SCHEDULER = "scheduler"
    PIPELINE = "pipeline"
    MEMORY = "memory"
    PLANNER = "planner"
    REASONER = "reasoner"
    LEARNER = "learner"
    WORLD_MODEL = "world_model"
    REFLECTION = "reflection"
    VALIDATOR = "validator"
    SERIALIZER = "serializer"
    FACTORY = "factory"
    CACHE = "cache"
    EVENTBUS = "eventbus"
    PLUGIN = "plugin"
    AGENT = "agent"
    OBSERVER = "observer"
    EXECUTOR = "executor"
    LOGGER = "logger"
    MONITOR = "monitor"

    @property
    def is_system(self) -> bool:
        return self in {
            Role.SYSTEM,
            Role.KERNEL,
            Role.CORE,
            Role.SERVICE,
            Role.RUNTIME,
            Role.SCHEDULER,
            Role.PIPELINE,
            Role.VALIDATOR,
            Role.SERIALIZER,
            Role.FACTORY,
            Role.CACHE,
            Role.EVENTBUS,
            Role.LOGGER,
            Role.MONITOR,
        }

    @property
    def is_ai(self) -> bool:
        return self in {
            Role.ASSISTANT,
            Role.AGENT,
            Role.MEMORY,
            Role.PLANNER,
            Role.REASONER,
            Role.LEARNER,
            Role.WORLD_MODEL,
            Role.REFLECTION,
        }

    @property
    def is_runtime(self) -> bool:
        return self in {
            Role.RUNTIME,
            Role.SCHEDULER,
            Role.PIPELINE,
            Role.EXECUTOR,
        }

    @property
    def is_user(self) -> bool:
        return self is Role.USER

    @property
    def is_tool(self) -> bool:
        return self in {
            Role.TOOL,
            Role.PLUGIN,
        }

    @property
    def executable(self) -> bool:
        return self in {
            Role.ASSISTANT,
            Role.AGENT,
            Role.CORE,
            Role.SERVICE,
            Role.RUNTIME,
            Role.EXECUTOR,
            Role.TOOL,
            Role.PLUGIN,
        }
