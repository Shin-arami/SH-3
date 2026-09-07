"""
SH-3 Complete Edition v1.0
Foundation Layer
Configuration Subsystem

categories.py

Kernel namespace definitions.

Categories define the semantic namespace shared by every
Subsystem and Core.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "CATEGORY_ACTION",
    # AI
    "CATEGORY_AGENT",
    "CATEGORY_BELIEF",
    "CATEGORY_COMPONENT",
    "CATEGORY_CONFIG",
    "CATEGORY_EMBEDDING",
    "CATEGORY_ENTITY",
    "CATEGORY_EPISODIC_MEMORY",
    "CATEGORY_EVENT",
    "CATEGORY_EXPERIENCE",
    "CATEGORY_FACT",
    # Foundation
    "CATEGORY_FOUNDATION",
    # Goal
    "CATEGORY_GOAL",
    # Graph
    "CATEGORY_GRAPH",
    # Communication
    "CATEGORY_INPUT",
    # Knowledge
    "CATEGORY_KNOWLEDGE",
    "CATEGORY_LEARNING",
    # Cognition
    "CATEGORY_MEMORY",
    "CATEGORY_MESSAGE",
    "CATEGORY_METADATA",
    "CATEGORY_MODEL",
    # Base
    "CATEGORY_NODE",
    "CATEGORY_OUTPUT",
    "CATEGORY_PACKET",
    "CATEGORY_PIPELINE",
    "CATEGORY_PLAN",
    "CATEGORY_PLANNING",
    "CATEGORY_REASONING",
    "CATEGORY_REFLECTION",
    "CATEGORY_RELATION",
    "CATEGORY_RESPONSE",
    # Runtime
    "CATEGORY_RUNTIME",
    "CATEGORY_SCHEDULER",
    "CATEGORY_SEMANTIC_MEMORY",
    "CATEGORY_STRATEGY",
    "CATEGORY_SYSTEM",
    # Tool
    "CATEGORY_TOOL",
    # Other
    "CATEGORY_UNKNOWN",
    # Data
    "CATEGORY_VECTOR",
    "CATEGORY_WORKING_MEMORY",
    "CATEGORY_WORLD_MODEL",
]

# ==========================================================
# Foundation
# ==========================================================

CATEGORY_FOUNDATION: Final[str] = "foundation"
CATEGORY_CONFIG: Final[str] = "config"
CATEGORY_SYSTEM: Final[str] = "system"

# ==========================================================
# Base
# ==========================================================

CATEGORY_NODE: Final[str] = "node"
CATEGORY_COMPONENT: Final[str] = "component"
CATEGORY_ENTITY: Final[str] = "entity"
CATEGORY_PACKET: Final[str] = "packet"

# ==========================================================
# Runtime
# ==========================================================

CATEGORY_RUNTIME: Final[str] = "runtime"
CATEGORY_EVENT: Final[str] = "event"
CATEGORY_PIPELINE: Final[str] = "pipeline"
CATEGORY_SCHEDULER: Final[str] = "scheduler"

# ==========================================================
# Cognition
# ==========================================================

CATEGORY_MEMORY: Final[str] = "memory"
CATEGORY_WORKING_MEMORY: Final[str] = "working_memory"
CATEGORY_EPISODIC_MEMORY: Final[str] = "episodic_memory"
CATEGORY_SEMANTIC_MEMORY: Final[str] = "semantic_memory"

CATEGORY_REASONING: Final[str] = "reasoning"
CATEGORY_PLANNING: Final[str] = "planning"
CATEGORY_WORLD_MODEL: Final[str] = "world_model"
CATEGORY_LEARNING: Final[str] = "learning"
CATEGORY_REFLECTION: Final[str] = "reflection"

# ==========================================================
# Knowledge
# ==========================================================

CATEGORY_KNOWLEDGE: Final[str] = "knowledge"
CATEGORY_FACT: Final[str] = "fact"
CATEGORY_BELIEF: Final[str] = "belief"
CATEGORY_EXPERIENCE: Final[str] = "experience"

# ==========================================================
# Goal System
# ==========================================================

CATEGORY_GOAL: Final[str] = "goal"
CATEGORY_STRATEGY: Final[str] = "strategy"
CATEGORY_PLAN: Final[str] = "plan"

# ==========================================================
# Communication
# ==========================================================

CATEGORY_INPUT: Final[str] = "input"
CATEGORY_OUTPUT: Final[str] = "output"
CATEGORY_MESSAGE: Final[str] = "message"
CATEGORY_RESPONSE: Final[str] = "response"

# ==========================================================
# Tool
# ==========================================================

CATEGORY_TOOL: Final[str] = "tool"
CATEGORY_ACTION: Final[str] = "action"

# ==========================================================
# AI
# ==========================================================

CATEGORY_AGENT: Final[str] = "agent"
CATEGORY_MODEL: Final[str] = "model"

# ==========================================================
# Graph
# ==========================================================

CATEGORY_GRAPH: Final[str] = "graph"
CATEGORY_RELATION: Final[str] = "relation"

# ==========================================================
# Data
# ==========================================================

CATEGORY_VECTOR: Final[str] = "vector"
CATEGORY_EMBEDDING: Final[str] = "embedding"
CATEGORY_METADATA: Final[str] = "metadata"

# ==========================================================
# Unknown
# ==========================================================

CATEGORY_UNKNOWN: Final[str] = "unknown"
