"""
SH-3 Complete Edition v1.0
Foundation Layer
Enums Subsystem
category.py
"""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["Category"]


@unique
class Category(StrEnum):
    """
    SH-3 Category System

    システム内あらゆるオブジェクトの意味的分類軸。

    Memory / Event / Node / Task / Data を横断して使用される。
    """

    UNKNOWN = "unknown"

    FOUNDATION = "foundation"
    CONFIG = "config"
    TYPE = "type"
    ENUM = "enum"
    UTILITY = "utility"
    EXCEPTION = "exception"
    LOGGING = "logging"

    NODE = "node"
    COMPONENT = "component"
    ENTITY = "entity"
    PACKET = "packet"
    TRANSPORT = "transport"

    RUNTIME = "runtime"
    EXECUTION = "execution"
    PIPELINE = "pipeline"
    SCHEDULER = "scheduler"
    LIFECYCLE = "lifecycle"
    EVENT = "event"

    MEMORY = "memory"
    WORKING_MEMORY = "working_memory"
    SHORT_TERM_MEMORY = "short_term_memory"
    LONG_TERM_MEMORY = "long_term_memory"
    EPISODIC_MEMORY = "episodic_memory"
    SEMANTIC_MEMORY = "semantic_memory"

    REASONING = "reasoning"
    PLANNING = "planning"
    LEARNING = "learning"
    REFLECTION = "reflection"
    WORLD_MODEL = "world_model"

    GOAL = "goal"
    STRATEGY = "strategy"
    PLAN = "plan"
    TASK = "task"
    ACTION = "action"

    KNOWLEDGE = "knowledge"
    FACT = "fact"
    BELIEF = "belief"
    RULE = "rule"
    CONCEPT = "concept"

    GRAPH = "graph"
    NODE_GRAPH = "node_graph"
    EDGE = "edge"
    RELATION = "relation"

    VECTOR = "vector"
    EMBEDDING = "embedding"
    METADATA = "metadata"

    CACHE = "cache"
    STORAGE = "storage"
    SERIALIZER = "serializer"
    VALIDATOR = "validator"
    FACTORY = "factory"

    AGENT = "agent"
    MODEL = "model"
    TOOL = "tool"
    PLUGIN = "plugin"

    INPUT = "input"
    OUTPUT = "output"
    MESSAGE = "message"
    RESPONSE = "response"

    USER = "user"
    SYSTEM = "system"

    @property
    def is_foundation(self) -> bool:
        return self in {
            Category.FOUNDATION,
            Category.CONFIG,
            Category.TYPE,
            Category.ENUM,
            Category.UTILITY,
            Category.EXCEPTION,
            Category.LOGGING,
        }

    @property
    def is_base(self) -> bool:
        return self in {
            Category.NODE,
            Category.COMPONENT,
            Category.ENTITY,
            Category.PACKET,
            Category.TRANSPORT,
        }

    @property
    def is_runtime(self) -> bool:
        return self in {
            Category.RUNTIME,
            Category.EXECUTION,
            Category.PIPELINE,
            Category.SCHEDULER,
            Category.LIFECYCLE,
            Category.EVENT,
        }

    @property
    def is_memory(self) -> bool:
        return self in {
            Category.MEMORY,
            Category.WORKING_MEMORY,
            Category.SHORT_TERM_MEMORY,
            Category.LONG_TERM_MEMORY,
            Category.EPISODIC_MEMORY,
            Category.SEMANTIC_MEMORY,
        }

    @property
    def is_cognition(self) -> bool:
        return self in {
            Category.REASONING,
            Category.PLANNING,
            Category.LEARNING,
            Category.REFLECTION,
            Category.WORLD_MODEL,
        }

    @property
    def is_knowledge(self) -> bool:
        return self in {
            Category.KNOWLEDGE,
            Category.FACT,
            Category.BELIEF,
            Category.RULE,
            Category.CONCEPT,
        }

    @property
    def is_service(self) -> bool:
        return self in {
            Category.CACHE,
            Category.STORAGE,
            Category.SERIALIZER,
            Category.VALIDATOR,
            Category.FACTORY,
        }

    @property
    def is_graph(self) -> bool:
        return self in {
            Category.GRAPH,
            Category.NODE_GRAPH,
            Category.EDGE,
            Category.RELATION,
        }

    @property
    def is_ai(self) -> bool:
        return self in {
            Category.AGENT,
            Category.MODEL,
            Category.TOOL,
            Category.PLUGIN,
        }
